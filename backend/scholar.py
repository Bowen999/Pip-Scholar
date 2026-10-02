"""Google Scholar 抓取（基于 scholarly），输出与 scholarly 解耦的普通 dict。

被限流时可走代理：SCRAPERAPI_KEY（付费服务，自动换 IP）或 SCHOLAR_PROXY=http://user:pass@host:port。
"""

import os
import re
import threading

_lock = threading.Lock()  # scholarly 有全局状态；串行抓取，也降低被限流的概率
_proxy_ready = False


class ScholarError(Exception):
    """抓取失败。code 交给前端做中英文提示。"""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code


def parse_scholar_id(text):
    """从 Scholar 主页链接或裸 ID 中提取 12 位 ID；无法识别时返回 None。"""
    text = (text or "").strip()
    m = re.search(r"[?&]user=([\w-]{12})(?![\w-])", text)
    if m:
        return m.group(1)
    return text if re.fullmatch(r"[\w-]{12}", text) else None


def profile_url(scholar_id):
    return f"https://scholar.google.com/citations?user={scholar_id}"


def proxy_mode():
    if os.environ.get("SCRAPERAPI_KEY"):
        return "scraperapi"
    return "proxy" if os.environ.get("SCHOLAR_PROXY") else None


def _setup_proxy(scholarly):
    """按环境变量配置代理，进程内只做一次。"""
    global _proxy_ready
    if _proxy_ready or not proxy_mode():
        return
    from scholarly import ProxyGenerator

    key, url = os.environ.get("SCRAPERAPI_KEY"), os.environ.get("SCHOLAR_PROXY")
    if not key and not re.match(r"https?://", url):
        raise ScholarError("proxy_failed", "SCHOLAR_PROXY must be an http:// or https:// proxy URL")
    pg = ProxyGenerator()
    try:
        ok = pg.ScraperAPI(key) if key else pg.SingleProxy(http=url)
    except Exception as e:  # noqa: BLE001 —— 账号或网络问题都归为代理不可用
        raise ScholarError("proxy_failed", f"{type(e).__name__}: {e}") from e
    if not ok:
        raise ScholarError("proxy_failed", "proxy check failed")
    # 主、次都用同一个代理：只传一个时，scholarly 会把主页请求交给免费代理
    scholarly.use_proxy(pg, pg)
    _proxy_ready = True


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_author(scholar_id):
    """抓取主页指标、每年被引与全部论文。"""
    try:
        from scholarly import scholarly
        from scholarly._proxy_generator import MaxTriesExceededException
    except ImportError as e:
        raise ScholarError("scholarly_missing", str(e)) from e

    with _lock:
        _setup_proxy(scholarly)
        try:
            author = scholarly.search_author_id(scholar_id)
            author = scholarly.fill(author, sections=["basics", "indices", "counts", "publications"])
        except MaxTriesExceededException as e:
            # 验证码 / 限流，或 ID 不存在（Scholar 对不存在的 ID 也会反复失败）
            raise ScholarError("scholar_unavailable", str(e)) from e
        except Exception as e:
            raise ScholarError("scholar_failed", f"{type(e).__name__}: {e}") from e

    pubs = []
    for p in author.get("publications", []):
        bib = p.get("bib", {})
        pid = p.get("author_pub_id")
        pubs.append({
            "title": bib.get("title", ""),
            "year": _int(bib.get("pub_year")),
            "citation": bib.get("citation", ""),
            "citations": p.get("num_citations") or 0,
            "url": ("https://scholar.google.com/citations?view_op=view_citation"
                    f"&citation_for_view={pid}") if pid else "",
        })
    return {
        "scholar_id": scholar_id,
        "name": author.get("name", ""),
        "affiliation": author.get("affiliation", ""),
        "interests": author.get("interests", []),
        "homepage": author.get("homepage", ""),
        "photo": author.get("url_picture", ""),
        "citedby": author.get("citedby", 0),
        "citedby5y": author.get("citedby5y", 0),
        "hindex": author.get("hindex", 0),
        "hindex5y": author.get("hindex5y", 0),
        "i10index": author.get("i10index", 0),
        "i10index5y": author.get("i10index5y", 0),
        "cites_per_year": {int(y): int(c) for y, c in author.get("cites_per_year", {}).items()},
        "publications": pubs,
    }
