# Commit paths from Git Bash

Use this when Claude Code runs native Windows Bash and commit protection cannot find a repository named by `/e/...` or another drive-rooted Git-Bash path. Native Python otherwise interprets that spelling as a path on the current drive, such as `E:\e\...`, and the identity check can become unavailable.

## Configure the project

Run `awkit kit hooks --claude` in a project that uses the kit's hooks. It inserts an absent `env.AWKIT_CLAUDE_BASH_PATHS` with the value `git-bash` into `.claude/settings.local.json`. The file must be untracked and unstaged; otherwise, or if tracking cannot be established, the installer skips this insertion and reports a note. Existing hook installation continues. Known non-Git folders remain supported. An existing value belongs to the project and is preserved, even when it already equals `git-bash`. An invalid `env` container is also preserved and reported without stopping hook installation.

The selector adds no command rewrite. Existing shared handlers still prevent duplicate local handlers, and the shared-settings generator is unchanged. The installer retains its separate, existing migration of old generated `|| exit 0` command endings. It writes the same selector on every platform because a local settings file may be shared between machines.

The outer hook reads the delivered environment value once. Conversion applies only on native Windows when the raw tool name is `Bash` and that value matches the current local declaration: both must equal `git-bash`. With no environment selector, the hook keeps existing behavior and does not read local settings. PowerShell, Codex `exec_command`, Linux/WSL and events without that tool identity also retain their existing interpretation.

The declaration comes only from `.claude/settings.local.json` under the hook's already-resolved rule project root. Existing root discovery and `--root` behavior govern that choice. A nested or different-directory rule root without the same declaration makes selected commit protection unavailable, even if the starting project's file has the key. The hook does not search parent, sibling or user-global settings. This checks current configuration; it does not authenticate the client or provider. Retained environment after removing the file or key cannot activate conversion.

Observe a real Claude hook receiving the setting before reporting active protection. A saved setting, successful package installation or a test process launched with supplied environment proves a narrower stage. Keep any unverified native delivery explicit in the task receipt.

Prevents: F9, F11.

## Interpret paths and unavailable protection

The selected mode converts drive-rooted paths such as `/e/work/repo` before combining each `cd` or successive `git -C` component. Relative paths, native absolute drive paths and UNC shares keep their meanings. Quoted spaces and Unicode are supported. Unsupported POSIX roots, WSL shares, drive-relative forms and paths requiring shell expansion produce unavailable protection instead of choosing a different repository. The check does not execute the shell command or search for an alternative repository.

The runner passes a private selector argument only to the exact bundled `check commit --hook` adapter command using `command_protocol = "awkit-v1"`. Custom commands and other bundled actions receive no argument. The original event payload and result-envelope fields are preserved. The setting is read at the outer entry; child adapters use only the explicit argument.

Invalid selection, a missing, unreadable, malformed or mismatching current declaration, or an unavailable selected check adds visible `commit protection unavailable` context and retains an error log. An unavailable declaration stops that commit rule before path conversion or identity lookup. The hook still allows that unavailable check, other rules continue, and ordinary identity or trailer findings keep their existing blocking behavior. Timeouts, spawn failures and an older child rejecting the argument are unavailable checks, not successful protection.

Prevents: F9, F11.

## Removal and mixed versions

The schema-1 installation record adds optional per-file `owned_env` metadata only when awkit inserts the key. An unchanged file is restored from its backup or removed as before. In an edited file, removal deletes the owned key only while its value still matches, preserving changed values and other settings; existing marked-handler removal still applies. Without ownership metadata, the environment key stays.

Hook-file and exclusion backups reserve a fresh file exclusively before changing the file they protect, preserving older copies at the requested path. Existing receipt fields record the actual backup paths. Allocation or backup-write failures leave the protected file unchanged; a failed write may retain its newly created backup. Removal deletes only recorded, hash-matching backups within the managed backup folder and empty directories. Unknown or changed backup files remain, with `.awkit/` still excluded when they keep that directory in use.

An older outer runner ignores this setting. A new outer runner with an older child reports unavailable protection when the child rejects the private argument: `awkit-v1` versions the result envelope, not every adapter argument. Upgrade the actual runner and child before relying on the repair.

Older removers can restore an unchanged file from the existing hash and backup fields. They leave the selector in an edited file because they do not understand `owned_env`; inspect that retained setting when removing a mixed-version installation. Their broader backup-folder cleanup can also delete unrecorded copies. Use the current remover when those copies need to survive.

Prevents: F11.
