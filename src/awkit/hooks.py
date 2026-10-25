"""Hook runner: one command for Claude Code and Codex hooks, driven by the project's rules.toml, or with
--kit-rules by the kit's own when the project has none.

Instructions in a prompt are forgotten as turns accumulate, and they cost context every turn. A rule here
costs nothing until the tool call it describes arrives: the runner reads the hook event on stdin, matches
it against the rules and writes the decision JSON on stdout. Three kinds of rule:

- block: before a tool call, refuse it with a one-line reason (or ask the user).
- verify: after a tool call or when the agent stops, run a command and block once with its output if it fails.
- inject: add one line of guidance as additionalContext, once per session.

A rule matches on the event, the tool, the shell command, the edited paths, the text written and, for
inject rules only, the user's message. A verify rule that runs when the agent stops blocks at most once per
session. A block ends with the failure entries the rule guards, so the agent can read why.

The runner is quiet by default and errs toward missing a rule: a broken input, a broken rule or a command
that times out allows the call and leaves one line in the log. Every firing is logged in
.awkit/hooks.ndjson; `awkit hook report` summarizes it per session.

Claude Code and Codex share the hook contract (event names, input fields, output fields). The only
difference handled here is tool naming: Codex edits files with apply_patch and starts subagents with
spawn_agent, which match rules written for Edit, Write and Agent.
"""

import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

RULES_FILE = "rules.toml"
LOG_FILE = Path(".awkit") / "hooks.ndjson"
STATE_DIR = Path(".awkit") / "hooks"
KINDS = ("block", "verify", "inject")
EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SubagentStop")
CAN_BLOCK = {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop", "SubagentStop"}
CAN_CONTEXT = {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse"}
DEFAULT_EVENTS = {"block": ["PreToolUse"], "verify": ["Stop"], "inject": ["PreToolUse"]}
FIELDS = {"name", "kind", "events", "tools", "shell", "paths", "text", "prompt", "command", "message", "decision",
          "timeout", "prevents", "command_protocol"}
MESSAGE_LIMIT = 200
OUTPUT_LIMIT = 1000
TIMEOUT = 20
# Names Codex sends, and the Claude Code names a rule may use for the same tool. Task is Claude Code's
# earlier name for Agent.
ALIASES = {"apply_patch": ("Edit", "Write"), "spawn_agent": ("Agent",), "Task": ("Agent",)}
PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+?)\s*$", re.M)
# Pasted material in a user message, which Claude Code marks; its words are not the user's request.
PASTED = re.compile(r"^<pasted_content[^>]*>$.*?^</pasted_content[^>]*>$", re.M | re.S)
STOPS = ("Stop", "SubagentStop")

# The failure catalogue entries (kit/failures.md) the runner guards with the kit's rules: work reported as
# done without a check (F1), commits as the agent (F9), writing patterns (F13, F14), and rules that live in
# one agent's memory instead of a file every agent's hooks read (F29).
PREVENTS = {"awkit hook": ("F1", "F9", "F11", "F13", "F14", "F29")}


# Rules


class Rule:
    """One rule from rules.toml. Plain classes, not dataclasses: importing dataclasses costs more than
    the rest of a silent hook call."""

    def __init__(self, name, kind, events, timeout=TIMEOUT, kit="agent-work-kit"):
        self.name, self.kind, self.events, self.timeout, self.kit = name, kind, events, timeout, kit
        self.tools = self.paths = self.shell = self.text = self.prompt = self.command = None
        self.message, self.decision, self.prevents = "", "deny", ()
        self.command_protocol = None

    @property
    def label(self):
        """How a firing names its rule: `awkit commit-identity (F9)`. The entries are in the kit's
        failures.md, where the reason for the rule can be read."""
        return f"awkit {self.name}" + (f" ({', '.join(self.prevents)})" if self.prevents else "")

    @property
    def why(self):
        """What a block ends with: where the entries it guards are described."""
        return f"({self.kit}/failures.md: {', '.join(self.prevents)})" if self.prevents else ""


def _strings(value, key):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"`{key}` must be a non-empty string or list of strings")
    return value


def _regex(value, key):
    if not isinstance(value, str) or not value:
        raise ValueError(f"`{key}` must be a regular expression")
    try:
        return re.compile(value)
    except re.error as exc:
        raise ValueError(f"`{key}` is not a valid regular expression: {exc}") from None


