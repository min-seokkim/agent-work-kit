"""Check a native Codex CLI with initialization and capability probes; never send a turn."""

import argparse
import json
import tempfile
from pathlib import Path

from awkit.codex_session import CodexSession
from awkit.sessions import SessionController


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True, help="Path to the native executable, not an npm wrapper")
    parser.add_argument("--create", action="store_true", help="Also create an empty conversation in a scratch project")
    args = parser.parse_args()
    command = [str(Path(args.codex).resolve(strict=True))]
    with tempfile.TemporaryDirectory(prefix="awkit-codex-check-") as directory:
        client = CodexSession(command, directory, lambda message: None, experimental=True)
        try:
            report = {key: client.runtime.get(key) for key in ("version", "executable_sha256", "capabilities")}
            print(json.dumps(report, indent=2))
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
