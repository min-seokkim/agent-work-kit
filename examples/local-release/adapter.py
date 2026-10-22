"""File-only release simulator. It never connects to a server or runs Docker."""

import json
import sys
import time
from pathlib import Path

phase, target, requested = sys.argv[1:]
base = Path(__file__).resolve().parent / ".demo-target"
state_path = base / "current.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {"release": None}
fault_path = Path(__file__).resolve().parent / "faults.json"
faults = json.loads(fault_path.read_text()) if fault_path.exists() else {}
if faults.get("orphan_phase") == phase:
    # Imitate a deploy script that starts its own child (ssh, docker, ...) and then hangs.
    import subprocess
    subprocess.Popen([sys.executable, "-c",
                      "import sys, time; time.sleep(3); open(sys.argv[1], 'w').write('alive')",
                      faults["orphan_marker"]])
    time.sleep(30)
if faults.get("sleep_phase") == phase:
    time.sleep(2)
if faults.get("exit_phase") == phase:
    raise SystemExit(faults.get("exit_code", 7))

if phase == "preflight":
    print(json.dumps({"target": faults.get("target", target), "release": state["release"]}))
elif phase == "backup":
    base.mkdir(exist_ok=True)
    (base / "backup.json").write_text(json.dumps(state))
elif phase in ("deploy", "rollback"):
    base.mkdir(exist_ok=True)
    if not faults.get("skip_change"):
        state_path.write_text(json.dumps({"release": requested}))
    if faults.get("fail_after_change") and phase == "deploy":
        raise SystemExit(9)
elif phase == "verify":
    if faults.get("malformed"):
        print("not a report")
    else:
        release = state["release"]
        healthy = bool(release) and not release.startswith("f") and release not in faults.get("unhealthy", [])
        checks = [{"name": "service", "ok": healthy}]
        if "checks" in faults:
            checks = faults["checks"]
        print(json.dumps({"target": faults.get("target", target), "release": release, "checks": checks}))
else:
    raise SystemExit(2)
