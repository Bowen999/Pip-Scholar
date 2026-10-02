"""OpenAlex 作者身份补充：每篇论文中本人的作者位置（first / middle / last）与是否通讯作者。

OpenAlex 自 2026 年起按调用计费：搜索 $0.001/次，列表+过滤 $0.0001/次；
无 key 每天 $0.10 免费额度，免费 key（openalex.org/settings/api）每天 $1。
所以先按作者 ID 批量拉取全部论文（便宜），只对剩下没匹配上的论文逐篇搜索标题（有次数上限）。
"""

import difflib
import logging
import os
import re
import unicodedata
from collections import defaultdict

import requests

API = "https://api.openalex.org"
WORK_FIELDS = "id,title,publication_year,authorships"
MAX_WORKS = 5000  # 批量拉取上限（每页 200 篇）
log = logging.getLogger("pip_scholar")
_TITLES = {"dr", "prof", "professor", "phd", "md", "jr", "sr", "msc", "mba"}


class QuotaExceeded(Exception):
    """OpenAlex 返回 429（当日额度用完），或本次报告的搜索次数达到上限。"""


def normalize_title(title):
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def clean_scholar_title(title):
    """去掉 Scholar 偶尔拼在书籍/章节标题尾部的作者，如 "... of carrot: A. Khadr et al."。"""
    return re.sub(r":\s*(?:[A-Z]\.?\s*)+[A-Z][\w\-]+(?:\s+et\s+al\.?)?$", "", title or "")


def name_tokens(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\([^)]*\)", " ", s)  # "Bowen Yang (杨博文)"
    return [t for t in re.sub(r"[^a-z ]+", " ", s).split() if t not in _TITLES]


def names_match(a, b, strict=False):
    """人名匹配。strict：全名一致，允许姓名顺序与空格不同（"Yang Bowen" / "Xiao-Ming Wang"）；
    否则再放宽到 姓 + 名首字母（"B. Yang"）。"""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    ja = "".join(ta)
    if ja in ("".join(tb), "".join(tb[1:] + tb[:1]), "".join(tb[-1:] + tb[:-1])):
        return True
    if strict:
        return False
    return (ta[-1] == tb[-1] and ta[0][0] == tb[0][0]) or (ta[0] == tb[-1] and ta[-1][0] == tb[0][0])


def _short_id(url):
    return (url or "").rsplit("/", 1)[-1]


def locate(work, name, author_ids=()):
    """在作者列表中定位本人 → (position, is_corresponding)；定位不到返回 (None, None)。"""
    auths = work.get("authorships") or []
    tests = (
        lambda a: _short_id((a.get("author") or {}).get("id")) in author_ids,
        lambda a: names_match(name, (a.get("author") or {}).get("display_name"), strict=True),
        lambda a: names_match(name, (a.get("author") or {}).get("display_name")),
    )
    for test in tests:
        for a in auths:
            if test(a):
                return a.get("author_position"), bool(a.get("is_corresponding"))
    return None, None


