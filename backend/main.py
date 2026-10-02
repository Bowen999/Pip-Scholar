"""FastAPI 应用：/api/* 为 JSON 接口，其余路径为静态前端（frontend/）。启动：python run.py"""

import os
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, citemap, demo, openalex
from .jobs import Jobs, load_report, map_dir, save_report
from .nature_index import NatureIndex
from .report import build_report, to_csv
from .scholar import fetch_author, parse_scholar_id

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = Path(os.environ.get("PIP_SCHOLAR_FRONTEND", ROOT / "frontend"))

ni = NatureIndex()
jobs = Jobs()
app = FastAPI(title="Pip-Scholar", version=__version__)
# 允许本机其他端口的前端（如 Figma 导出的 Vite 项目）调用 API
app.add_middleware(CORSMiddleware, allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
                   allow_methods=["*"], allow_headers=["*"])


class ApiError(Exception):
    def __init__(self, status, code, message=""):
        super().__init__(message or code)
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def _api_error(_, exc):
    return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}})


class ReportRequest(BaseModel):
    query: str               # Scholar 主页链接、12 位 ID，或 "demo"
    openalex: bool = True    # 是否做作者身份分析
    refresh: bool = False    # 忽略缓存重新抓取


def _generate(scholar_id, use_openalex, progress):
    if scholar_id == demo.DEMO_ID:
        report = demo.build(ni, progress, use_openalex)
    else:
        progress("scholar")
        author = fetch_author(scholar_id)
        enrich = None
        if use_openalex:
            client = openalex.Client()
            enrich = lambda pubs, name, prog: openalex.enrich(pubs, name, client, prog)  # noqa: E731
        report = build_report(author, ni, enrich=enrich, progress=progress)
    save_report(report)


def _cached_report(scholar_id):
    report = load_report(scholar_id) if re.fullmatch(r"demo|[\w-]{12}", scholar_id) else None
    if not report:
        raise ApiError(404, "report_not_found")
    return report


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "nature_index_journals": len(ni),
            "openalex_key": bool(os.environ.get("OPENALEX_API_KEY")), "citation_map": citemap.available()}


@app.post("/api/reports")
def create_report(req: ReportRequest):
    """开始生成报告，返回任务；命中缓存时任务直接是 done。"""
    query = req.query.strip()
    sid = demo.DEMO_ID if query.lower() == demo.DEMO_ID else parse_scholar_id(query)
    if not sid:
        raise ApiError(400, "invalid_query", "Expected a Google Scholar profile URL or a 12-character ID.")
    cached = None if req.refresh else load_report(sid)
    if cached and (cached["authorship"]["enabled"] or not req.openalex):
        return jobs.finished("report", sid)
    return jobs.submit("report", sid, f"report:{sid}:{req.openalex}",
                       lambda progress: _generate(sid, req.openalex, progress))


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise ApiError(404, "job_not_found")
    return job


@app.get("/api/reports/{scholar_id}")
def get_report(scholar_id: str):
    report = _cached_report(scholar_id)
    report["citation_map"] = {"available": citemap.available() and not report["demo"],
                              "ready": (map_dir(scholar_id) / citemap.HTML).exists()}
    return report


@app.get("/api/reports/{scholar_id}/publications.csv")
def get_csv(scholar_id: str):
    return Response(to_csv(_cached_report(scholar_id)), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="publications_{scholar_id}.csv"'})


@app.post("/api/reports/{scholar_id}/map")
def create_map(scholar_id: str):
    report = _cached_report(scholar_id)
    if report["demo"] or not citemap.available():
        raise ApiError(501, "map_unavailable", "pip install citation-map")
    return jobs.submit("map", scholar_id, f"map:{scholar_id}",
                       lambda progress: citemap.generate(scholar_id, map_dir(scholar_id), progress))


@app.get("/api/reports/{scholar_id}/map")
def get_map(scholar_id: str):
    _cached_report(scholar_id)
    path = map_dir(scholar_id) / citemap.HTML
    if not path.exists():
        raise ApiError(404, "map_not_found")
    return FileResponse(path, media_type="text/html")


if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
