from pathlib import Path

import pytest

from backend import scholar
from backend.nature_index import NatureIndex
from backend.report import build_report
from backend.scholar import ScholarError
from backend.scholar_html import parse_profile_html

HTML = (Path(__file__).parent / "fixtures" / "scholar_profile.html").read_text(encoding="utf-8")


def test_parse_saved_profile():
    a = parse_profile_html(HTML)
    assert a["scholar_id"] == "AbCdEfGhIjKL"
    assert (a["name"], a["affiliation"], a["homepage"]) == ("Ada Lovelace", "University of London", "https://ada.example.org/")
    assert a["interests"] == ["Analytical engines", "Poetical science"]
    assert a["photo"] == ""  # 本地保存的图片路径不可用
    assert (a["citedby"], a["citedby5y"], a["hindex"], a["i10index5y"]) == (1234, 800, 3, 2)
    assert a["cites_per_year"] == {2022: 100, 2023: 0, 2024: 600}
    assert [p["citations"] for p in a["publications"]] == [1000, 200, 0]
    assert [p["year"] for p in a["publications"]] == [2020, 2022, None]
    assert a["publications"][0]["citation"] == "Nature 586 (7829), 378-382 , 2020"
    assert a["publications"][0]["url"].startswith("https://scholar.google.com/citations?view_op=view_citation")
    assert a["partial"] is False


def test_import_feeds_the_normal_report():
    r = build_report(parse_profile_html(HTML), NatureIndex(), source="import")
    assert r["source"] == "import" and r["partial"] is False
    assert r["totals"] == {"publications": 3, "nature_index": 1, "citations": 1200}
    assert r["nature_index"]["papers"][0]["journal"] == "Nature"


def test_partial_page_and_missing_id():
    page = HTML.replace(' disabled><span class="gs_wr">', '><span class="gs_wr">')
    assert parse_profile_html(page)["partial"] is True
    no_id = HTML.replace("AbCdEfGhIjKL", "x").replace("saved from url", "")
    assert parse_profile_html(no_id)["scholar_id"] is None
    with pytest.raises(ScholarError):
        parse_profile_html("<html><body>Sign in</body></html>")


class FakePG:
    calls = []

    def ScraperAPI(self, key):
        FakePG.calls.append(("scraperapi", key))
        return key == "good"

    def SingleProxy(self, http):
        FakePG.calls.append(("single", http))
        return True


class FakeScholarly:
    def __init__(self):
        self.used = None

    def use_proxy(self, pg1, pg2=None):
        self.used = (pg1, pg2)


@pytest.fixture()
def proxy_env(monkeypatch):
    monkeypatch.setattr("scholarly.ProxyGenerator", FakePG)
    monkeypatch.setattr(scholar, "_proxy_ready", False)
    monkeypatch.delenv("SCRAPERAPI_KEY", raising=False)
    monkeypatch.delenv("SCHOLAR_PROXY", raising=False)
    FakePG.calls = []
    return monkeypatch


def test_proxy_uses_same_generator_for_both_slots(proxy_env):
    proxy_env.setenv("SCHOLAR_PROXY", "http://user:pw@proxy.example:8080")
    s = FakeScholarly()
    scholar._setup_proxy(s)
    assert FakePG.calls == [("single", "http://user:pw@proxy.example:8080")]
    assert s.used[0] is s.used[1]  # 不让 scholarly 退回免费代理
    scholar._setup_proxy(s)
    assert len(FakePG.calls) == 1  # 只配置一次


def test_proxy_errors(proxy_env):
    proxy_env.setenv("SCRAPERAPI_KEY", "bad")
    with pytest.raises(ScholarError, match="proxy check failed"):
        scholar._setup_proxy(FakeScholarly())
    proxy_env.delenv("SCRAPERAPI_KEY")
    proxy_env.setenv("SCHOLAR_PROXY", "socks5://127.0.0.1:1080")
    with pytest.raises(ScholarError) as e:
        scholar._setup_proxy(FakeScholarly())
    assert e.value.code == "proxy_failed"


def test_no_proxy_configured(proxy_env):
    s = FakeScholarly()
    scholar._setup_proxy(s)
    assert s.used is None and scholar.proxy_mode() is None
