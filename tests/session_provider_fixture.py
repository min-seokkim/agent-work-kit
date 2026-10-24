"""Offline stdio fixture. It never calls a model or an external service."""

import json
import os
import sys
import uuid


def main():
    if "--version" in sys.argv:
        print("offline-session-fixture 1")
        return
    threads = {}
    pending = {}

    def emit(value):
        print(json.dumps(value), flush=True)

    def event(method, **params):
        emit(dict(method=method, params=params))

    def finish(thread_id, turn_id, text, status="completed"):
        event("item/completed", threadId=thread_id, turnId=turn_id,
              item=dict(id=turn_id + "-answer", type="agentMessage", phase="final_answer", text=text))
        threads[thread_id]["status"] = {"type": "idle"}
        event("turn/completed", threadId=thread_id, turn=dict(id=turn_id, status=status, items=[], error=None))

    for line in sys.stdin:
        message = json.loads(line)
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
            thread = dict(id=thread_id, status={"type": "idle"}, memory="", count=0)
            threads[thread_id] = thread
            emit(dict(id=ident, result=dict(thread=thread, cwd=params["cwd"], model="offline fixture",
                                           modelProvider="fixture", approvalPolicy=params["approvalPolicy"],
                                           approvalsReviewer=params["approvalsReviewer"],
                                           sandbox={"type": params["sandbox"]})))
        elif method == "thread/read":
            emit(dict(id=ident, result=dict(thread=threads[params["threadId"]])))
        elif method == "turn/start":
            thread_id = params["threadId"]
            thread = threads[thread_id]
            text = params["input"][0]["text"]
            if text == "DISCONNECT":
                os._exit(7)
            thread["count"] += 1
            thread["status"] = {"type": "active"}
            turn_id = f"{thread_id}-turn-{thread['count']}"
            response = dict(id=ident, result=dict(turn=dict(id=turn_id, status="inProgress")))
            if text != "EARLY":
                emit(response)
            event("turn/started", threadId=thread_id, turn=dict(id=turn_id, status="inProgress"))
            if text == "ASK_APPROVAL":
                pending[71] = thread_id, turn_id
                emit(dict(id=71, method="item/commandExecution/requestApproval",
                          params=dict(threadId=thread_id, turnId=turn_id, itemId="command-1",
                                      command="offline fixture only", availableDecisions=["accept", "decline", "cancel"])))
                continue
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
