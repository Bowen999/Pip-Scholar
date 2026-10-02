"""后台任务：耗时的抓取在线程中执行，前端轮询进度；报告以 JSON 缓存在 cache/ 下。"""

import json
import logging
import os
import threading
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.environ.get("PIP_SCHOLAR_CACHE", ROOT / "cache"))
log = logging.getLogger("pip_scholar")


def report_path(scholar_id):
    return CACHE_DIR / "reports" / f"{scholar_id}.json"


def map_dir(scholar_id):
    return CACHE_DIR / "maps" / scholar_id


def load_report(scholar_id):
    path = report_path(scholar_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_report(report):
    path = report_path(report["scholar_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{uuid.uuid4().hex}.tmp")  # 先写临时文件再替换，避免读到半个文件
    tmp.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


class Jobs:
    """任务状态：status = running | done | error；stage / done / total 描述进度。"""

    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def _new(self, kind, scholar_id, key, status):
        job = {"id": uuid.uuid4().hex[:12], "kind": kind, "scholar_id": scholar_id, "status": status,
               "stage": None, "done": None, "total": None, "error": None, "_key": key}
        self._jobs[job["id"]] = job
        return job

    def get(self, job_id):
        job = self._jobs.get(job_id)
        return {k: v for k, v in job.items() if not k.startswith("_")} if job else None

    def finished(self, kind, scholar_id):
        """命中缓存：直接返回一个已完成的任务，前端流程不变。"""
        with self._lock:
            job = self._new(kind, scholar_id, None, "done")
            job["stage"] = "done"
        return self.get(job["id"])

    def submit(self, kind, scholar_id, key, fn):
        """fn(progress) 在后台线程运行；同一 key 的任务未结束时复用它。"""
        with self._lock:
            for job in self._jobs.values():
                if job["_key"] == key and job["status"] == "running":
                    return self.get(job["id"])
            job = self._new(kind, scholar_id, key, "running")
        threading.Thread(target=self._run, args=(job, fn), daemon=True).start()
        return self.get(job["id"])

    def _run(self, job, fn):
        def progress(stage, done=None, total=None):
            job.update(stage=stage, done=done, total=total)

        try:
            fn(progress)
            job.update(status="done", stage="done")
        except Exception as e:  # noqa: BLE001 —— 所有错误都要回传给前端
            code = getattr(e, "code", "internal")
            if code == "internal":
                log.exception("job %s failed", job["id"])
            job.update(status="error", error={"code": code, "message": str(e)})
