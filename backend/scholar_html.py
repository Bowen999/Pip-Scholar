"""解析用户在浏览器里保存的 Google Scholar 主页（.html），完全绕开限流。

输出与 scholar.fetch_author() 相同的 dict，另加 partial：论文列表没有展开完（"显示更多"按钮仍可点）。
"""

import re
from collections import Counter
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .scholar import ScholarError, parse_scholar_id

BASE = "https://scholar.google.com"


def _text(el):
    return el.get_text(" ", strip=True) if el else ""


def _num(text):
    digits = re.sub(r"\D", "", text or "")  # 去掉千分位与合并标记 "*"
    return int(digits) if digits else 0


def _scholar_id(html):
    """论文链接 citation_for_view=<ID>:xxxx 的前缀就是本人 ID；其次看页面地址。"""
    ids = Counter(re.findall(r"citation_for_view=([\w-]{12}):", html))
    if ids:
        return ids.most_common(1)[0][0]
    m = re.search(r"saved from url=\(\d+\)(\S+)", html) or re.search(r'rel="canonical" href="([^"]+)"', html)
    return parse_scholar_id(m.group(1).replace("&amp;", "&")) if m else None


def parse_profile_html(html):
    soup = BeautifulSoup(html, "html.parser")
    name = _text(soup.find(id="gsc_prf_in"))
    if not name:
        raise ScholarError("import_invalid", "not a Google Scholar profile page")

    lines = soup.find_all("div", class_="gsc_prf_il")
    homepage = soup.select_one("#gsc_prf_ivh a")
    photo = soup.find(id="gsc_prf_pup-img")
    stats = [_num(_text(td)) for td in soup.find_all("td", class_="gsc_rsb_std")] + [0] * 6

    # 每年被引柱图：年份按顺序排列；柱子用 z-index 倒序对应年份（与 scholarly 相同）
    years = [int(_text(y)) for y in soup.find_all("span", class_="gsc_g_t") if _text(y).isdigit()]
    cites = [0] * len(years)
    for a in soup.find_all("a", class_="gsc_g_a"):
        z = re.search(r"z-index:\s*(\d+)", a.get("style", ""))
        if z and 0 < int(z.group(1)) <= len(cites):
            cites[-int(z.group(1))] = _num(_text(a.find("span", class_="gsc_g_al")))

    pubs = []
    for row in soup.find_all("tr", class_="gsc_a_tr"):
        link = row.find("a", class_="gsc_a_at")
        if not link:
            continue
        gray = row.find_all("div", class_="gs_gray")
        year = _text(row.find("span", class_="gsc_a_h"))
        href = link.get("href") or link.get("data-href") or ""
        pubs.append({
            "title": _text(link),
            "year": int(year) if year.isdigit() else None,
            "citation": _text(gray[1]) if len(gray) > 1 else "",
            "citations": _num(_text(row.find("a", class_="gsc_a_ac"))),
            "url": urljoin(BASE, href) if "citation_for_view" in href else "",
        })

    more = soup.find(id="gsc_bpf_more")
    return {
        "scholar_id": _scholar_id(html),
        "name": name,
        "affiliation": _text(lines[0]) if lines else "",
        "interests": [_text(a) for a in soup.find_all("a", class_="gsc_prf_inta")],
        "homepage": homepage.get("href", "") if homepage else "",
        "photo": photo.get("src", "") if photo and photo.get("src", "").startswith("http") else "",
        "citedby": stats[0], "citedby5y": stats[1], "hindex": stats[2],
        "hindex5y": stats[3], "i10index": stats[4], "i10index5y": stats[5],
        "cites_per_year": dict(zip(years, cites)),
        "publications": pubs,
        "partial": bool(more and not more.has_attr("disabled")),
    }