def _rule(raw, variables, timeout):
    if not isinstance(raw, dict):
        raise ValueError("a rule must be a table")
    unknown = sorted(set(raw) - FIELDS)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    name = raw.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
        raise ValueError("`name` must use letters, digits, `.`, `_` and `-`")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise ValueError(f"`kind` must be one of {', '.join(KINDS)}")
    events = _strings(raw.get("events", DEFAULT_EVENTS[kind]), "events")
    allowed = {"block": CAN_BLOCK, "verify": CAN_BLOCK | {"SessionStart"}, "inject": CAN_CONTEXT}[kind]
    wrong = [event for event in events if event not in allowed]
    if wrong:
        raise ValueError(f"a {kind} rule cannot run on {', '.join(wrong)}")
    rule = Rule(name=name, kind=kind, events=events, timeout=timeout, kit=variables["kit"])
    if "tools" in raw:
        rule.tools = _strings(raw["tools"], "tools")
    if "paths" in raw:
        rule.paths = _strings(raw["paths"], "paths")
    if "shell" in raw:
        rule.shell = _regex(raw["shell"], "shell")
    if "text" in raw:
        rule.text = _regex(raw["text"], "text")
    if "prompt" in raw:
        # The user's words say what the user wants, not what a tool call does: they may add a line of
        # guidance, never refuse anything.
        if kind != "inject":
            raise ValueError("`prompt` is for inject rules only; a block or verify rule matches tool calls")
        rule.prompt = _regex(raw["prompt"], "prompt")
    if "command" in raw:
        rule.command = [_expand(part, variables) for part in _strings(raw["command"], "command")]
    if "command_protocol" in raw:
        if raw["command_protocol"] != "awkit-v1" or not rule.command:
            raise ValueError("`command_protocol` needs a command and the supported value awkit-v1")
        rule.command_protocol = raw["command_protocol"]
    if "message" in raw:
        if not isinstance(raw["message"], str) or not raw["message"].strip():
            raise ValueError("`message` must be text")
        # The limit applies to the text the rule's author wrote: {kit} can expand to a long installed path.
        if len(raw["message"].strip()) > MESSAGE_LIMIT:
            raise ValueError(f"`message` has {len(raw['message'].strip())} characters; the limit is {MESSAGE_LIMIT}")
        rule.message = _expand(raw["message"].strip(), variables)
    if "decision" in raw:
        if kind != "block" or raw["decision"] not in ("deny", "ask"):
            raise ValueError("`decision` is `deny` or `ask`, for block rules only")
        rule.decision = raw["decision"]
    if "prevents" in raw:
        rule.prevents = tuple(_strings(raw["prevents"], "prevents"))
        if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", entry) for entry in rule.prevents):
            raise ValueError("`prevents` names failure entries such as F9")
    if "timeout" in raw:
        value = raw["timeout"]
        if isinstance(value, bool) or not isinstance(value, int | float) or not 0 < value <= 600:
            raise ValueError("`timeout` must be a number of seconds between 0 and 600")
        rule.timeout = float(value)
    if kind == "verify" and not rule.command:
        raise ValueError("a verify rule needs `command`")
    if kind != "verify" and not (rule.message or rule.command):
        raise ValueError(f"a {kind} rule needs `message` or `command`")
    return rule


def _expand(text, variables):
    for key, value in variables.items():
        text = text.replace("{" + key + "}", value)
    return text


def load_rules(path, kit=None):
    """(rules, problems) from a rules file, or from several read as one, such as the kit's default bundle.
    A file that cannot be read or parsed raises ValueError; a rule that is wrong is left out and described in
    `problems`, so the other rules still run. `kit` overrides the file's own `kit` value."""
    paths = list(path) if isinstance(path, list | tuple) else [path]
    path = paths[0]
    try:
        data = tomllib.loads("\n".join(Path(each).read_text(encoding="utf-8") for each in paths))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"{path}: {exc}") from None
    return _rules_from_data(data, path, kit)


def _rules_from_data(data, path, kit=None):
    """Validate captured TOML data without reading again or evaluating rules; path labels errors."""
    if data.get("schema") != 1:
        raise ValueError(f"{path}: `schema = 1` is required")
    kit = data.get("kit", "agent-work-kit") if kit is None else kit
    timeout = data.get("timeout_seconds", TIMEOUT)
    if not isinstance(kit, str) or isinstance(timeout, bool) or not isinstance(timeout, int | float) \
            or not 0 < timeout <= 600:
        raise ValueError(f"{path}: `kit` must be text and `timeout_seconds` between 0 and 600")
    variables = {"kit": kit, "python": sys.executable}
    rules, problems, names = [], [], set()
    raw_rules = data.get("rules", [])
    if not isinstance(raw_rules, list):
        raise ValueError(f"{path}: `rules` must be an array of tables ([[rules]])")
    for index, raw in enumerate(raw_rules, 1):
        label = raw.get("name", f"#{index}") if isinstance(raw, dict) else f"#{index}"
        try:
            rule = _rule(raw, variables, float(timeout))
            if rule.name in names:
                raise ValueError("another rule has the same name")
        except ValueError as exc:
            problems.append(f"rule {label}: {exc}")
            continue
        names.add(rule.name)
        rules.append(rule)
    return rules, problems


# Events


class Call:
    """The parts of a hook event the rules look at."""

    def __init__(self, event, session, payload, cwd):
        self.event, self.session, self.payload, self.cwd = event, session, payload, cwd
        self.tool, self.tool_names, self.shell, self.paths, self.text = "", (), "", [], ""
        self.prompt = ""


