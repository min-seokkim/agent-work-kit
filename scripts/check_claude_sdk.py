"""Check the installed optional runtime without connecting, authentication or history."""

import importlib.metadata
import inspect
import json
import subprocess
import sys
from dataclasses import fields

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, UserMessage

from awkit.claude_session import SDK_VERSION, executable

assert importlib.metadata.version("claude-agent-sdk") == SDK_VERSION
option_fields = {field.name for field in fields(ClaudeAgentOptions)}
assert {"session_id", "resume", "cli_path", "can_use_tool", "system_prompt", "setting_sources"} <= option_fields
assert {"uuid", "origin"} <= {field.name for field in fields(UserMessage)}
assert {"uuid", "session_id", "origin", "terminal_reason"} <= {field.name for field in fields(ResultMessage)}
assert "session_id" in inspect.signature(ClaudeSDKClient.query).parameters
assert inspect.isasyncgenfunction(ClaudeSDKClient.receive_messages)
binary, digest = executable(None)
result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=15, check=True)
assert result.stdout.strip().startswith("2.1.310 "), result.stdout
print(json.dumps(dict(python=sys.version, sdk=SDK_VERSION, cli=result.stdout.strip(),
                      binary=str(binary), sha256=digest, model_queries=0, native_connections=0), indent=2))
