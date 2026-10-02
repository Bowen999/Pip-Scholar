"""汇总报告：Nature Index 匹配 + 作者身份 + 6 个维度统计 + 图表数据（JSON，直接交给前端）。"""

import csv
import datetime
import io
from collections import Counter

from .nature_index import normalize_journal, parse_venue
from .scholar import profile_url

# 作者身份维度。position / corresponding 来自 OpenAlex；共同一作不可见，"一作"即作者列表第一位。
ROLES = {
    "all": lambda p: True,
    "first_corr": lambda p: p["position"] == "first" or p["corresponding"] is True,
    "first_lastcorr": lambda p: p["position"] == "first"
    or (p["corresponding"] is True and p["position"] == "last"),
}
POSITIONS = ("first", "middle", "last", "unknown", "unmatched")
PUB_FIELDS = ("title", "year", "venue", "citations", "nature_index", "ni_journal",
              "position", "corresponding", "first_corr", "first_lastcorr", "url")


def h_index(cites):
    return sum(1 for i, c in enumerate(sorted(cites, reverse=True), 1) if c >= i)


def subset_stats(pubs):
    """一个论文子集的统计；引用数是子集论文在 Scholar 上的单篇被引之和。"""
    cites = [p["citations"] for p in pubs]
    return {
        "papers": len(pubs),
        "citations": sum(cites),
        "h_index": h_index(cites),
        "i10_index": sum(c >= 10 for c in cites),
        "nature_index": sum(p["nature_index"] for p in pubs),
    }


def build_report(author, ni, enrich=None, progress=None, today=None, demo=False, source="scholar"):
    """author: scholar.fetch_author() 或 scholar_html.parse_profile_html() 的结果；
    enrich(pubs, name, progress): 作者身份补充（可选）；source: scholar | import | demo。"""
    progress = progress or (lambda *a, **k: None)
    today = today or datetime.date.today()
    since = today.year - 5  # 与 Google Scholar "Since 20xx" 口径一致

    progress("nature_index")
    pubs, near_misses = [], {}
    for raw in author["publications"]:
        venue = parse_venue(raw["citation"])
        hit = ni.match(venue) if venue else None
        if venue and not hit and (official := ni.near_miss(venue)):
            near_misses.setdefault(venue, official)
        pubs.append({
            "title": raw["title"], "year": raw["year"], "venue": venue,
            "citations": raw["citations"] or 0, "url": raw.get("url", ""),
            "nature_index": bool(hit), "ni_journal": hit[0] if hit else "",
            "ni_categories": hit[1] if hit else [], "position": None, "corresponding": None,
        })

    authorship = {"enabled": bool(enrich), "status": "disabled", "matched": 0}
    if enrich:
        progress("openalex", 0, len(pubs))
        authorship.update(enrich(pubs, author["name"], progress))

    progress("stats")
    for p in pubs:
        p["first_corr"] = ROLES["first_corr"](p)
        p["first_lastcorr"] = ROLES["first_lastcorr"](p)
    pubs.sort(key=lambda p: (-p["citations"], -(p["year"] or 0)))
    positions = Counter(p["position"] or "unmatched" for p in pubs)
    authorship["positions"] = {k: positions.get(k, 0) for k in POSITIONS}
    authorship["corresponding"] = sum(p["corresponding"] is True for p in pubs)

    dimensions = []
    for role, keep in ROLES.items():
        subset = [p for p in pubs if keep(p)]
        dimensions.append({"role": role, "period": "all", **subset_stats(subset)})
        recent = [p for p in subset if (p["year"] or 0) >= since]
        dimensions.append({"role": role, "period": "recent", **subset_stats(recent)})

    ni_pubs = sorted((p for p in pubs if p["nature_index"]),
                     key=lambda p: (-(p["year"] or 0), -p["citations"]))
    categories = Counter(c for p in ni_pubs for c in p["ni_categories"])

    return {
        "version": 1,
        "scholar_id": author["scholar_id"],
        "demo": demo,
        "source": "demo" if demo else source,
        "partial": bool(author.get("partial")),  # 导入的网页没有展开全部论文
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "recent_since": since,
        "profile": {
            "name": author["name"], "affiliation": author["affiliation"],
            "interests": author["interests"], "homepage": author["homepage"], "photo": author["photo"],
            "url": "" if demo else profile_url(author["scholar_id"]),
        },
        "official": {  # Google Scholar 主页上的官方值
            "citations": {"all": author["citedby"], "recent": author["citedby5y"]},
            "h_index": {"all": author["hindex"], "recent": author["hindex5y"]},
            "i10_index": {"all": author["i10index"], "recent": author["i10index5y"]},
        },
        "totals": {"publications": len(pubs), "nature_index": len(ni_pubs),
                   "citations": sum(p["citations"] for p in pubs)},
        "authorship": authorship,
        "dimensions": dimensions,
        "citations_per_year": _citations_per_year(author["cites_per_year"]),
        "publications_per_year": _publications_per_year(pubs, today.year),
        "nature_index": {
            "papers": [{"title": p["title"], "year": p["year"], "journal": p["ni_journal"],
                        "citations": p["citations"], "categories": p["ni_categories"], "url": p["url"]}
                       for p in ni_pubs],
            "categories": [{"name": c, "count": n} for c, n in categories.most_common()],
            "near_misses": [{"venue": v, "journal": j} for v, j in near_misses.items()],
        },
        "venues": _top_venues(pubs),
        "publications": [{k: p[k] for k in PUB_FIELDS} for p in pubs],
    }


def _citations_per_year(cites_per_year):
    if not cites_per_year:
        return []
    years = range(min(cites_per_year), max(cites_per_year) + 1)
    return [{"year": y, "citations": cites_per_year.get(y, 0)} for y in years]


def _publications_per_year(pubs, this_year):
    dated = [p for p in pubs if p["year"] and 1950 <= p["year"] <= this_year + 1]
    if not dated:
        return []
    total = Counter(p["year"] for p in dated)
    ni = Counter(p["year"] for p in dated if p["nature_index"])
    return [{"year": y, "total": total[y], "nature_index": ni[y]}
            for y in range(min(total), max(total) + 1)]


def _top_venues(pubs, n=10):
    counts, names, is_ni = Counter(), {}, {}
    for p in pubs:
        if p["venue"]:
            key = p["ni_journal"] or normalize_journal(p["venue"])  # NI 别名合并到官方刊名
            counts[key] += 1
            names.setdefault(key, p["ni_journal"] or p["venue"])
            is_ni[key] = p["nature_index"]
    return [{"name": names[k], "count": c, "nature_index": is_ni[k]} for k, c in counts.most_common(n)]


def to_csv(report):
    """论文明细 CSV（带 BOM，Excel 打开中文不乱码）。"""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PUB_FIELDS)
    writer.writeheader()
    writer.writerows(report["publications"])
    return "﻿" + buf.getvalue()