def _event_name(value):
    """PreToolUse from PreToolUse or pre_tool_use."""
    if not isinstance(value, str):
        return ""
    if "_" in value or value.islower():
        return "".join(part.capitalize() for part in value.split("_"))
    return value


def _relative(path, cwd, root):
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return candidate.as_posix()


def normalize(payload, root):
    """The parts of a hook event the rules look at, the same for Claude Code and Codex."""
    cwd = Path(payload.get("cwd") or root)
    session = payload.get("session_id") if isinstance(payload.get("session_id"), str) else ""
    call = Call(event=_event_name(payload.get("hook_event_name")), session=session, payload=payload, cwd=cwd)
    if isinstance(payload.get("prompt"), str):
        call.prompt = PASTED.sub("", payload["prompt"])
    tool = payload.get("tool_name")
    if not isinstance(tool, str) or not tool:
        return call
    call.tool = tool
    call.tool_names = (tool, *ALIASES.get(tool, ()))
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = data.get("command")
    if isinstance(command, list):
        command = " ".join(str(part) for part in command)
    paths, texts = [], []
    if tool == "apply_patch" and isinstance(command, str):
        paths = PATCH_PATH.findall(command)
        texts = [line[1:] for line in command.splitlines() if line.startswith("+")]
    else:
        if isinstance(command, str):
            # The body of a heredoc fed to a program is its input, such as a file being written, not commands.
            call.shell = _without_heredocs(command) if "<<" in command else command
        for key in ("file_path", "notebook_path"):
            if isinstance(data.get(key), str):
                paths.append(data[key])
        for key in ("content", "new_string", "new_source"):
            if isinstance(data.get(key), str):
                texts.append(data[key])
        for edit in data.get("edits") or []:
            if isinstance(edit, dict) and isinstance(edit.get("new_string"), str):
                texts.append(edit["new_string"])
    call.paths = list(dict.fromkeys(_relative(path, cwd, root) for path in paths))
    call.text = "\n".join(texts)
    return call


def matched_paths(patterns, paths):
    """The paths matching any pattern. A pattern without `/` matches the file name in any folder."""
    found = []
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        if any(fnmatch.fnmatchcase(path if "/" in pattern else name, pattern) for pattern in patterns):
            found.append(path)
    return found


def matches(rule, call):
    if call.event not in rule.events:
        return False
    if rule.tools is not None and not any(fnmatch.fnmatchcase(name, pattern)
                                          for name in call.tool_names for pattern in rule.tools):
        return False
    if rule.shell is not None and not (call.shell and rule.shell.search(call.shell)):
        return False
    if rule.paths is not None and not matched_paths(rule.paths, call.paths):
        return False
    if rule.prompt is not None and not (call.prompt and rule.prompt.search(call.prompt)):
        return False
    return rule.text is None or bool(call.text and rule.text.search(call.text))


# Running rules


class Firing:
    def __init__(self, rule, decision, text):
        self.rule, self.decision, self.text = rule, decision, text  # decision: deny, ask, block or context


def _trim(text, limit=OUTPUT_LIMIT):
    text = text.strip()
    return text if len(text) <= limit else text[:limit - 4].rstrip() + " ..."


def _argv(rule, call, root):
    """The rule's command with {paths} expanded to the matching files that exist, or None when it names
    {paths} and none exists (a deleted file has nothing to check)."""
    argv = []
    for part in rule.command:
        if part == "{paths}":
            files = [path for path in matched_paths(rule.paths or ["*"], call.paths) if (root / path).is_file()]
            if not files:
                return None
            argv.extend(files)
        else:
            argv.append(part.replace("{root}", str(root)))
    return argv


def run_command(argv, payload, root, timeout):
    """(exit code, output) of a rule command fed the hook event on stdin. Raises TimeoutExpired after
    stopping the command's process tree, and OSError when it cannot start."""
    from .process import kill_tree, spawn_options
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(argv, cwd=root, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, **spawn_options())
    try:
        output, _ = process.communicate(json.dumps(payload).encode("utf-8"), timeout=timeout)
    except BaseException:
        kill_tree(process)
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except OSError:
                pass
        raise
    return process.returncode, output.decode("utf-8", errors="replace")


def _from_json(text):
    """A decision object printed by a rule command, or None when the output is not one."""
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


class CommandProtocolError(ValueError):
    """An opted-in command did not deliver a valid completed-check result."""


def _protocol_result(code, output):
    if code != 0:
        raise CommandProtocolError(f"protocol command exited {code} without a successful result")
    value = _from_json(output)
    if (value is None or set(value) != {"protocol", "status", "message"}
            or value.get("protocol") != "awkit-v1" or value.get("status") not in ("pass", "finding", "error")
            or not isinstance(value.get("message"), str) or len(value["message"]) > OUTPUT_LIMIT):
        raise CommandProtocolError("missing or invalid awkit-v1 result; check runner/child capability")
    if value["status"] == "error":
        raise CommandProtocolError(value["message"] or "bundled command execution error")
    return value["status"], value["message"]


