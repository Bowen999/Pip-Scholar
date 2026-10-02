"""Nature Index 期刊名单与刊名匹配。"""

import csv
import difflib
import re
from pathlib import Path

CSV_PATH = Path(__file__).parent / "data" / "nature_index_journals.csv"

# Scholar 引用串里的常见写法 → Nature Index 官方刊名（两侧都会先经 normalize_journal 规范化）
ALIASES = {
    "proceedings of the national academy of sciences":
        "proceedings of the national academy of sciences of the united states of america",
    "pnas": "proceedings of the national academy of sciences of the united states of america",
    "jama": "jama the journal of the american medical association",
    "journal of the american medical association": "jama the journal of the american medical association",
    "isme journal": "isme journal multidisciplinary journal of microbial ecology",
    "proceedings of the royal society b biological sciences": "proceedings of the royal society b",
}


def normalize_journal(name):
    """小写、去标点、& → and、去掉开头的 the、压缩空格。"""
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[4:] if s.startswith("the ") else s


def parse_venue(citation):
    """从 Scholar 列表的引用串解析刊名。

    "Nature communications 15 (1), 4295, 2024"            → "Nature communications"
    "2020 IEEE/RSJ International Conference ..., 1-8, 2020" → "IEEE/RSJ International Conference ..."
    "arXiv preprint arXiv:2401.12345, 2024"               → "arXiv preprint"
    """
    s = (citation or "").strip()
    s = re.sub(r",\s*\d{4}\s*$", "", s)                      # 结尾年份
    s = re.sub(r"\s*arXiv:\S+", "", s)                         # arXiv 编号
    s = re.sub(r"^(?:19|20)\d{2}\s+", "", s)                   # 会议名前的年份
    m = re.match(r"^(.*?)\s+\d+\s*(?:\([^)]*\))?\s*,", s)      # "刊名 卷 (期), 页码"
    if m:
        s = m.group(1)
    else:
        s = re.sub(r",\s*[A-Za-z]?[\d\-–]+[A-Za-z]?\s*$", "", s)   # "刊名, 页码"
        s = re.sub(r"(?<=[A-Za-z])\s+\d+\s*(?:\([^)]*\))?$", "", s)  # "刊名 卷 (期)"
    return s.strip(" ,.")


class NatureIndex:
    """加载期刊名单；match() 精确匹配，near_miss() 给出可能因写法不同而漏判的近似刊名。"""

    def __init__(self, path=CSV_PATH):
        self.journals = {}  # 规范化刊名 → (官方刊名, [学科])
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row["journal"].strip()
                cats = [c.strip() for c in row.get("category", "").split(";") if c.strip()]
                self.journals[normalize_journal(name)] = (name, cats)
        for alias, official in ALIASES.items():
            if official in self.journals:
                self.journals[alias] = self.journals[official]

    def __len__(self):
        return len({v[0] for v in self.journals.values()})

    def match(self, venue):
        return self.journals.get(normalize_journal(venue))

    def near_miss(self, venue, cutoff=0.88):
        close = difflib.get_close_matches(normalize_journal(venue), self.journals, n=1, cutoff=cutoff)
        return self.journals[close[0]][0] if close else None
