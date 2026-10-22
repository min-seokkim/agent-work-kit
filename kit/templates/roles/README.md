# Role Templates

These templates define the five roles in the [delegation guide](../../delegation.md) independently of provider. Each file has front matter for its name, model tier (`tier`), access (`access`) and description. The body contains the subagent's instructions.

Edit the templates directly or generate provider-specific role files with `awkit kit roles`. Choose a model for each tier in the project profile before generating files.

## Model mappings

These explicit mappings are starting examples for both providers. Tiers describe the work assigned; they do not establish equal capability or cost across providers. Check model access in the target account and client before using them. The Codex names come from the [official model guide](https://learn.chatgpt.com/docs/models); the tier assignments below are the kit's examples.

| Tier | Roles | Claude Code example | Codex example |
|---|---|---|---|
| `efficient` | `scout` | `haiku` | `gpt-6-luna:high` |
| `standard` | `builder`, `writer` | `sonnet` | `gpt-6.1-sol:medium` |
| `judge` | `analyst`, `verifier` | `opus` | `gpt-6.1-sol:high` |
| `top` | Escalated `analyst` | `fable` | `gpt-6-astra:high` |

The commands below configure all three regular tiers. Replace `C:\work\my-project` with an existing project folder. The Codex `:effort` suffix sets `model_reasoning_effort`; awkit's Claude generator accepts model names only.

```powershell
awkit kit roles C:\work\my-project --provider claude --model efficient=haiku --model standard=sonnet --model judge=opus
awkit kit roles C:\work\my-project --provider codex --model efficient=gpt-6-luna:high --model standard=gpt-6.1-sol:medium --model judge=gpt-6.1-sol:high --model top=gpt-6-astra:high
```

Existing role files are skipped and preserved. To change a generated model later, edit the existing role file; rerunning the command with a new mapping does not update it.

## Generator defaults

| Setting | Claude Code | Codex |
|---|---|---|
| Output | `.claude/agents/<role>.md` | `.codex/agents/<role>.toml` |
| Tier omitted from `--model` | awkit supplies `haiku`, `sonnet` or `opus` for the three regular tiers | awkit omits the model fields and warns which roles inherit settings |
| Explicit mapping | `--model tier=model` | `--model tier=model:effort`, with effort optional |
| `--model top=...` | awkit warns and leaves the top mapping out of generated files | awkit also creates `analyst_top.toml` |

The explicit examples above make each provider's regular roles predictable despite these different generator defaults. Model availability is checked by the provider when used, not by `awkit kit roles`.

## Claude Code

Read-only roles receive `tools: Read, Grep, Glob, Bash`. Bash can still modify files, so this setting alone does not enforce read-only access.

The top tier is not written into role files. Under Claude Code's normal model resolution, a call-time model takes precedence over the role file's `model`; select `fable` explicitly when escalating an analyst to `top`, leaving regular `judge` roles on `opus`. Forced model settings can override that selection. Claude Code also supports an `effort` field, but awkit's generator does not write it; add it to the generated file if needed. See [Claude Code subagents](https://code.claude.com/docs/en/sub-agents) for model and effort precedence.

## Codex

For fields omitted from the role file, Codex resolves an explicit spawn setting, then the corresponding `[agents]` default, then the parent's setting. A file that pins only `model` can retain an already resolved effort; set both fields when the role needs a particular combination. These rules are documented in [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

The model in a Codex role file takes precedence over the call-time value, so that call-time mechanism cannot escalate an analyst. Pass `--model top=...` to create an additional `analyst_top` role with the same instructions and the top-tier model.

A role file's `sandbox_mode` cannot override the parent setting, so generated files omit it. Read-only restrictions are expressed in the instructions; verify actual execution permissions in the logs.

## Verify the actual model

For either provider, do not assume the role file proves which model ran. Use `awkit usage` to examine execution logs and check actual models and tokens for the relevant threads.
