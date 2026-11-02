"""Run the test suite with one process per test module, several modules at a time.

CI uses this instead of `python -m unittest discover -s tests`. The tests start about 11,000 git processes and
1,000 Python processes; on Windows runners each start costs about 40 ms (git) or 120 ms (Python), so one
process running every module took 11 to 13 minutes there. The modules use their own temporary folders and
home directories and share no ports, so they can run side by side.

Each module runs as `python -m unittest -v MODULE` would, with tests/ on the path and `support` imported first,
as under discovery. Its output is printed whole when it finishes, failing modules are listed again at the end,
and the exit status is 1 when any module failed. Modules start largest file first, so a long module does not start last.

    python scripts/run_tests.py [--jobs N] [--durations N] [MODULE...]
"""

import argparse
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)


def modules():
    files = sorted(TESTS.glob("test_*.py"), key=lambda path: (-path.stat().st_size, path.name))
    return [path.stem for path in files]


def run(module, durations, env):
    # support.py turns off Git's background gc and maintenance for every git the tests start and checks that awkit
    # comes from src/. Discovery imported it once for the whole suite; a module that does not import it itself would
    # otherwise run without it (Git 2.56 on Linux CI then wrote .git/objects/maintenance.lock during a test).
    argv = [sys.executable, "-c", "import support, unittest; unittest.main(module=None)", "-v", module]
    if durations is not None and sys.version_info >= (3, 12):
        argv += ["--durations", str(durations)]
    start = time.perf_counter()
    try:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace")
    except OSError as exc:
        return module, 1, f"cannot start the module's process: {exc}", time.perf_counter() - start
    return module, result.returncode, result.stdout, time.perf_counter() - start


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="modules run at a time")
    parser.add_argument("--durations", type=int, help="pass --durations N to each module (Python 3.12+)")
    parser.add_argument("modules", nargs="*", help="test modules to run (default: every tests/test_*.py)")
    args = parser.parse_args(argv)
    selected = args.modules or modules()
    path = os.pathsep.join(p for p in (str(TESTS), str(ROOT / "src"), os.environ.get("PYTHONPATH", "")) if p)
    env = {**os.environ, "PYTHONPATH": path, "PYTHONUTF8": "1"}
    failed, tests, lock, start = [], 0, threading.Lock(), time.perf_counter()

    def report(future):
        nonlocal tests
        module, code, output, seconds = future.result()
        found = RAN.search(output)
        with lock:
            tests += int(found.group(1)) if found else 0
            if code:
                failed.append(module)
            print(f"===== {module}: {'FAILED' if code else 'ok'} in {seconds:.1f} s", flush=True)
            print(output.rstrip(), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        for module in selected:
            pool.submit(run, module, args.durations, env).add_done_callback(report)
    print(f"===== {len(selected)} modules, {tests} tests, {time.perf_counter() - start:.1f} s with {args.jobs} jobs")
    if failed:
        print("Failed modules: " + ", ".join(sorted(failed)))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
