import datetime

import pytest
import requests

from backend import demo
from backend.nature_index import ALIASES, NatureIndex, parse_venue
from backend.openalex import Client, QuotaExceeded, TitleIndex, enrich, locate, names_match
from backend.report import build_report, h_index
from backend.scholar import parse_scholar_id

NI = NatureIndex()


@pytest.mark.parametrize("text, expected", [
    ("https://scholar.google.ca/citations?user=A4H2UV8AAAAJ&hl=en", "A4H2UV8AAAAJ"),
    ("https://scholar.google.com/citations?hl=zh-CN&user=A4H2UV8AAAAJ", "A4H2UV8AAAAJ"),
    ("  A4H2UV8AAAAJ ", "A4H2UV8AAAAJ"),
    ("abc", None),
    ("https://scholar.google.com/citations?user=A4H2UV8AAAAJXX", None),
])
def test_parse_scholar_id(text, expected):
    assert parse_scholar_id(text) == expected


@pytest.mark.parametrize("citation, venue", [
    ("Nature communications 15 (1), 4295, 2024", "Nature communications"),
    ("Physical Review B 101 (5), 054101, 2020", "Physical Review B"),
    ("Advances in neural information processing systems 33, 1877-1901, 2020",
     "Advances in neural information processing systems"),
    ("Proceedings of the IEEE/CVF conference on computer vision and pattern recognition, 770-778, 2016",
     "Proceedings of the IEEE/CVF conference on computer vision and pattern recognition"),
    ("2020 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS), 5678-5684, 2020",
     "IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)"),
    ("arXiv preprint arXiv:2401.12345, 2024", "arXiv preprint"),
    ("Journal of Hepatology 72 (2), 2020", "Journal of Hepatology"),
    ("", ""),
])
def test_parse_venue(citation, venue):
    assert parse_venue(citation) == venue


def test_nature_index_matching():
    assert len(NI) == 178
    assert all(official in NI.journals for official in ALIASES.values())
    assert NI.match("Nature communications")[0] == "Nature Communications"
    assert NI.match("PNAS")[0].startswith("Proceedings of the National Academy of Sciences")
    assert NI.match("Environmental Science & Technology")[0] == "Environmental Science and Technology"
    assert NI.match("Jama")[0] == "JAMA: The Journal of the American Medical Association"
    assert NI.match("IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)")
    assert NI.match("Scientific Reports") is None
    assert NI.match("Nature communication") is None
    assert NI.near_miss("Nature communication") == "Nature Communications"
    assert "Physical sciences" in NI.match("Nature")[1]


def test_names_match():
    assert names_match("Bowen Yang", "Yang Bowen", strict=True)
    assert names_match("Xiao-Ming Wang", "Xiaoming Wang", strict=True)
    assert names_match("Xiaoming Wang", "Wang Xiaoming", strict=True)
    assert names_match("José García", "Jose Garcia", strict=True)
    assert names_match("Bowen Yang (杨博文)", "Bowen Yang", strict=True)
    assert not names_match("Bowen Yang", "B. Yang", strict=True)
    assert names_match("Bowen Yang", "B. Yang")
    assert names_match("John A. Smith", "John Smith")
    assert not names_match("Bowen Yang", "Bin Li")


def _work(title, year, authors):
    return {"title": title, "publication_year": year, "authorships": [
        {"author": {"id": f"https://openalex.org/{aid}", "display_name": name},
         "author_position": pos, "is_corresponding": corr} for aid, name, pos, corr in authors]}


def test_locate_prefers_author_id_then_full_name():
    work = _work("T", 2020, [("A1", "B. Yang", "first", False), ("A2", "Bowen Yang", "last", True)])
    assert locate(work, "Bowen Yang", {"A2"}) == ("last", True)
    assert locate(work, "Bowen Yang") == ("last", True)
    assert locate(work, "Ann Lee") == (None, None)


def test_title_index():
    idx = TitleIndex([_work("Deep Residual Learning for Image Recognition", 2016, [])])
    assert idx.find("Deep residual learning for image recognition", 2016)
    assert idx.find("Deep residual learning for image recognitions", 2017)
    assert idx.find("Something else entirely", 2016) is None


class FakeClient:
    def __init__(self, works, hits, quota_after=None):
        self.works, self.hits, self.quota_after, self.searches = works, hits, quota_after, 0

    def author_ids(self, name):
        return ["A1"]

    def works_by_authors(self, ids):
        return self.works

    def search_title(self, title):
        if self.quota_after is not None and self.searches >= self.quota_after:
            raise QuotaExceeded()
        self.searches += 1
        return self.hits.get(title)


def _pubs():
    return [{"title": "Paper One", "year": 2020}, {"title": "Paper Two", "year": 2021},
            {"title": "Paper Three", "year": 2022}]


def test_enrich_bulk_then_title_search():
    works = [_work("Paper One", 2020, [("A1", "Ada Lovelace", "first", True)])]
    hits = {"Paper Two": _work("Paper Two", 2021, [("A9", "Someone Else", "first", False),
                                                    ("A7", "Ada Lovelace", "last", True)])}
    pubs = _pubs()
    assert enrich(pubs, "Ada Lovelace", FakeClient(works, hits)) == {"status": "ok", "matched": 2}
    assert [p["position"] for p in pubs] == ["first", "last", None]
    assert [p["corresponding"] for p in pubs] == [True, True, None]


