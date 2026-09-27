#!/usr/bin/env -S uv run --script
"""Run the repro, capture a hang, and stop only the process group we started."""
import argparse
from contextlib import suppress
import os
from pathlib import Path
import signal
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--timeout", type=float, default=180, help="maximum wait for Mill, in seconds")
args = parser.parse_args()
if args.timeout <= 0:
    parser.error("timeout must be positive")

root = Path(__file__).resolve().parent
output = root / "out" / f"repro-{time.time_ns()}"
output.mkdir(parents=True)
log = output / "run.log"
print(f"Evidence: {output}", flush=True)
with log.open("w") as stream:
    process = subprocess.Popen(
        ["./mill", "--no-daemon", "--ticker", "false", "repro.test"],
        cwd=root, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
        env={**os.environ, "MILL_OUTPUT_DIR": str(output)},
    )
    try:
        deadline = time.monotonic() + args.timeout
        while process.poll() is None and time.monotonic() < deadline:
            if "Completed tests" in log.read_text(errors="replace"):
                deadline = min(deadline, time.monotonic() + 3)
            time.sleep(0.2)
        if process.poll() is not None:
            print(log.read_text(errors="replace"))
            raise SystemExit(process.returncode)

        print("Still running; capturing thread dumps.", flush=True)
        # Mill records its JVM's PID in this run's output directory.
        for pidfile in output.glob("mill-no-daemon/pid-*/processId"):
            pid = pidfile.read_text().strip()
            for sample in (1, 2):
                with (output / f"threads-{pid}-{sample}.txt").open("w") as dump:
                    subprocess.run(["jcmd", str(pid), "Thread.print", "-l"], stdout=dump, stderr=subprocess.STDOUT, timeout=10)
                if sample == 1:
                    time.sleep(1)
    finally:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)
raise SystemExit(124)