def _firing(rule, event, reason):
    text = f"{rule.label}: {reason}"
    if rule.kind == "inject" or event not in CAN_BLOCK:
        return Firing(rule.name, "context", text)
    text = f"{text} {rule.why}".rstrip()
    if event == "PreToolUse":
        return Firing(rule.name, rule.decision if rule.kind == "block" else "deny", text)
    return Firing(rule.name, "block", text)


def evaluate(rule, call, root, state):
    """The rule's firing for this call, or None. Raises on a command that times out or cannot start."""
    if rule.kind == "inject" and rule.name in state["injected"]:
        return None
    # A check when the agent stops blocks once per session; after that the agent's report says the rest.
    stopping = rule.kind == "verify" and call.event in STOPS
    if stopping and rule.name in state["stopped"]:
        return None
    output, chosen = None, None
    if rule.command:
        argv = _argv(rule, call, root)
        if argv is None:
            return None
        code, output = run_command(argv, call.payload, root, rule.timeout)
        if rule.command_protocol:
            status, output = _protocol_result(code, output)
            if status == "pass":
                state["reported"].pop(rule.name, None)
                return None
        else:
            decision = _from_json(output) if output.strip() else None
            if code == 0:
                if decision is None or decision.get("decision") == "allow":
                    state["reported"].pop(rule.name, None)
                    return None
                chosen = decision.get("decision") if decision.get("decision") in ("deny", "ask") else None
                output = str(decision.get("reason") or decision.get("context") or "").strip()
                if not output and not rule.message:
                    return None
    if rule.kind == "verify":
        # Block once per failure: the same output again has already been reported in this session.
        digest = hashlib.sha256((output or "").encode("utf-8")).hexdigest()[:16]
        if state["reported"].get(rule.name) == digest:
            return None
        state["reported"][rule.name] = digest
    parts = [part for part in (rule.message, _trim(output or "")) if part]
    firing = _firing(rule, call.event, "\n".join(parts))
    if chosen and rule.kind == "block" and firing.decision in ("deny", "ask"):
        firing.decision = chosen
    if rule.kind == "inject":
        state["injected"].append(rule.name)
    if stopping:
        state["stopped"].append(rule.name)
    return firing


def render(event, firings):
    """The decision JSON for the event, or None when nothing fired."""
    if not firings:
        return None
    contexts = [f.text for f in firings if f.decision == "context"]
    output = {}
    if event == "PreToolUse":
        specific = {"hookEventName": event}
        for decision in ("deny", "ask"):
            reasons = [f.text for f in firings if f.decision == decision]
            if reasons:
                specific["permissionDecision"] = decision
                specific["permissionDecisionReason"] = "\n".join(reasons)
                break
        if contexts:
            specific["additionalContext"] = "\n".join(contexts)
        output["hookSpecificOutput"] = specific
        return output
    reasons = [f.text for f in firings if f.decision == "block"]
    if reasons and event in CAN_BLOCK:
        output["decision"] = "block"
        output["reason"] = "\n".join(reasons)
    if contexts and event in CAN_CONTEXT:
        output["hookSpecificOutput"] = {"hookEventName": event, "additionalContext": "\n".join(contexts)}
    return output or None


# State and log


def find_root(start):
    """The nearest folder at or above `start` with rules.toml, else the nearest with .git, else `start`."""
    start = Path(start).resolve()
    repository = None
    for folder in (start, *start.parents):
        if (folder / RULES_FILE).is_file():
            return folder
        if repository is None and (folder / ".git").exists():
            repository = folder
    return repository or start


def _state_path(root, session):
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", session or "default")[:120]
    return root / STATE_DIR / f"{name}.json"