def test_enrich_stops_when_quota_is_exhausted():
    works = [_work("Paper One", 2020, [("A1", "Ada Lovelace", "middle", False)])]
    pubs = _pubs()
    assert enrich(pubs, "Ada Lovelace", FakeClient(works, {}, quota_after=0)) == {"status": "limited", "matched": 1}


def test_h_index():
    assert h_index([]) == 0
    assert h_index([10, 8, 5, 4, 3]) == 4
    assert h_index([25, 8, 5, 3, 3]) == 3


def test_build_report_dimensions():
    author = {
        "scholar_id": "A4H2UV8AAAAJ", "name": "Ada Lovelace", "affiliation": "", "interests": [],
        "homepage": "", "photo": "", "citedby": 0, "citedby5y": 0, "hindex": 0, "hindex5y": 0,
        "i10index": 0, "i10index5y": 0, "cites_per_year": {2019: 3, 2021: 5},
        "publications": [
            {"title": "A", "year": 2018, "citation": "Nature 1 (1), 1-2, 2018", "citations": 40},
            {"title": "B", "year": 2023, "citation": "Scientific Reports 1 (1), 1, 2023", "citations": 12},
            {"title": "C", "year": 2024, "citation": "Physical Review Letters 1 (1), 1, 2024", "citations": 3},
            {"title": "D", "year": None, "citation": "", "citations": 0},
        ],
    }
    roles = {"A": ("first", False), "B": ("last", True), "C": ("middle", True), "D": (None, None)}

    def fake_enrich(pubs, name, progress):
        for p in pubs:
            p["position"], p["corresponding"] = roles[p["title"]]
        return {"status": "ok", "matched": 3}

    r = build_report(author, NI, enrich=fake_enrich, today=datetime.date(2026, 6, 1))
    dims = {(d["role"], d["period"]): d for d in r["dimensions"]}
    assert dims["all", "all"] == {"role": "all", "period": "all", "papers": 4, "citations": 55,
                                  "h_index": 3, "i10_index": 2, "nature_index": 2}
    assert dims["all", "recent"]["papers"] == 2  # 2021 年起：B、C
    assert dims["first_corr", "all"]["papers"] == 3  # A 一作，B、C 通讯
    assert dims["first_lastcorr", "all"]["papers"] == 2  # A 一作，B 末位通讯
    assert r["authorship"]["positions"] == {"first": 1, "middle": 1, "last": 1, "unknown": 0, "unmatched": 1}
    assert r["citations_per_year"] == [{"year": 2019, "citations": 3}, {"year": 2020, "citations": 0},
                                       {"year": 2021, "citations": 5}]
    assert [y["year"] for y in r["publications_per_year"]] == list(range(2018, 2025))
    assert [p["journal"] for p in r["nature_index"]["papers"]] == ["Physical Review Letters", "Nature"]


def test_demo_report_is_consistent():
    r = demo.build(NI, lambda *a, **k: None, delay=0)
    assert len(r["dimensions"]) == 6 and r["demo"] is True
    assert r["dimensions"][0]["papers"] == r["totals"]["publications"] == len(r["publications"])
    assert sum(y["total"] for y in r["publications_per_year"]) == len(r["publications"])
    assert r["nature_index"]["near_misses"] == [{"venue": "Nature communication", "journal": "Nature Communications"}]


class FakeResponse:
    def __init__(self, status, data=None):
        self.status_code, self.data = status, data or {}

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    """按 (路径, 是否带 search, cursor) 返回预设响应，并记录请求参数。"""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, params, timeout):
        self.calls.append((url.rsplit("/", 1)[-1], dict(params)))
        return self.routes(url.rsplit("/", 1)[-1], params)


def test_client_bulk_fetch_and_quota():
    works_page = {"results": [_work("Paper One", 2020, [("A1", "Ada Lovelace", "last", True)])],
                  "meta": {"next_cursor": "c2"}}

    def routes(path, params):
        if path == "authors":
            return FakeResponse(200, {"results": [
                {"id": "https://openalex.org/A1", "display_name": "Ada Lovelace"},
                {"id": "https://openalex.org/A2", "display_name": "A. Lovelace"},  # 非严格同名，不纳入
                {"id": "https://openalex.org/A3", "display_name": "Lovelace Ada"}]})
        if "filter" in params:
            return FakeResponse(200, works_page if params["cursor"] == "*" else {"results": [], "meta": {}})
        return FakeResponse(429)  # 逐篇搜索时额度用完

    session = FakeSession(routes)
    client = Client(api_key="KEY", max_searches=5, session=session)
    pubs = _pubs()
    assert enrich(pubs, "Ada Lovelace", client) == {"status": "limited", "matched": 1}
    assert pubs[0]["position"] == "last" and pubs[0]["corresponding"] is True
    paths = [c[0] for c in session.calls]
    assert paths == ["authors", "works", "works", "works"]  # 作者搜索 → 两页批量 → 一次标题搜索（429）
    assert session.calls[1][1]["filter"] == "author.id:A1|A3"
    assert all(c[1]["api_key"] == "KEY" for c in session.calls)


def test_client_search_budget():
    client = Client(max_searches=1, session=FakeSession(lambda path, params: FakeResponse(200, {"results": []})))
    client.search_title("A title")
    with pytest.raises(QuotaExceeded):
        client.search_title("Another title")
