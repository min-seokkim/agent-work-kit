# Role Templates

These templates define the five roles in the [delegation guide](../../delegation.md) independently of provider. Each file has front matter for its name, model tier (`tier`), access (`access`) and description. The body contains the subagent's instructions.

Edit the templates directly or generate provider-specific role files with `awkit kit roles`.

```powershell
awkit kit roles C:\work\my-project --provider claude
awkit kit roles C:\work\my-project --provider codex --model efficient=<efficient-model> --model judge=<judge-model>:high
```

Existing role files are skipped and preserved.

## Claude Code

The command creates `.claude/agents/<role>.md`. Without explicit tier mappings, it uses `haiku` for `efficient`, `sonnet` for `standard` and `opus` for `judge`. Read-only roles receive `tools: Read, Grep, Glob, Bash`. Bash can still modify files, so this setting alone does not enforce read-only access.

The top tier is not written into role files. Claude Code's call-time model selection takes precedence over the role file's `model`; specify the model in the call when escalating an analyst to the top tier.

## Codex

The command creates `.codex/agents/<role>.toml`. There is no built-in tier mapping for Codex. It writes `model` and `model_reasoning_effort` only for tiers supplied as `--model tier=model` or `--model tier=model:effort`. Unconfigured roles inherit the `[agents]` defaults or the parent session's model, and the command lists them in a warning. Explicitly configure `judge` to avoid running judgment roles on the default model.

The model in a Codex role file takes precedence over the call-time value, so that call-time mechanism cannot escalate an analyst. Pass `--model top=...` to create an additional `analyst_top` role with the same instructions and the top-tier model.

A role file's `sandbox_mode` cannot override the parent setting, so generated files omit it. Read-only restrictions are expressed in the instructions; verify actual execution permissions in the logs.

## Verify the actual model

For either provider, do not assume the role file proves which model ran. Use `awkit usage` to examine execution logs and check actual models and tokens for the relevant threads.
