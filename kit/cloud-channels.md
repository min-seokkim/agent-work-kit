# Cloud channels through Desktop

Keep the database on its host. A cloud session uses a local MCP process through an online Claude Desktop; it does not open a copied or mounted SQLite file. The verified route is a Desktop-started cloud Cowork conversation on Windows. Other providers and offline operation need their own trial. This carries messages, not host files, snapshot creation or agent wake-up.

Create a channel locally with the normal `post` command, then configure one stdio MCP process for that existing channel:

```sh
awkit channel --db /absolute/project/.awkit/review.sqlite3 serve --role reviewer --consumer cloud-reviewer
```

Use an absolute installed executable and DB path in Desktop's `mcpServers` entry, and back up its configuration before editing. For example, replace both paths here with your host paths:

```json
{
  "mcpServers": {
    "awkit-review": {
      "command": "C:\\path\\to\\awkit.exe",
      "args": ["channel", "--db", "C:\\project\\.awkit\\review.sqlite3", "serve", "--role", "reviewer", "--consumer", "cloud-reviewer"]
    }
  }
}
```

Restart Desktop to load the process. Changing the channel requires editing the binding and restarting; missing or replaced databases fail instead of being recreated. Keep the returned `channel_id` with the conversation's context. Account/device access to this tool grants the bound role; different cloud sessions sharing its consumer share receipt positions. Tool arguments cannot change that binding. Local filesystem permissions protect the DB; there is no network listener or additional authentication.

| Tool | Use |
|---|---|
| `channel_post(channel_id, key, kind, body, reply_to?, snap?)` | Keep the intended channel ID and generate a stable key before sending. A different channel ID fails before writing. Retry the identical payload with that key after a lost response. A conflict fails; successful retries return the original ID, including after closure. Bodies are limited to 65,536 UTF-8 bytes. `snap` is an unverified reference. |
| `channel_read()` | Read one incoming segment of at most 4,096 Unicode characters. Retain its ID, offsets and total length, assemble every segment, and process only a complete message. The outstanding segment repeats until acknowledged. |
| `channel_ack(receipt)` | Acknowledge that segment after retaining it. The message position advances only after its final segment. Retry the latest acknowledgement safely; older or unknown tokens fail. Receipt is not request completion or verdict acceptance. |
| `channel_requests(after_seq?)` | On resume, recover unanswered requests and rebuttals even if their receipts were acknowledged. Pages contain at most 20 metadata rows; continue with `next_after` until null. |
| `channel_message(message_id, offset?)` | Recover an incoming body's segments by ID without changing receipts. Continue at `next_offset` until `complete`. Use this after losing already acknowledged partial text. |

Delivery is at least once. On resume recover pending requests, then read new segments. Reuse send keys and message IDs to avoid repeating work. Closure remains visible while outstanding messages remain readable. Existing CLI commands and their `new` positions keep their behavior; delivery tables extend schema 2 without changing its version. Errors are explicit; do not retry a denied operation through another route. `serve` uses bounded JSON lines on stdin/stdout and diagnostic stderr; it neither wakes ended agents nor schedules polling.

Clients must send UTF-8. Undecodable input stops the process with a stderr diagnostic; reconnect with valid input and recover using the same keys and consumer. Blank lines are ignored.

Prevents: F29.
