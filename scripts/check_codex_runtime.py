"""Check a native Codex CLI with initialization and capability probes; never send a turn."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from awkit.codex_session import CodexSession
from awkit.sessions import SessionController


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    launch = parser.add_mutually_exclusive_group(required=True)
    launch.add_argument("--codex", help="Path to the native executable, not an npm wrapper")
    launch.add_argument("--npm-root", type=Path, help="Isolated npm install prefix containing @openai/codex")
    parser.add_argument("--create", action="store_true", help="Also create an empty conversation in a scratch project")
    args = parser.parse_args()
    if args.npm_root:
        filename = "codex.exe" if os.name == "nt" else "codex"
        candidates = [path for directory in ("bin", "codex")
                      for path in (args.npm_root / "node_modules" / "@openai").glob(
                          f"codex*/vendor/*/{directory}/{filename}") if path.is_file()]
        if len(candidates) != 1:
            parser.error(f"Expected one installed native Codex executable, found {len(candidates)}.")
        executable = candidates[0]
    else:
        executable = Path(args.codex)
    command = [str(executable.resolve(strict=True))]
    with tempfile.TemporaryDirectory(prefix="awkit-codex-check-") as directory:
        client = CodexSession(command, directory, lambda message: None, experimental=True)
        try:
            report = {key: client.runtime.get(key) for key in ("version", "executable_sha256", "capabilities")}
            print(json.dumps(dict(report, model_queries=0), indent=2))
            assert all(value["supported"] for value in report["capabilities"].values()), report
        finally:
            client.close()
        if args.create:
            controller = SessionController(directory, command)
            try:
                view = controller.create(name="Runtime check", responsibility="Empty capability check; no work sent")
                assert view["session"]["native_id"], view["session"].get("error")
                assert not view["attempts"]
                print("Empty conversation created; no turn submitted.")
            finally:
                controller.close()


if __name__ == "__main__":
    main()