def _load_state(root, session):
    try:
        state = json.loads(_state_path(root, session).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if not isinstance(state, dict):
        state = {}
    injected = state.get("injected")
    reported = state.get("reported")
    return {"injected": injected if isinstance(injected, list) else [],
            "reported": reported if isinstance(reported, dict) else {},
            "stopped": state.get("stopped") if isinstance(state.get("stopped"), list) else [],
            "logged": state.get("logged") if isinstance(state.get("logged"), list) else []}


def _prepare(root):
    """Create .awkit and keep it out of Git on this machine the first time the runner writes there."""
    folder = root / ".awkit"
    if folder.is_dir():
        return
    folder.mkdir(parents=True, exist_ok=True)
    if (root / ".git").exists():
        try:
            from .review import exclude_locally
            exclude_locally(root, ".awkit/")
        except Exception:  # noqa: BLE001 - the log must never stop a tool call
            pass


def _save_state(root, session, state):
    path = _state_path(root, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(state), encoding="utf-8")
    os.replace(temporary, path)


def log(root, entry):
    try:
        _prepare(root)
        line = {"time": datetime.now(UTC).isoformat(timespec="seconds"), **entry}
        with open(root / LOG_FILE, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(line, ensure_ascii=False) + "\n")
    except OSError:
        pass


# Bounded observations only; never read hook input, environment, argv or source text.
_ERROR_CONTEXT_FRAMES = 8
_ERROR_CONTEXT_SCAN = 64


def _context_text(value, limit):
    return value[:limit] if type(value) is str else None


def _exception_identifier(exc):
    kind = type(exc)
    module, name = kind.__module__, kind.__qualname__
    return f"{module}.{name}" if type(module) is str and type(name) is str else None


def _collect_error_context(exc, context):
    observations = (
        ("executable", lambda: sys.executable, 512),
        ("python_version", lambda: sys.version, 256),
        ("cwd", os.getcwd, 512),
        ("awkit_file", lambda: vars(sys.modules.get("awkit")).get("__file__"), 512),
        ("hooks_file", lambda: vars(sys.modules.get(__name__)).get("__file__"), 512),
        ("exception_type", lambda: _exception_identifier(exc), 128),
    )
    for key, observe, limit in observations:
        try:
            context[key] = _context_text(observe(), limit)
        except Exception:  # noqa: BLE001 - unavailable context must not replace the original error
            pass
    frames = []
    try:
        trace = exc.__traceback__
        for _ in range(_ERROR_CONTEXT_SCAN):
            if trace is None:
                break
            frame = trace.tb_frame
            module = frame.f_globals.get("__name__")
            line = trace.tb_lineno
            if (type(module) is str and (module == "awkit" or module.startswith("awkit."))
                    and type(line) is int and 0 < line <= 2**31 - 1):
                frames.append({"file": _context_text(frame.f_code.co_filename, 512),
                               "function": _context_text(frame.f_code.co_name, 128), "line": line})
            trace = trace.tb_next
        context["frames"] = frames[-_ERROR_CONTEXT_FRAMES:]
    except Exception:  # noqa: BLE001
        pass


# Entry points


def run(stdin_text, root=None, skip=(), kit_rules=False, event=None):
    """Handle one hook event; returns decision text (empty when nothing fired). Caught handler failures
    allow the call and are logged once. Startup/imports and the initial cwd lookup are outside this handler. Rules named in `skip` do not run. With `kit_rules`,
    a project without rules.toml gets the kit's rules; without it, such a project gets none. `event` is the
    event the handler was registered for, used when the input does not name one."""
    start = Path(root) if root else Path.cwd()
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError("the hook input is not a JSON object")
    except ValueError as exc:
        base = find_root(start)
        if (base / RULES_FILE).is_file():
            log(base, {"session": None, "event": None, "rule": None, "decision": "error",
                       "reason": f"unreadable hook input: {_trim(str(exc), 160)}"})
        return ""
    try:
        if not root and isinstance(payload.get("cwd"), str) and Path(payload["cwd"]).is_dir():
            start = Path(payload["cwd"])
        base = find_root(start)
        if event and not payload.get("hook_event_name"):
            payload = {**payload, "hook_event_name": event}
        return _run(payload, base, skip, kit_rules)
    except Exception as exc:  # noqa: BLE001 - a hook failure must never block the agent
        context = {"schema": 1, "executable": None, "python_version": None, "cwd": None,
                   "awkit_file": None, "hooks_file": None, "exception_type": None, "frames": []}
        try:
            _collect_error_context(exc, context)
        except Exception:  # noqa: BLE001 - preserve the original error even if collection breaks
            pass
        try:
            log(find_root(start), {"session": payload.get("session_id"), "event": payload.get("hook_event_name"),
                                   "rule": None, "decision": "error", "reason": _trim(repr(exc), 160),
                                   "context": context})
        except Exception:  # noqa: BLE001
            pass
        return ""


def _run(payload, root, skip=(), kit_rules=False):
    rules_path, kit = root / RULES_FILE, None
    call = normalize(payload, root)
    if not rules_path.is_file():
        if not kit_rules:
            _missing_rules(root, call)
            return ""
        rules_path, kit = default_rules(root)
    state = _load_state(root, call.session)
    before = json.dumps(state, sort_keys=True)
    errors = []
    try:
        rules, problems = load_rules(rules_path, kit)
    except ValueError as exc:
        rules, problems = [], [str(exc)]
    rules = [rule for rule in rules if rule.name not in skip]
    # A broken rule is reported once per session, not on every tool call.
    for problem in problems:
        if problem not in state["logged"]:
            state["logged"].append(problem)
            errors.append((None, problem))
    firings = []
    # A second stop in the same turn passes, so the agent can report what it could not fix.
    repeated_stop = call.event in ("Stop", "SubagentStop") and payload.get("stop_hook_active") is True
    for rule in rules:
        if repeated_stop and rule.kind != "inject":
            continue
        if not matches(rule, call):
            continue
        try:
            firing = evaluate(rule, call, root, state)
        except subprocess.TimeoutExpired:
            errors.append((rule.name, f"timed out after {rule.timeout:g} s; allowed"))
            continue
        except CommandProtocolError as exc:
            errors.append((rule.name, f"bundled command error: {exc}; allowed"))
            continue
        except OSError as exc:
            errors.append((rule.name, f"could not run {rule.command[0]}: {exc.strerror or exc}; allowed"))
            continue
        if firing:
            firings.append(firing)
    for rule_name, reason in errors:
        log(root, {"session": call.session or None, "event": call.event, "tool": call.tool or None,
                   "rule": rule_name, "decision": "error", "reason": _trim(reason, 200)})
    for firing in firings:
        log(root, {"session": call.session or None, "event": call.event, "tool": call.tool or None,
                   "rule": firing.rule, "decision": firing.decision})
    if json.dumps(state, sort_keys=True) != before:
        _prepare(root)
        _save_state(root, call.session, state)
    output = render(call.event, firings)
    return json.dumps(output, ensure_ascii=False) if output else ""


def _missing_rules(root, call):
    """Leave one line per session in the log of a project that uses awkit (it has .awkit/) but has no
    rules.toml. Anywhere else the runner writes nothing: it must not create files in a folder whose owner
    never chose awkit."""
    if not (root / ".awkit").is_dir():
        return
    state = _load_state(root, call.session)
    if "no rules file" in state["logged"]:
        return
    state["logged"].append("no rules file")
    log(root, {"session": call.session or None, "event": call.event, "tool": call.tool or None, "rule": None,
               "decision": "error", "reason": f"no {RULES_FILE} in {root}; allowed"})
    _save_state(root, call.session, state)


def report(folder):
    """Per session: how often rules fired, blocked, asked, injected and failed, from .awkit/hooks.ndjson."""
    root = find_root(Path(folder))
    result = {"root": str(root), "rules_file": None, "problems": [], "sessions": [], "damaged_lines": 0}
    rules_path = root / RULES_FILE
    if rules_path.is_file():
        result["rules_file"] = str(rules_path)
        try:
            rules, result["problems"] = load_rules(rules_path)
            result["rules"] = [rule.name for rule in rules]
        except ValueError as exc:
            result["problems"] = [str(exc)]
    sessions = {}
    path = root / LOG_FILE
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.is_file() else []
    for line in lines:
        try:
            entry = json.loads(line)
            decision = entry["decision"]
        except (ValueError, KeyError, TypeError):
            result["damaged_lines"] += 1
            continue
        key = entry.get("session") or "(none)"
        summary = sessions.setdefault(key, {"session": key, "first": entry.get("time"), "last": None, "fired": 0,
                                            "blocked": 0, "asked": 0, "injected": 0, "errors": 0, "rules": {}})
        summary["last"] = entry.get("time")
        if decision == "error":
            summary["errors"] += 1
            continue
        summary["fired"] += 1
        summary[{"deny": "blocked", "block": "blocked", "ask": "asked"}.get(decision, "injected")] += 1
        rule = entry.get("rule") or "(none)"
        summary["rules"][rule] = summary["rules"].get(rule, 0) + 1
    result["sessions"] = list(sessions.values())
    return result


def render_report(result):
    lines = []
    if not result["rules_file"]:
        lines.append(f"no {RULES_FILE} in {result['root']}: the hook runner does nothing here unless its handlers "
                     "pass --kit-rules, which applies the kit's rules")
    for problem in result["problems"]:
        lines.append(f"rule problem: {problem}")
    if not result["sessions"]:
        lines.append("no rule has fired yet")
    for summary in result["sessions"]:
        rules = ", ".join(f"{name} {count}" for name, count in sorted(summary["rules"].items()))
        lines.append(f"{summary['session']}  fired {summary['fired']}, blocked {summary['blocked']}, asked "
                     f"{summary['asked']}, injected {summary['injected']}, errors {summary['errors']}"
                     + (f"  ({rules})" if rules else ""))
    if result["damaged_lines"]:
        lines.append(f"{result['damaged_lines']} damaged log lines skipped")
    return "\n".join(lines)


# Commit identity before `git commit` runs


HEREDOC_SUBSTITUTION = re.compile(r"^\$\(\s*cat\s+<<-?\s*['\"]?(\w+)['\"]?[ \t]*\n(.*?)\n[ \t]*\1[ \t]*\n?\s*\)\s*$",
                                  re.S)
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n(.*?)\n[ \t]*\1[ \t]*(?:\n|$)", re.S)
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
IDENT = re.compile(r"\s*(.*?)\s*<([^>]*)>\s*$")


HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _without_heredocs(command):
    """The command without the bodies of heredocs that feed a program, since their lines are its input,
    not commands. A heredoc inside a quoted `$(...)`, as in `-m "$(cat <<'EOF' ... EOF)"`, stays: its text
    is an argument, such as the commit message."""
    lines = command.split("\n")
    kept, index = [], 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for match in HEREDOC.finditer(line):
            before = line[:match.start()]
            if before.count('"') % 2 or before.count("'") % 2:
                continue
            while index < len(lines) and lines[index].strip() != match.group(2):
                index += 1
            index += 1
            break
    return "\n".join(kept)


def _simple_commands(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    words = []
    for token in lexer:
        if token and set(token) <= set(";&|()"):
            yield words
            words = []
        else:
            words.append(token)
    yield words


def git_commits(command):
    """Each `git commit` in a shell command as (environment assignments, git options, commit arguments,
    folder), where folder is where earlier `cd` commands in the same command line moved to (None when
    none did). Raises ValueError when the command cannot be split, such as an unclosed quote."""
    found = []
    folder = None
    for words in _simple_commands(_without_heredocs(command)):
        if len(words) >= 2 and words[0] == "cd":
            target = os.path.expanduser(words[1])
            folder = target if folder is None else os.path.join(folder, target)
            continue
        env, index = {}, 0
        while index < len(words) and ASSIGNMENT.match(words[index]):
            key, value = words[index].split("=", 1)
            env[key] = value
            index += 1
        if index < len(words) and words[index] == "env":
            index += 1
            while index < len(words) and ASSIGNMENT.match(words[index]):
                key, value = words[index].split("=", 1)
                env[key] = value
                index += 1
        if index >= len(words) or Path(words[index]).name not in ("git", "git.exe"):
            continue
        index += 1
        options = []
        while index < len(words) and words[index].startswith("-"):
            if words[index] in ("-c", "-C") and index + 1 < len(words):
                options.append((words[index], words[index + 1]))
                index += 2
            else:
                options.append((words[index], None))
                index += 1
        if index < len(words) and words[index] == "commit":
            found.append((env, options, words[index + 1:], folder))
    return found


def _message(value):
    match = HEREDOC_SUBSTITUTION.match(value)
    return match.group(2) if match else value


def commit_arguments(args, raw, cwd):
    """(message or None, author or None) from `git commit` arguments. The message is None when Git would
    open an editor or reuse a message; the author is the `--author` value."""
    messages, author, file = [], None, None
    index = 0
    while index < len(args):
        arg = args[index]
        following = args[index + 1] if index + 1 < len(args) else None
        if arg in ("-m", "--message") and following is not None:
            messages.append(_message(following))
            index += 2
            continue
        if arg in ("-F", "--file") and following is not None:
            file = following
            index += 2
            continue
        if arg == "--author" and following is not None:
            author = following
            index += 2
            continue
        if arg.startswith("--message="):
            messages.append(_message(arg.split("=", 1)[1]))
        elif arg.startswith("--file="):
            file = arg.split("=", 1)[1]
        elif arg.startswith("--author="):
            author = arg.split("=", 1)[1]
        elif re.fullmatch(r"-[A-Za-z]+", arg) and "m" in arg:
            rest = arg[arg.index("m") + 1:]
            if rest:
                messages.append(_message(rest))
            elif following is not None:
                messages.append(_message(following))
                index += 1
        index += 1
    if messages:
        return "\n\n".join(messages), author
    if file == "-":
        match = HEREDOC.search(raw)
        return (match.group(2) if match else None), author
    if file:
        try:
            return (Path(cwd) / file).read_text(encoding="utf-8", errors="replace"), author
        except OSError:
            return None, author
    return None, author


def _author_ident(folder, env, options):
    """(name, email) Git would use for the commit, with the command's environment and -c settings."""
    argv = ["git", "-C", str(folder)]
    for option, value in options:
        if option == "-c" and value:
            argv += ["-c", value]
    argv += ["var", "GIT_AUTHOR_IDENT"]
    probe = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env={**os.environ, **env})
    match = re.match(r"(.*?) <([^>]*)>", probe.stdout.strip())
    return (match.group(1), match.group(2)) if match else None


def check_commit_command(payload, *, strict=False):
    """Problems with each `git commit` in a Bash hook event: the author and trailers compared with the
    repository's history, as `check commit` does for a written commit. Empty when there is no commit or
    nothing wrong. Legacy calls leave unavailable parsing/checks unjudged; strict calls raise their ValueError."""
    from .checks import commit_identity
    data = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    command = data.get("command")
    if not isinstance(command, str) or "commit" not in command:
        return []
    cwd = Path(payload.get("cwd") or ".")
    try:
        commits = git_commits(command)
    except ValueError:
        if strict:
            raise
        return []
    problems = []
    for env, options, args, moved in commits:
        folder = cwd / moved if moved else cwd
        for option, value in options:
            if option == "-C" and value:
                folder = folder / value
        message, author = commit_arguments(args, command, folder)
        match = IDENT.match(author) if author else None
        ident = (match.group(1), match.group(2)) if match else _author_ident(folder, env, options)
        try:
            report = commit_identity(folder, message=message, author=ident)
        except ValueError:
            if strict:
                raise
            continue
        problems.extend(problem for problem in report["problems"] if problem not in problems)
    return problems


# Installing the runner


HOOK_COMMAND = "awkit hook"
HOOK_EVENTS = ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop")
SETTINGS = {"claude": Path(".claude") / "settings.json", "codex": Path(".codex") / "hooks.json"}
# The done check earlier versions wrote to .claude/settings.local.json.
OLD_DONE_HOOK = "if command -v awkit >/dev/null 2>&1; then awkit check done --hook; fi"


def hook_command(skip=()):
    """The handler command. --kit-rules applies the kit's rules while the project has no rules.toml."""
    return " ".join(["awkit", "hook", "--kit-rules", *(f"--skip {name}" for name in skip)])


def migrate_commands(settings):
    """Remove the shell fallback only from exact command forms earlier awkit versions generated.

    PowerShell 5.1 rejects || before starting the runner (F11). Custom shell commands stay untouched.
    Missing executables must remain visible as launch failures; rule errors are handled by the runner.
    """
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks"), dict):
        return False
    legacy = re.compile(
        r"awkit hook(?: (?:SessionStart|UserPromptSubmit|PreToolUse|PostToolUse|Stop) --kit-hooks"
        r"| --kit-rules)?(?: --skip [A-Za-z0-9_.-]+)* \|\| exit 0"
    )
    changed = False
    for entries in settings["hooks"].values():
        for entry in entries if isinstance(entries, list) else []:
            inner = entry.get("hooks", []) if isinstance(entry, dict) else []
            for handler in inner if isinstance(inner, list) else []:
                command = (handler.get("command") if isinstance(handler, dict)
                           and handler.get("type") == "command" else None)
                if isinstance(command, str) and legacy.fullmatch(command):
                    handler["command"] = command.removesuffix(" || exit 0")
                    changed = True
    return changed


def is_awkit_command(command):
    """A hook command awkit wrote: the runner, with or without skipped rules, or the old done check."""
    return command.strip().startswith("awkit hook") or command == OLD_DONE_HOOK


def _settings_commands(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return []
    return [str(hook.get("command", "")) for entries in hooks.values() if isinstance(entries, list)
            for entry in entries if isinstance(entry, dict) for hook in entry.get("hooks", []) if isinstance(hook, dict)]


def install_settings(top, provider, changes=None, skip=()):
    """Add a handler running `awkit hook` for every hook event to Claude Code's or Codex's project settings.
    Every other key and handler stays as it was, and the file keeps its indentation and characters. When
    another settings file of the same agent runs the runner already, nothing is added. The command names
    awkit, not an interpreter, so the file can be committed. The runner handles rule errors; launch
    failures stay visible to the host. Returns (path, changed)."""
    from .connect import dump_json, read_exact
    top = Path(top)
    path = top / SETTINGS[provider]
    others = [top / ".claude" / "settings.local.json"] if provider == "claude" else []
    if any(cmd.strip().startswith("awkit hook") for other in others for cmd in _settings_commands(other)):
        return others[0], False
    original = read_exact(path) if path.is_file() else ""
    settings = json.loads(original) if original.strip() else {}
    if not isinstance(settings, dict) or not isinstance(settings.setdefault("hooks", {}), dict):
        raise ValueError(f"{path} does not hold a JSON object with a `hooks` object")
    changed = migrate_commands(settings)
    command = hook_command(skip)
    for event in HOOK_EVENTS:
        entries = settings["hooks"].setdefault(event, [])
        commands = [str(hook.get("command", "")) for entry in entries if isinstance(entry, dict)
                    for hook in entry.get("hooks", []) if isinstance(hook, dict)]
        if any(c.strip().startswith("awkit hook") for c in commands):
            continue
        entries.append({"hooks": [{"type": "command", "command": command, "timeout": 60}]})
        changed = True
    if changed:
        text = dump_json(settings, original)
        if changes is not None:
            changes.write(path, text, "merged")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.encode("utf-8", errors="surrogateescape"))
    return path, changed


def remove_entries(path, command, changes=None):
    """Remove hook entries running exactly `command`, which an earlier awkit wrote. Returns True when
    the file changed."""
    from .connect import dump_json, read_exact
    if not path.is_file():
        return False
    original = read_exact(path)
    settings = json.loads(original)
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks, dict):
        return False
    changed = False
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept = [entry for entry in entries if not (isinstance(entry, dict) and entry.get("hooks")
                and all(isinstance(h, dict) and h.get("command") == command for h in entry["hooks"]))]
        if len(kept) != len(entries):
            changed = True
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
    if changed:
        text = dump_json(settings, original)
        if changes is not None:
            changes.write(path, text, "merged")
        else:
            path.write_bytes(text.encode("utf-8", errors="surrogateescape"))
    return changed


# The kit's default rules: the tool-call rules, then the rules that read the session (the user's request, the
# final reply, the kit version). The second file holds only [[rules]] tables, so the two read as one.
BUNDLE = (RULES_FILE, "rules-session.toml")


def kit_folder(root):
    """The kit folder {kit} names in the default rules: one in the project, else the kit installed with
    awkit, so a message that names a guide points at a file that exists on this machine."""
    from .kit_install import kit_root
    for name in ("agent-work-kit", "kit"):
        if (Path(root) / name / "workflow.md").is_file():
            return name
    return str(kit_root())


def default_rules(root):
    """The kit's rules, used when the project has no rules.toml of its own: ([paths], kit folder for {kit})."""
    from .kit_install import kit_root
    return [kit_root().joinpath(name) for name in BUNDLE], kit_folder(root)
