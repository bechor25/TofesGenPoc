"""In-process background jobs + an SSE event stream.

Slow pipeline work (extraction can take minutes on gpt-5.1, image render is an
expensive metered call) runs on a daemon thread so the HTTP request returns at
once. Each job captures a log marker; the SSE stream reports the latest real
pipeline stage (mapped to Hebrew) plus elapsed seconds until the job finishes."""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from doc2tests.api.status import friendly_stage
from doc2tests.common.logging import get_logger, log_marker, logs_since

_log = get_logger("api.jobs")


@dataclass
class Job:
    id: str
    marker: int
    started: float
    status: str = "running"  # running | done | error
    result: Any = None
    error: str | None = None


class JobManager:
    """Starts jobs on daemon threads and streams their progress. Kept generic:
    the job's return value is opaque and fetched via ``get`` / the SSE ``done``
    frame signals completion, so callers serialize results however they like."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def start(self, fn: Callable[[], Any]) -> str:
        with self._lock:
            self._counter += 1
            job_id = f"job-{self._counter}"
        job = Job(id=job_id, marker=log_marker(), started=time.time())
        self._jobs[job_id] = job

        def run() -> None:
            try:
                job.result = fn()
                job.status = "done"
            except BaseException as exc:  # noqa: BLE001 - surfaced via job.error
                job.error = str(exc)
                job.status = "error"
                _log.exception("job %s failed", job_id)

        threading.Thread(target=run, daemon=True).start()
        return job_id

    def get(self, job_id: str) -> Job:
        """Return the job or raise KeyError (routes convert that to 404)."""
        return self._jobs[job_id]

    def events(self, job_id: str, poll: float = 0.4) -> Iterator[str]:
        """SSE frames: ``data: {json}\\n\\n`` with stage + elapsed while running,
        then a single ``done`` frame (carrying ``error`` if it failed). If the job
        is already finished, yields exactly one ``done`` frame and returns."""
        job = self.get(job_id)
        while True:
            stage = friendly_stage(logs_since(job.marker))
            elapsed = int(time.time() - job.started)
            if job.status == "running":
                yield _frame({"stage": stage, "elapsed": elapsed, "done": False})
                time.sleep(poll)
            else:
                yield _frame({"stage": stage, "elapsed": elapsed, "done": True,
                              "error": job.error})
                return


def _frame(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