class Client:
    def __init__(self, api_key=None, max_searches=None, session=None, timeout=20):
        self.api_key = api_key or os.environ.get("OPENALEX_API_KEY") or None
        if max_searches is None:
            max_searches = int(os.environ.get("OPENALEX_MAX_SEARCHES", 300 if self.api_key else 30))
        self.max_searches = max_searches
        self.searches = 0
        self.session = session or requests.Session()
        self.timeout = timeout

    def get(self, path, params, billed_as_search=False):
        """billed_as_search：按"搜索"计费的调用，受 max_searches 限制。"""
        if billed_as_search:
            if self.searches >= self.max_searches:
                raise QuotaExceeded("search limit")
            self.searches += 1
        params = dict(params, api_key=self.api_key) if self.api_key else params
        r = self.session.get(f"{API}/{path}", params=params, timeout=self.timeout)
        if r.status_code == 429:
            raise QuotaExceeded("HTTP 429")
        r.raise_for_status()
        return r.json()

    def author_ids(self, name):
        """按姓名搜索作者（1 次搜索），保留姓名严格一致的候选（OpenAlex 常把同一人拆成多个 ID）。"""
        data = self.get("authors", {"search": name, "per-page": 25,
                                    "select": "id,display_name,display_name_alternatives"}, billed_as_search=True)
        ids = []
        for a in data.get("results", []):
            names = [a.get("display_name")] + (a.get("display_name_alternatives") or [])
            if any(names_match(name, n, strict=True) for n in names):
                ids.append(_short_id(a["id"]))
        return ids

    def works_by_authors(self, ids):
        works = []
        for i in range(0, len(ids), 50):
            cursor = "*"
            while cursor and len(works) < MAX_WORKS:
                data = self.get("works", {"filter": "author.id:" + "|".join(ids[i:i + 50]),
                                          "select": WORK_FIELDS, "per-page": 200, "cursor": cursor})
                works += data.get("results", [])
                cursor = data.get("meta", {}).get("next_cursor") if data.get("results") else None
        return works

    def search_title(self, title):
        """逐篇兜底：按标题搜索（计为搜索调用），相似度 >= 0.9 才算匹配。"""
        query = re.sub(r"[^\w\s]", " ", title).lower()
        data = self.get("works", {"search": query, "per-page": 5, "select": WORK_FIELDS}, billed_as_search=True)
        return TitleIndex(data.get("results", [])).find(title)


class TitleIndex:
    """按规范化标题精确查找，失败时在相邻年份内做相似度匹配。"""

    def __init__(self, works):
        self.exact, self.by_year = {}, defaultdict(list)
        for w in works:
            key = normalize_title(w.get("title"))
            if key:
                self.exact.setdefault(key, w)
                self.by_year[w.get("publication_year")].append((key, w))

    def find(self, title, year=None):
        key = normalize_title(clean_scholar_title(title))
        if not key:
            return None
        if key in self.exact:
            return self.exact[key]
        if year:
            pool = [kw for y in (year - 1, year, year + 1) for kw in self.by_year.get(y, [])]
        else:
            pool = [kw for kws in self.by_year.values() for kw in kws]
        best, best_sim = None, 0.9
        for k, w in pool:
            sm = difflib.SequenceMatcher(None, k, key)
            if sm.quick_ratio() >= best_sim and (sim := sm.ratio()) >= best_sim:
                best, best_sim = w, sim
        return best


def enrich(pubs, name, client=None, progress=None):
    """为每篇论文写入 position / corresponding（原地修改）。

    position: first / middle / last；"unknown" = 匹配到论文但没定位到本人；None = 没匹配到。
    返回 {"status": ok | limited | error, "matched": 匹配篇数}。
    """
    client = client or Client()
    progress = progress or (lambda *a, **k: None)
    for p in pubs:
        p["position"], p["corresponding"] = None, None

    def apply(p, work, ids=()):
        pos, corr = locate(work, name, ids)
        p["position"], p["corresponding"] = pos or "unknown", corr

    status = "ok"
    try:
        ids = client.author_ids(name)
        index = TitleIndex(client.works_by_authors(ids) if ids else [])
        pending = []
        for p in pubs:
            work = index.find(p["title"], p.get("year"))
            if work:
                apply(p, work, set(ids))
            else:
                pending.append(p)
        done = len(pubs) - len(pending)
        for i, p in enumerate(pending):
            progress("openalex", done + i, len(pubs))
            work = client.search_title(p["title"]) if p["title"] else None
            if work:
                apply(p, work)
    except QuotaExceeded:
        status = "limited"
    except Exception:  # noqa: BLE001 —— 作者身份只是补充信息，OpenAlex 出任何问题都不能让整份报告失败
        log.exception("OpenAlex enrichment failed")
        status = "error"
    return {"status": status, "matched": sum(p["position"] is not None for p in pubs)}
