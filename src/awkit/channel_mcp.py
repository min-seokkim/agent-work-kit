"""A bounded stdio MCP adapter for one host-local channel participant."""

import json
import sqlite3
import sys

from . import __version__
from .channel import KINDS
from .channel_delivery import Delivery

PREVENTS = {"awkit channel serve": ("F29",)}

MAX_LINE_CHARS = 524288
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
SPECS = {
    "channel_post": ("Send once using a stable key; retry the identical payload with the same key after a lost response. Bodies are limited to 65536 UTF-8 bytes. Snapshot references are unverified.",
                     {"channel_id": str, "key": str, "kind": str, "body": str, "reply_to": str, "snap": str}, ("channel_id", "key", "kind", "body")),
    "channel_read": ("Read one incoming body segment. Replay continues until its receipt is acknowledged. Assemble all segments before processing the message.", {}, ()),
    "channel_ack": ("Acknowledge only the received segment. This is not task completion or review-verdict acceptance.", {"receipt": str}, ("receipt",)),
    "channel_requests": ("Recover unanswered requests and rebuttals on resume, even after receipt acknowledgement. Page using next_after.", {"after_seq": int}, ()),
    "channel_message": ("Read an incoming message by ID in bounded segments without changing receipt positions. Continue with next_offset until complete.", {"message_id": str, "offset": int}, ("message_id",)),
}


def tool_list():
    tools = []
    for name, (description, fields, required) in SPECS.items():
        properties = {field: {"type": "integer" if kind is int else "string"} for field, kind in fields.items()}
        for field in ("reply_to", "snap", "offset", "after_seq"):
            if field in properties:
                properties[field]["type"] = [properties[field]["type"], "null"]
        for field in ("offset", "after_seq"):
            if field in properties:
                properties[field]["minimum"] = 0
        if name == "channel_post":
            properties["kind"]["enum"] = list(KINDS)
            properties["key"]["maxLength"] = 128
            properties["body"]["maxLength"] = 65536
        tools.append({"name": name, "description": description,
                      "inputSchema": {"type": "object", "properties": properties,
                                      "required": list(required), "additionalProperties": False},
                      "annotations": {"readOnlyHint": name in ("channel_requests", "channel_message"),
                                      "destructiveHint": False, "openWorldHint": False}})
    return tools


def error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


class Server:
    def __init__(self, delivery):
        self.delivery = delivery
        self.initialized = False

    def handle(self, request):
        if not isinstance(request, dict):
            return error(None, -32600, "Expected one JSON-RPC object")
        request_id = request.get("id")
        if (request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str)
                or ("id" in request and (type(request_id) not in (str, int) or
                    (isinstance(request_id, str) and len(request_id) > 128)))):
            return error(None, -32600, "Invalid JSON-RPC request")
        # Notifications never execute channel operations and never receive replies.
        if "id" not in request:
            return None
        method = request["method"]
        params = request.get("params", {})
        if not isinstance(params, dict):
            return error(request_id, -32602, "params must be an object")
        if method == "initialize":
            if self.initialized:
                return error(request_id, -32600, "Already initialized")
            if not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("capabilities"), dict):
                return error(request_id, -32602, "initialize requires protocolVersion and capabilities")
            self.initialized = True
            version = params["protocolVersion"]
            result = {"protocolVersion": version if version in PROTOCOLS else PROTOCOLS[-1],
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "awkit-channel", "version": __version__},
                      "instructions": "Bound to one host channel, role and consumer. Access is account/device scoped. Recover unanswered requests on resume. This adapter polls; it cannot wake ended agents."}
        elif method == "ping":
            result = {}
        elif not self.initialized:
            return error(request_id, -32002, "Initialize first")
        elif method == "tools/list":
            result = {"tools": tool_list()}
        elif method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or name not in SPECS:
                return error(request_id, -32602, "Unknown channel tool")
            arguments = params.get("arguments", {})
            _, fields, required = SPECS[name]
            if isinstance(arguments, dict):
                arguments = {key: value for key, value in arguments.items()
                             if not (key in ("reply_to", "snap", "offset", "after_seq") and value is None)}
            if (not isinstance(arguments, dict) or set(arguments) - set(fields)
                    or any(field not in arguments for field in required)
                    or any(type(value) is not fields[field] for field, value in arguments.items())):
                return error(request_id, -32602, "Invalid tool arguments; channel binding cannot be overridden")
            try:
                value = getattr(self.delivery, name.removeprefix("channel_"))(**arguments)
                failed = False
            except (ValueError, TypeError, OSError, sqlite3.Error, UnicodeError) as exc:
                value = self.delivery.result(error=str(exc))
                failed = True
            result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=True)}], "isError": failed}
        else:
            return error(request_id, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": request_id, "result": result}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError("Non-finite JSON number")


def serve(path, role, consumer, *, input_stream=None, output_stream=None):
    source = sys.stdin if input_stream is None else input_stream
    output = sys.stdout if output_stream is None else output_stream
    server = Server(Delivery(path, role, consumer))
    while True:
        line = source.readline(MAX_LINE_CHARS + 1)
        if not line:
            return 0
        if len(line) > MAX_LINE_CHARS:
            while line and not line.endswith("\n"):
                line = source.readline(MAX_LINE_CHARS + 1)
            response = error(None, -32700, "JSON line exceeds 524288 characters")
        else:
            if not line.strip():
                continue
            try:
                request = json.loads(line, object_pairs_hook=unique_object, parse_constant=invalid_constant)
                response = server.handle(request)
            except (ValueError, RecursionError):
                response = error(None, -32700, "Invalid JSON")
        if response is not None:
            output.write(json.dumps(response, ensure_ascii=True) + "\n")
            output.flush()
