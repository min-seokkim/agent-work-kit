"""Read-only protocol observations beside explicit task-record declarations."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .channel import ID, KINDS, REQUESTS, ROLES


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string.")
    return value


def _reference(value, relationships):
    if (not isinstance(value, dict) or set(value) != {"relationship", "message"}
            or not isinstance(value["relationship"], str) or value["relationship"] not in relationships
            or not isinstance(value["message"], str) or not ID.fullmatch(value["message"])):
        raise ValueError("A reference needs a declared relationship and a channel message ID.")
    return dict(value)


def _same_channel(left, right):
    if os.path.normcase(str(left)) == os.path.normcase(str(right)):
        return True
    try:
        return left.samefile(right)
    except OSError:
        return False  # Missing/unreadable evidence is reported when opening the channel.


def _load(record_path):
    # Anchor before resolve: Windows may reject resolving a relative path directly.
    anchor = Path(os.path.abspath(record_path))
    record = json.loads(anchor.read_text(encoding="utf-8-sig"))
    if not isinstance(record, dict) or type(record.get("schema")) is not int or record["schema"] != 1:
        raise ValueError("The task record needs schema 1.")
    session = _text(record.get("session"), "session")
    if not isinstance(record.get("relationships"), list):
        raise ValueError("relationships must be a list.")
    relationships, by_id = [], {}
    for value in record["relationships"]:
        if not isinstance(value, dict):
            raise ValueError("Each relationship must be an object.")
        ident = _text(value.get("id"), "relationship id")
        if ident in by_id:
            raise ValueError(f"Duplicate relationship ID: {ident}")
        role = value.get("local_role")
        if role not in ROLES:
            raise ValueError("local_role must be main or reviewer.")
        counterpart = _text(value.get("counterpart"), "counterpart")
        path = Path(_text(value.get("channel"), "channel"))
        path = Path(os.path.abspath(anchor.parent / path)).resolve()
        row = dict(id=ident, channel=str(path), local_role=role, counterpart=counterpart)
        if "task" in value:
            row["task"] = _text(value["task"], "task")
        for previous in relationships:
            if _same_channel(path, Path(previous["channel"])):
                if (role, counterpart) != (previous["local_role"], previous["counterpart"]):
                    raise ValueError(f"Conflicting roles or identities for channel aliases: {previous['id']}, {ident}")
                row["alias_of"] = previous.get("alias_of", previous["id"])
                break
        relationships.append(row)
        by_id[ident] = row
    values = record.get("obligations", [])
    if not isinstance(values, list):
        raise ValueError("obligations must be a list.")
    obligations, identifiers = [], set()
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("Each obligation must be an object.")
        ident = _text(value.get("id"), "obligation id")
        if ident in identifiers:
            raise ValueError(f"Duplicate obligation ID: {ident}")
        identifiers.add(ident)
        state = value.get("state")
        if state not in ("pending", "done", "no-action"):
            raise ValueError("An obligation state must be pending, done or no-action.")
        evidence = value.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError("Obligation evidence must be a list.")
        row = dict(id=ident, source=_reference(value.get("source"), by_id),
                   responsible_session=_text(value.get("responsible_session"), "responsible_session"),
                   action=_text(value.get("action"), "action"), state=state,
                   evidence=[_reference(ref, by_id) for ref in evidence])
        for field in ("recipient", "revision", "reason"):
            if field in value:
                row[field] = _text(value[field], field)
        obligations.append(row)
    return session, relationships, by_id, obligations


def _read_channel(path, *, include_body=False):
    # mode=ro refuses absent files. Never use Channel.transaction: it prepares/migrates.
    conn = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True, timeout=1)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        if conn.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise ValueError("Unsupported channel database version (expected 1).")
        tables = {row["name"]: row["type"] for row in conn.execute("SELECT name,type FROM sqlite_master")}
        shapes = {
            "messages": {"seq": "INTEGER", "id": "TEXT", "sender": "TEXT", "receiver": "TEXT",
                         "kind": "TEXT", "reply_to": "TEXT", "snap": "TEXT", "at": "TEXT", "body": "TEXT"},
            "cursors": {"role": "TEXT", "seq": "INTEGER"},
        }
        for table, expected in shapes.items():
            actual = {row["name"]: row["type"].upper() for row in conn.execute(f"PRAGMA table_info({table})")}
            if tables.get(table) != "table" or actual != expected:
                raise ValueError(f"Unsupported channel table shape: {table}")
        columns = "seq,id,sender,receiver,kind,reply_to,snap,at" + (",body" if include_body else "")
        rows = [dict(row) for row in conn.execute(f"SELECT {columns} FROM messages ORDER BY seq")]
        seen = {}
        for row in rows:
            if (not isinstance(row["id"], str) or not ID.fullmatch(row["id"]) or row["id"] in seen
                    or row["sender"] not in ROLES or row["receiver"] not in ROLES
                    or row["sender"] == row["receiver"] or row["kind"] not in KINDS
                    or row["id"][0] != ("M" if row["sender"] == "main" else "R")
                    or (row["kind"] == "close" and row["sender"] != "main")
                    or (row["kind"] in ("re", "rebut")) != bool(row["reply_to"])):
                raise ValueError("Unsupported channel message data.")
            if row["reply_to"]:
                parent = seen.get(row["reply_to"])
                if not parent or parent["sender"] != row["receiver"] or parent["receiver"] != row["sender"]:
                    raise ValueError("Unresolved channel reply link.")
            seen[row["id"]] = row
        return rows
    finally:
        conn.close()


def observe(record_path):
    """Return a schema-1 report and exit code; declarations never certify completion."""
    session, relationships, by_id, obligations = _load(record_path)
    report = dict(schema=1, session=session, relationships=relationships, protocol=[],
                  obligations=[], diagnostics=[])
    messages, unavailable = {}, set()
    for relationship in relationships:
        ident = relationship["id"]
        if "alias_of" in relationship:
            original = by_id[relationship["alias_of"]]
            relationship["state"] = original["state"]
            continue
        try:
            rows = _read_channel(relationship["channel"])
        except (OSError, sqlite3.Error, ValueError) as error:
            unavailable.add(ident)
            relationship["state"] = "unavailable"
            report["diagnostics"].append(dict(kind="channel-unavailable", relationship=ident, detail=str(error)))
        else:
            messages[ident] = {row["id"]: row for row in rows}
            relationship["state"] = "closed" if any(row["kind"] == "close" for row in rows) else "open"

    def key(ref):
        relationship = by_id[ref["relationship"]]
        return relationship.get("alias_of", relationship["id"]), ref["message"]

    def resolved(ref):
        ident, message = key(ref)
        return "unavailable" if ident in unavailable else "resolved" if message in messages[ident] else "missing"

    dispositions, groups = {}, {}
    for obligation in obligations:
        row = dict(obligation)
        row["source_status"] = resolved(row["source"])
        row["evidence_resolution"] = [dict(ref, status=resolved(ref)) for ref in row["evidence"]]
        row["support"] = ("unsupported" if row["source_status"] != "resolved"
                          or any(ref["status"] != "resolved" for ref in row["evidence_resolution"])
                          or (row["state"] != "pending" and not row["evidence"])
                          else "references-resolved" if row["evidence"] else "not-required")
        row["conflicts"] = []
        report["obligations"].append(row)
        source = key(row["source"])
        dispositions.setdefault(source, []).append(row)
        group = (*source, row["responsible_session"], row["action"], row.get("recipient"))
        groups.setdefault(group, []).append(row)
        if row["support"] == "unsupported":
            report["diagnostics"].append(dict(kind="unsupported-declaration", obligation=row["id"],
                                              detail="Source or evidence missing/unavailable, or disposition has no evidence."))
    for group in groups.values():
        if len({row["state"] for row in group}) > 1:
            for row in group:
                row["conflicts"] = [other["id"] for other in group if other["id"] != row["id"]]
            report["diagnostics"].append(dict(kind="conflicting-declarations", obligations=[row["id"] for row in group],
                                              detail="Different declared states for the same source, owner, action and recipient."))
    for ident, rows in messages.items():
        relationship = by_id[ident]
        for message in rows.values():
            incoming = message["receiver"] == relationship["local_role"]
            source = dict(relationship=ident, message=message["id"])
            declarations = dispositions.get((ident, message["id"]), [])
            base = dict(source=source, counterpart=relationship["counterpart"], local_role=relationship["local_role"],
                        channel_state=relationship["state"], kind=message["kind"], direction="incoming" if incoming else "outgoing",
                        declarations=[row["id"] for row in declarations],
                        declaration_details=[{field: row[field] for field in
                            ("id", "state", "support", "evidence_resolution", "conflicts")} for row in declarations])
            replies = [dict(relationship=ident, message=row["id"]) for row in rows.values()
                       if row["reply_to"] == message["id"]]
            if message["kind"] in (*REQUESTS, "rebut"):
                state = "response-returned" if replies else "protocol-unanswered" if incoming else "awaiting-reply"
                action = "inspect linked response" if replies else "reply to request" if incoming else "await linked response"
                if declarations and incoming and not replies:
                    action = "reconcile protocol and declaration evidence before another reply"
                report["protocol"].append(dict(base, observation=state, next_protocol_action=action, replies=replies))
            if incoming and message["kind"] in ("re", "rebut"):
                report["protocol"].append(dict(base, observation="returned-response",
                    reply_to=dict(relationship=ident, message=message["reply_to"]),
                    disposition="declared" if declarations else "disposition-unrecorded",
                    next_protocol_action="inspect returned response; record disposition if needed"))
    return report, 1 if unavailable else 0


def render(report):
    lines = [f"Session: {report['session']}"]
    protocol = report["protocol"]
    obligations = report["obligations"]
    lines.append("Protocol: unanswered incoming=" + str(sum(row["observation"] == "protocol-unanswered" for row in protocol))
                 + " | awaiting replies=" + str(sum(row["observation"] == "awaiting-reply" for row in protocol))
                 + " | returned responses without disposition=" + str(sum(row.get("disposition") == "disposition-unrecorded" for row in protocol)))
    lines.append("Declared state: pending=" + str(sum(row["state"] == "pending" for row in obligations))
                 + " | unsupported=" + str(sum(row["support"] == "unsupported" for row in obligations))
                 + " | conflicting=" + str(sum(bool(row["conflicts"]) for row in obligations))
                 + " | unavailable channels=" + str(sum(row["state"] == "unavailable" and "alias_of" not in row
                                                        for row in report["relationships"])))
    def declaration_outstanding(row):
        return row["state"] == "pending" or row["support"] == "unsupported" or bool(row["conflicts"])

    def protocol_outstanding(row):
        return (row["observation"] in ("protocol-unanswered", "awaiting-reply")
                or row.get("disposition") == "disposition-unrecorded"
                or any(declaration_outstanding(item) for item in row["declaration_details"]))

    def relationship_line(row):
        alias = f" (alias of {row['alias_of']})" if "alias_of" in row else ""
        task = f" | declared task: {row['task']}" if "task" in row else ""
        return f"{row['id']}: {row['counterpart']} | local {row['local_role']} | {row['state']}{alias} | {row['channel']}{task}"

    def evidence_text(row):
        return ", ".join(f"{ref['relationship']}:{ref['message']} ({ref['status']})"
                         for ref in row["evidence_resolution"]) or "none"

    def protocol_line(row):
        source = row["source"]
        disposition = f" | {row['disposition']}" if "disposition" in row else ""
        references = "; ".join(f"{item['id']} ({item['state']}, {item['support']}; evidence: {evidence_text(item)})"
                               for item in row["declaration_details"])
        return (f"{source['relationship']}:{source['message']} | {row['counterpart']} | local {row['local_role']} | "
                f"{row['observation']}{disposition} | channel {row['channel_state']} | next: {row['next_protocol_action']}"
                + (f" | declaration refs: {references}" if references else ""))

    relationships = {row["id"]: row for row in report["relationships"]}

    def declaration_lines(row):
        source = row["source"]
        relationship = relationships[source["relationship"]]
        conflict = f" | conflicts: {', '.join(row['conflicts'])}" if row["conflicts"] else ""
        details = "".join(f" | {key}: {row[key]}" for key in ("recipient", "revision", "reason") if key in row)
        return [f"Declared {row['id']} | {source['relationship']}:{source['message']} | {relationship['counterpart']} | "
                f"local {relationship['local_role']} | channel {relationship['state']} | {row['responsible_session']} | {row['state']} | "
                f"action: {row['action']} | support: {row['support']}{conflict}{details}",
                f"  evidence: {evidence_text(row)}"]

    lines.extend("Diagnostic: " + json.dumps(row, ensure_ascii=False) for row in report["diagnostics"])
    unavailable = [row for row in report["relationships"] if row["state"] == "unavailable"]
    if unavailable:
        lines.append("Unavailable relationships:")
        lines.extend(relationship_line(row) for row in unavailable)
    outstanding_protocol = [row for row in protocol if protocol_outstanding(row)]
    outstanding_declarations = [row for row in obligations if declaration_outstanding(row)]
    lines.append("Outstanding protocol and declarations:")
    if not outstanding_protocol and not outstanding_declarations:
        lines.append("Unavailable channel evidence leaves outstanding work unknown." if unavailable
                     else "No outstanding protocol or declaration is recorded.")
    lines.extend(protocol_line(row) for row in outstanding_protocol)
    for row in outstanding_declarations:
        lines.extend(declaration_lines(row))
    lines.append("Relationships:")
    lines.extend(relationship_line(row) for row in report["relationships"] if row["state"] != "unavailable")
    lines.append("Recorded history:")
    lines.extend(protocol_line(row) for row in protocol if not protocol_outstanding(row))
    for row in obligations:
        if not declaration_outstanding(row):
            lines.extend(declaration_lines(row))
    lines.append("Declarations describe recorded intent and evidence references; semantic completion is not verified.")
    return "\n".join(lines)
