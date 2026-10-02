"""离线演示：虚构学者 "Demo Scholar"。走与真实数据相同的统计流程，不联网，用于试用和前端开发。"""

import datetime
import math
import random
import time
from collections import Counter

from .report import build_report, h_index

DEMO_ID = "demo"

# (引用串模板, 抽样权重, 被引系数)
NEAR_MISS = ("Nature communication {v} (1), {p}", 0.6, 1.0)  # 故意写错，演示"近似但未计入"提示
VENUES = [
    ("Nature {v} ({i}), {p}-{q}", 0.3, 3.0),
    ("Nature Communications {v} (1), {p}", 1.5, 1.8),
    ("Science Advances {v} ({i}), eabc{p}", 1, 1.6),
    ("Proceedings of the National Academy of Sciences {v} ({i}), e{p}", 1, 1.5),
    ("Journal of the American Chemical Society {v} ({i}), {p}-{q}", 1, 1.4),
    ("Advanced Materials {v} ({i}), {p}", 1, 1.5),
    ("Nano Letters {v} ({i}), {p}-{q}", 1, 1.2),
    ("Physical Review Letters {v} ({i}), {p}", 0.5, 1.3),
    NEAR_MISS,
    ("Scientific Reports {v} (1), {p}", 5, 0.7),
    ("ACS Applied Materials & Interfaces {v} ({i}), {p}-{q}", 5, 0.8),
    ("Journal of Materials Chemistry A {v} ({i}), {p}-{q}", 3, 0.9),
    ("Chemical Engineering Journal {v}, {p}", 3, 0.8),
    ("Physical Chemistry Chemical Physics {v} ({i}), {p}-{q}", 4, 0.6),
    ("Journal of Applied Physics {v} ({i}), {p}", 3, 0.5),
    ("Advances in Neural Information Processing Systems {v}, {p}-{q}", 2, 1.2),
    ("arXiv preprint arXiv:{a}.{b}", 4, 0.4),
]
ADJ = ["Scalable", "Robust", "Interpretable", "Self-supervised", "Ultrafast", "Programmable",
       "High-throughput", "Adaptive", "Low-cost", "Atomically precise", "Data-driven", "Bioinspired"]
NOUNS = ["graph learning", "spectroscopy", "synthesis", "charge transport", "inverse design",
         "operando imaging", "sensing", "multiscale modelling", "self-assembly", "Bayesian inference",
         "electrocatalysis", "phase engineering"]
TOPICS = ["catalyst discovery", "perovskite solar cells", "solid-state batteries", "quantum materials",
          "single-atom catalysts", "2D semiconductors", "CO2 reduction", "porous frameworks",
          "protein design", "soft robotics", "water splitting", "thermal transport"]


def make_author(today=None, n=72):
    today = today or datetime.date.today()
    since = today.year - 5
    elapsed = today.timetuple().tm_yday / 365
    rng = random.Random(2026)
    pubs, cites_per_year, recent_cites, titles = [], Counter(), [], set()
    for i in range(n):
        year = today.year - int(rng.triangular(0, 14.99, 3))  # 近年发表更多
        template, _, impact = rng.choices(VENUES, [w for _, w, _ in VENUES])[0]
        if i == 3:
            template, _, impact = NEAR_MISS
        title = None
        while not title or title in titles:
            title = rng.choice(["{} {} for {}", "{} {} of {}", "{} {} in {}"]).format(
                rng.choice(ADJ), rng.choice(NOUNS), rng.choice(TOPICS))
        titles.add(title)
        age = today.year - year + 0.5
        cites = int(rng.lognormvariate(1.0 + 0.4 * min(age, 8), 0.9) * impact)
        p = rng.randint(100, 9999)
        citation = template.format(v=rng.randint(10, 140), i=rng.randint(1, 24), p=p, q=p + rng.randint(3, 15),
                                   a=f"{year % 100:02d}{rng.randint(1, 12):02d}", b=f"{rng.randint(0, 99999):05d}")
        # 把单篇被引分摊到发表后的各年（约第 4 年达到峰值后缓慢回落；当年只算已过去的部分），汇总成每年被引
        years = list(range(year, today.year + 1))
        weights = [(y - year + 1) * math.exp(-(y - year + 1) / 4) * (elapsed if y == today.year else 1) for y in years]
        spread = Counter(rng.choices(years, weights, k=cites)) if cites else Counter()
        cites_per_year.update(spread)
        recent_cites.append(sum(c for y, c in spread.items() if y >= since))
        pubs.append({"title": title, "year": year, "citation": f"{citation}, {year}", "citations": cites, "url": ""})

    all_cites = [p["citations"] for p in pubs]
    return {
        "scholar_id": DEMO_ID,
        "name": "Demo Scholar",
        "affiliation": "Pip-Scholar Example University (fictional)",
        "interests": ["Materials informatics", "Catalysis", "Machine learning"],
        "homepage": "",
        "photo": "",
        "citedby": sum(all_cites),
        "citedby5y": sum(c for y, c in cites_per_year.items() if y >= since),
        "hindex": h_index(all_cites),
        "hindex5y": h_index(recent_cites),
        "i10index": sum(c >= 10 for c in all_cites),
        "i10index5y": sum(c >= 10 for c in recent_cites),
        "cites_per_year": dict(cites_per_year),
        "publications": pubs,
    }


def _fake_enrich(pubs, progress, delay):
    """模拟 OpenAlex：约 8% 未匹配，其余随机分配作者位置与通讯作者。"""
    rng = random.Random(7)
    for i, p in enumerate(pubs):
        if i % 8 == 0:
            progress("openalex", i, len(pubs))
            time.sleep(delay)
        if rng.random() < 0.08:
            continue
        pos = rng.choices(["first", "middle", "last", "unknown"], [38, 30, 28, 4])[0]
        p["position"] = pos
        p["corresponding"] = None if pos == "unknown" else rng.random() < {"first": .35, "middle": .12, "last": .7}[pos]
    return {"status": "ok", "matched": sum(p["position"] is not None for p in pubs)}


def build(ni, progress, openalex=True, delay=0.25):
    progress("scholar")
    time.sleep(delay * 4)
    enrich = (lambda pubs, name, prog: _fake_enrich(pubs, prog, delay)) if openalex else None
    return build_report(make_author(), ni, enrich=enrich, progress=progress, demo=True)
