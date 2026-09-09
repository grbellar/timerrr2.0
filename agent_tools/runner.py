"""Run a subprocess with a hard elapsed budget and Timerrr lease heartbeats.

python -m agent_tools.runner --client-id 1 --title 'Checkout fix' --budget 1200 -- python task.py
The child inherits no TIMERRR_TOKEN. Requires POSIX process groups.
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import uuid4

from agent_tools.client import TimerrrClient


def stop_process(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", type=int, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--budget", type=int, default=1200)
    parser.add_argument(
        "--work-id",
        type=int,
        help="Join an existing session instead of creating/finishing one",
    )
    parser.add_argument(
        "--artifact", help="Attach this HTTP(S) artifact URL after execution"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not 1 <= args.budget <= 86400 or os.name != "posix":
        parser.error(
            "Provide a command, a budget from 1 to 86400 seconds, and run on a POSIX system."
        )
    client = TimerrrClient()
    actor = "runner-" + str(uuid4())
    began = time.monotonic()
    if args.work_id:
        result = client.call(
            "record_work_event",
            {
                "work_id": args.work_id,
                "kind": "actor_started",
                "actor_id": actor,
                "actor_kind": "agent",
            },
            True,
        )
    else:
        result = client.call(
            "start_work",
            {
                "client_id": args.client_id,
                "title": args.title,
                "budget_seconds": args.budget,
                "actor_id": actor,
                "actor_kind": "agent",
            },
            True,
        )
    work = result["work"]
    work_id = work["id"]
    budget_end = began + min(args.budget, work["budget_remaining_seconds"])
    span = next(s for s in work["spans"] if s["actor_id"] == actor)
    lease_end = (
        began
        + (
            datetime.fromisoformat(span["lease_until"])
            - datetime.fromisoformat(work["server_time"])
        ).total_seconds()
    )
    print(
        f"Timerrr receipt #{work_id}: {client.base_url}/work#work-{work_id}",
        file=sys.stderr,
    )
    env = {k: v for k, v in os.environ.items() if k != "TIMERRR_TOKEN"}
    process = None
    summary, code = "Runner did not start.", 1
    pool = ThreadPoolExecutor(max_workers=1)
    future = None
    next_heartbeat = time.monotonic() + 30
    heartbeat_started = began

    def interrupted(signum, frame):
        raise KeyboardInterrupt()

    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        if time.monotonic() >= min(budget_end, lease_end):
            raise ValueError("Execution budget or lease expired before launch.")
        process = subprocess.Popen(command, env=env, start_new_session=True)
        while process.poll() is None:
            clock = time.monotonic()
            if clock >= min(budget_end, lease_end):
                summary, code = (
                    "Runner stopped at its execution budget or lease boundary.",
                    124,
                )
                break
            if future and future.done():
                update = future.result()
                if not update.get("continue_work"):
                    summary, code = (
                        "Runner stopped because Timerrr ended execution.",
                        124,
                    )
                    break
                updated = next(
                    s
                    for s in reversed(update["work"]["spans"])
                    if s["actor_id"] == actor
                )
                lease_end = (
                    heartbeat_started
                    + (
                        datetime.fromisoformat(updated["lease_until"])
                        - datetime.fromisoformat(update["work"]["server_time"])
                    ).total_seconds()
                )
                future = None
            if clock >= next_heartbeat and future is None:
                heartbeat_started = clock
                future = pool.submit(
                    client.call,
                    "record_work_event",
                    {"work_id": work_id, "kind": "heartbeat", "actor_id": actor},
                    True,
                )
                next_heartbeat = clock + 30
            time.sleep(0.1)
        else:
            code = process.returncode
            summary = f"Runner command exited with status {code}."
    except KeyboardInterrupt:
        summary, code = "Runner interrupted by user.", 130
    except (ValueError, OSError) as error:
        summary, code = f"Runner stopped: {error}", 1
    finally:
        signal.signal(signal.SIGTERM, previous)
        if process:
            stop_process(process)
        pool.shutdown(wait=True, cancel_futures=True)
        if args.artifact:
            try:
                client.call(
                    "record_work_event",
                    {
                        "work_id": work_id,
                        "kind": "artifact",
                        "url": args.artifact,
                        "text": "Runner output reference (not independently verified).",
                    },
                    True,
                )
            except ValueError as error:
                print(f"Artifact update failed: {error}", file=sys.stderr)
        try:
            if args.work_id:
                client.call(
                    "record_work_event",
                    {"work_id": work_id, "kind": "note", "text": summary},
                    True,
                )
                client.call(
                    "record_work_event",
                    {"work_id": work_id, "kind": "actor_stopped", "actor_id": actor},
                    True,
                )
            else:
                client.call(
                    "finish_work", {"work_id": work_id, "summary": summary}, True
                )
        except ValueError as error:
            print(
                f"Receipt update failed: {error}. The execution lease still bounds recorded time.",
                file=sys.stderr,
            )
    print(summary, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
