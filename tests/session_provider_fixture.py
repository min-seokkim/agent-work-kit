"""Offline stdio fixture. It never calls a model or an external service."""

import json
import os
import sys
import time
import uuid
from pathlib import Path


def main():
    if "--version" in sys.argv:
        print("offline-session-fixture 1")
        return
    history = Path.cwd() / ".offline-native.json"
    threads = json.loads(history.read_text()) if history.exists() else {}
    pending = {}

    def save():
        history.write_text(json.dumps(threads))

    def emit(value):
        print(json.dumps(value), flush=True)

    def event(method, **params):
        emit(dict(method=method, params=params))

    def finish(thread_id, turn_id, text, status="completed"):
        turn = next(turn for turn in threads[thread_id]["turns"] if turn["id"] == turn_id)
        turn["items"].append(dict(id=turn_id + "-answer", type="agentMessage", phase="final_answer", text=text))
        turn["status"] = status
        threads[thread_id]["status"] = {"type": "idle"}
        save()
        event("item/completed", threadId=thread_id, turnId=turn_id,
              item=dict(id=turn_id + "-answer", type="agentMessage", phase="final_answer", text=text))
        event("turn/completed", threadId=thread_id, turn=dict(id=turn_id, status=status, items=[], error=None))

    for line in sys.stdin.buffer:
        message = json.loads(line.decode("utf-8"))
        method, params = message.get("method"), message.get("params", {})
        ident = message.get("id")
        if method is None and ident in pending:
            thread_id, turn_id = pending.pop(ident)
            event("serverRequest/resolved", requestId=ident, threadId=thread_id, turnId=turn_id)
            finish(thread_id, turn_id, "Explicit decision: " + message["result"]["decision"])
        elif method == "initialize":
            emit(dict(id=ident, result=dict(userAgent="offline fixture")))
        elif method == "initialized":
            continue
        elif method == "thread/start":
            thread_id = "fixture-native-" + uuid.uuid4().hex
            thread = dict(id=thread_id, status={"type": "idle"}, memory="", count=0, turns=[])
            threads[thread_id] = thread
            save()
            emit(dict(id=ident, result=dict(thread=thread, cwd=params["cwd"], model="offline fixture",
                                           modelProvider="fixture", approvalPolicy=params["approvalPolicy"],
                                           approvalsReviewer=params["approvalsReviewer"],
                                           sandbox={"type": {"read-only": "readOnly", "workspace-write": "workspaceWrite"}[params["sandbox"]]})))
        elif method == "thread/resume":
            if (Path.cwd() / ".offline-resume-error").exists():
                emit(dict(id=ident, error=dict(code=-32000, message="Active owner conflict; fixture refuses resume")))
                continue
            thread = threads[params["threadId"]]
            thread["status"] = {"type": "idle"}
            save()
            scope = dict(sandbox={"type": "readOnly"}, approvalPolicy=params["approvalPolicy"], approvalsReviewer=params["approvalsReviewer"])
            if (Path.cwd() / ".offline-permission-change").exists():
                scope["approvalPolicy"] = "never"
            emit(dict(id=ident, result=dict(thread=thread, cwd=str(Path.cwd()), model="offline fixture",
                                           modelProvider="fixture", **scope)))
        elif method == "thread/turns/list":
            emit(dict(id=ident, result=dict(data=threads[params["threadId"]]["turns"], nextCursor=None)))
        elif method == "thread/read":
            emit(dict(id=ident, result=dict(thread=dict(threads[params["threadId"]], cwd=str(Path.cwd()), canAcceptDirectInput=True))))
        elif method == "turn/steer":
            thread_id = params["threadId"]
            thread = threads[thread_id]
            active = next((turn for turn in thread["turns"] if turn["status"] == "inProgress"), None)
            if active is None or active["id"] != params["expectedTurnId"]:
                emit(dict(id=ident, error=dict(code=-32600, message="expected turn mismatch")))
                continue
            text = params["input"][0]["text"]
            if text == "LOSE_UPDATE_RESPONSE":
                os._exit(9)
            emit(dict(id=ident, result=dict(turnId=active["id"])))
            if text != "KEEP_HOLDING":
                finish(thread_id, active["id"], "Updated same turn: " + text)
        elif method == "turn/start":
            thread_id = params["threadId"]
            thread = threads[thread_id]
            text = params["input"][0]["text"]
            if text == "DISCONNECT":
                os._exit(7)
            thread["count"] += 1
            thread["status"] = {"type": "active"}
            turn_id = f"{thread_id}-turn-{thread['count']}"
            turn = dict(id=turn_id, status="inProgress", items=[dict(type="userMessage", id=turn_id + "-user",
                        clientId=params.get("clientUserMessageId"), content=params["input"])])
            thread["turns"].append(turn)
            save()
            response = dict(id=ident, result=dict(turn=dict(id=turn_id, status="inProgress")))
            if text in ("LOST_RESPONSE", "MISSING_RECORD", "AMBIGUOUS_RESPONSE"):
                turn["status"] = "completed"
                turn["items"].append(dict(type="agentMessage", id=turn_id + "-answer", text="Recovered: " + text))
                if text == "AMBIGUOUS_RESPONSE":
                    turn["items"].append(dict(turn["items"][0], id=turn_id + "-duplicate"))
                thread["status"] = {"type": "idle"}
                save()
                if text == "MISSING_RECORD":
                    emit(response)
                os._exit(8)
            if text != "EARLY":
                emit(response)
            event("turn/started", threadId=thread_id, turn=dict(id=turn_id, status="inProgress"))
            if text in ("ASK_APPROVAL", "ASK_QUOTED_APPROVAL"):
                callback = "sdk-callback-fixture" if text == "ASK_QUOTED_APPROVAL" else 71
                pending[callback] = thread_id, turn_id
                emit(dict(id=callback, method="item/commandExecution/requestApproval",
                          params=dict(threadId=thread_id, turnId=turn_id, itemId="command-1",
                                      command="offline fixture only", availableDecisions=["accept", "decline", "cancel"])))
                continue
            if text == "HOLD":
                continue
            if text == "DELAYED_FINISH":
                time.sleep(7)  # Deterministically exceeds the old six-second harness deadline.
            answer = "Remembered: " + thread["memory"] if text == "recall" else "Fixture reply: " + text
            if not thread["memory"]:
                thread["memory"] = text
            finish(thread_id, turn_id, answer)
            if text == "EARLY":
                emit(response)
        elif method == "turn/interrupt":
            emit(dict(id=ident, result={}))
            finish(params["threadId"], params["turnId"], "", "interrupted")
        else:
            emit(dict(id=ident, error=dict(code=-32601, message="Unknown fixture method")))


if __name__ == "__main__":
    main()
