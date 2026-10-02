import time

import pytest
from fastapi.testclient import TestClient

from backend import demo, main
from backend.scholar import ScholarError


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.jobs.CACHE_DIR", tmp_path)
    build = demo.build
    monkeypatch.setattr(demo, "build", lambda ni, progress, openalex=True: build(ni, progress, openalex, delay=0))
    return TestClient(main.app)


def wait(client, job):
    for _ in range(200):
        if job["status"] != "running":
            return job
        time.sleep(0.02)
        job = client.get(f"/api/jobs/{job['id']}").json()
    raise AssertionError("job did not finish")


def test_demo_report_flow(client):
    assert client.get("/api/health").json()["status"] == "ok"
    job = wait(client, client.post("/api/reports", json={"query": "demo"}).json())
    assert job["status"] == "done"

    report = client.get("/api/reports/demo").json()
    assert report["profile"]["name"] == "Demo Scholar"
    assert report["citation_map"] == {"available": False, "ready": False}

    csv = client.get("/api/reports/demo/publications.csv")
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.text.lstrip("﻿").startswith("title,year,venue,citations")

    cached = client.post("/api/reports", json={"query": " DEMO "}).json()
    assert cached["status"] == "done"  # 命中缓存


def test_invalid_query(client):
    r = client.post("/api/reports", json={"query": "not a scholar"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_query"


def test_missing_report(client):
    assert client.get("/api/reports/AAAAAAAAAAAA").json()["error"]["code"] == "report_not_found"
    assert client.get("/api/reports/bad-id").status_code == 404
    assert client.post("/api/reports/demo/map").status_code == 404  # 报告还不存在


def test_scholar_error_reaches_the_job(client, monkeypatch):
    def blocked(scholar_id):
        raise ScholarError("scholar_unavailable", "captcha")

    monkeypatch.setattr(main, "fetch_author", blocked)
    job = client.post("/api/reports", json={"query": "A4H2UV8AAAAJ", "openalex": False}).json()
    job = wait(client, job)
    assert job["status"] == "error" and job["error"]["code"] == "scholar_unavailable"


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()


def test_import_saved_page(client):
    from pathlib import Path
    html = (Path(__file__).parent / "fixtures" / "scholar_profile.html").read_text(encoding="utf-8")
    job = wait(client, client.post("/api/reports/import", json={"html": html, "openalex": False}).json())
    assert job["status"] == "done" and job["scholar_id"] == "AbCdEfGhIjKL"
    report = client.get("/api/reports/AbCdEfGhIjKL").json()
    assert report["source"] == "import" and report["profile"]["name"] == "Ada Lovelace"

    bad = client.post("/api/reports/import", json={"html": "<html>login</html>"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "import_invalid"
    no_id = html.replace("AbCdEfGhIjKL", "x").replace("saved from url", "")
    assert client.post("/api/reports/import", json={"html": no_id}).json()["error"]["code"] == "import_no_id"
    ok = client.post("/api/reports/import", json={"html": no_id, "query": "ZZZZZZZZZZZZ", "openalex": False}).json()
    assert wait(client, ok)["scholar_id"] == "ZZZZZZZZZZZZ"
