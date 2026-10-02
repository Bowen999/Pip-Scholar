"""Google Scholar 个人学术报告 + Nature Index 论文统计 + CitationMap。

用法:
    python3 scholar_report.py <Google Scholar 链接或 ID> [--map] [--no-openalex]

示例:
    python3 scholar_report.py "https://scholar.google.ca/citations?user=A4H2UV8AAAAJ&hl=en"
    python3 scholar_report.py A4H2UV8AAAAJ --map   # 需要引用地图时加 --map（默认关闭）

输出（全部保存在 output_<scholar_id>/ 目录下）:
    - 终端汇总: 论文数量、引用数量、h-index、i10-index、Nature Index 论文数量，
      按 2 个时间维度（全部 / 近5年）x 3 个作者身份维度（全部作者 / 一作+通讯 /
      第一位一作+末位通讯）共 6 个维度统计
    - publications.csv: 全部论文明细（含 Nature Index 标记、作者位置、是否通讯）
    - citation_map.html / citation_info.csv: 引用地图（来自 citation-map 包）

说明:
    - 作者身份（作者位置、通讯作者）来自 OpenAlex（出版社上报数据），
      Google Scholar 本身不提供这些信息；通讯作者覆盖不全，统计为下限。
    - 共同第一作者在 OpenAlex 中不可见，"一作"按作者列表第一位认定。
    - "近5年"按论文发表年份 >= 当年-5（与 Google Scholar "Since 20xx" 口径一致）。
"""

import argparse
import csv
import datetime
import difflib
import os
import re
import sys
import time

import requests
from scholarly import scholarly

NI_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'nature_index_journals.csv')

# Google Scholar 引用串中的期刊写法与 Nature Index 官方刊名不一致时的别名表。
# 键和值都先经过 normalize_journal() 规范化。
JOURNAL_ALIASES = {
    'proceedings of the national academy of sciences':
        'proceedings of the national academy of sciences of the united states of america',
    'pnas':
        'proceedings of the national academy of sciences of the united states of america',
}


def normalize_journal(name):
    """规范化期刊名用于比对：小写、去标点、& -> and、去冠词 the、压缩空格。"""
    if not name:
        return ''
    s = name.lower().replace('&', ' and ')
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    if s.startswith('the '):
        s = s[4:]
    return s


def parse_scholar_id(text):
    """从 Google Scholar 链接或裸 ID 中提取 scholar ID（12 位）。"""
    text = text.strip()
    m = re.search(r'[?&]user=([\w-]{12})', text)
    if m:
        return m.group(1)
    if re.fullmatch(r'[\w-]{12}', text):
        return text
    raise ValueError(f'无法从输入中解析 Google Scholar ID: {text!r}\n'
                     '请输入形如 https://scholar.google.com/citations?user=XXXXXXXXXXXX 的链接'
                     '或 12 位 scholar ID。')


def parse_venue_from_citation(citation):
    """从列表视图的 citation 字符串解析期刊名。

    形如 "Nature communications 15 (1), 4295, 2024" -> "Nature communications"
    解析失败（arXiv、无卷期信息等）返回原串前段，交由后续匹配兜底。
    """
    if not citation:
        return ''
    s = re.sub(r',\s*\d{4}\s*$', '', citation)          # 去掉结尾年份
    m = re.match(r'^(.*?)\s+\d+\s*(\(\S*\))?\s*,', s)   # 去掉 "卷 (期), 页码"
    venue = m.group(1) if m else s
    venue = re.sub(r'([a-z])\s+\d+\s*(\(\S*\))?$', r'\1', venue)  # 无页码时去掉结尾 "卷 (期)"
    return venue.strip(' ,')


def load_nature_index_journals(path=NI_CSV_PATH):
    journals = {}
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = row['journal'].strip()
            journals[normalize_journal(name)] = (name, row.get('category', '').strip())
    # 别名也指向官方刊名
    for alias, official in JOURNAL_ALIASES.items():
        if official in journals:
            journals[alias] = journals[official]
    return journals


def fetch_author_report(scholar_id):
    """抓取作者指标与论文列表，返回 (author_dict, publications)。"""
    from scholarly._proxy_generator import MaxTriesExceededException
    try:
        author = scholarly.search_author_id(scholar_id)
        filled = scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
    except MaxTriesExceededException:
        sys.exit('Google Scholar 触发了验证码/限流（当前 IP 被临时封锁）。\n'
                 '请等待一段时间（通常几十分钟到几小时）后重试，或更换网络/代理后再试。')
    return filled, filled.get('publications', [])


def normalize_person_name(name):
    """规范化人名用于比对：小写、去标点、压缩空格。"""
    if not name:
        return ''
    s = re.sub(r'[^a-z ]+', ' ', name.lower())
    return re.sub(r'\s+', ' ', s).strip()


def openalex_lookup(title):
    """按标题在 OpenAlex 查找论文，返回最匹配的 work（标题相似度 >= 0.9），找不到返回 None。"""
    # Scholar 偶尔在标题尾部拼接作者信息（书籍/章节类条目），如 "... of carrot: A. Khadr et al."
    title = re.sub(r':\s*(?:[A-Z]\.?\s*)+[A-Z][\w\-]+(?:\s+et\s+al\.?)?$', '', title)

    def norm(s):
        return re.sub(r'[^a-z0-9]+', '', (s or '').lower())

    candidates = []
    for params in ({'filter': f'title.search:{title}', 'per-page': 5},
                   {'search': title, 'per-page': 5}):  # 兜底：全文相关性搜索
        try:
            r = requests.get('https://api.openalex.org/works', params=params, timeout=20)
            r.raise_for_status()
            candidates.extend(r.json().get('results', []))
        except requests.RequestException:
            continue
        if candidates:
            break
    best, best_sim = None, 0.0
    for w in candidates:
        sim = difflib.SequenceMatcher(None, norm(w.get('title')), norm(title)).ratio()
        if sim > best_sim:
            best, best_sim = w, sim
    return best if best_sim >= 0.9 else None


def find_scholar_authorship(work, scholar_name):
    """在 OpenAlex work 的作者列表中定位本人，返回 (author_position, is_corresponding)。

    author_position: 'first' / 'middle' / 'last' / None（未定位到本人）。
    先按规范化全名匹配，失败再按 姓+名首字母 匹配。
    """
    target = normalize_person_name(scholar_name)
    authorships = work.get('authorships', [])

    def match(a, mode):
        name = normalize_person_name(a.get('author', {}).get('display_name', ''))
        if not name or not target:
            return False
        if mode == 'full':
            return name == target
        # 姓+名首字母：人名按 "名 ... 姓" 顺序
        t_parts, n_parts = target.split(), name.split()
        return (t_parts[-1] == n_parts[-1]) and (t_parts[0][0] == n_parts[0][0])

    for mode in ('full', 'initial'):
        hits = [a for a in authorships if match(a, mode)]
        if hits:
            a = hits[0]
            return a.get('author_position'), bool(a.get('is_corresponding'))
    return None, False


def enrich_authorship(rows, scholar_name, sleep=0.2):
    """用 OpenAlex 为每篇论文补充作者位置与通讯作者信息（原地修改 rows）。"""
    n_matched = 0
    for row in rows:
        row['author_position'] = ''
        row['is_corresponding'] = ''
        work = openalex_lookup(row['title'])
        if work:
            n_matched += 1
            pos, corr = find_scholar_authorship(work, scholar_name)
            row['author_position'] = pos or 'not_found'
            row['is_corresponding'] = corr if pos else ''
        time.sleep(sleep)
    return n_matched


def build_report(scholar_id, out_dir, with_openalex=True):
    filled, pubs = fetch_author_report(scholar_id)
    ni_journals = load_nature_index_journals()
    ni_keys = set(ni_journals)

    rows, ni_rows, unmatched_venues = [], [], {}
    for p in pubs:
        bib = p.get('bib', {})
        venue_raw = parse_venue_from_citation(bib.get('citation', ''))
        key = normalize_journal(venue_raw)
        is_ni = key in ni_keys
        if venue_raw and not is_ni:
            unmatched_venues.setdefault(venue_raw, 0)
            unmatched_venues[venue_raw] += 1
        row = {
            'title': bib.get('title', ''),
            'year': bib.get('pub_year', ''),
            'venue': venue_raw,
            'citations': p.get('num_citations', 0),
            'is_nature_index': is_ni,
            'nature_index_journal': journals_official(key, ni_journals) if is_ni else '',
        }
        rows.append(row)
        if is_ni:
            ni_rows.append(row)

    # 作者身份补充（OpenAlex: 作者位置 + 通讯作者）
    n_openalex = 0
    if with_openalex and rows:
        n_openalex = enrich_authorship(rows, filled.get('name', ''))
    for row in rows:
        row.setdefault('author_position', '')
        row.setdefault('is_corresponding', '')
        is_first = row['author_position'] == 'first'
        is_corr = row['is_corresponding'] is True
        row['in_first_or_corr'] = is_first or is_corr                    # 一作 + 通讯
        row['in_first1_or_corr_last'] = (is_first or                     # 第一位一作 + 末位通讯
                                         (is_corr and row['author_position'] == 'last'))

    rows.sort(key=lambda r: (-(r['citations'] or 0), str(r['year'])))
    os.makedirs(out_dir, exist_ok=True)
    pubs_csv = os.path.join(out_dir, 'publications.csv')
    fieldnames = ['title', 'year', 'venue', 'citations', 'is_nature_index',
                  'nature_index_journal', 'author_position', 'is_corresponding',
                  'in_first_or_corr', 'in_first1_or_corr_last']
    with open(pubs_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    # 对未匹配的刊名做近似检查，提示可能因写法差异漏判的 Nature Index 期刊
    near_miss = []
    for venue in unmatched_venues:
        close = difflib.get_close_matches(normalize_journal(venue), ni_keys, n=1, cutoff=0.88)
        if close:
            near_miss.append((venue, ni_journals[close[0]][0]))

    # 6 个维度统计: 时间(全部/近5年) x 身份(全部作者/一作+通讯/第一位一作+末位通讯)
    cutoff_year = datetime.date.today().year - 5
    dimension_stats = []
    for role_key, role_label in ((None, '全部作者'),
                                 ('in_first_or_corr', '一作+通讯'),
                                 ('in_first1_or_corr_last', '第一位一作+末位通讯')):
        for recent_only, time_label in ((False, '全部'), (True, f'近5年({cutoff_year}起)')):
            subset = rows
            if role_key:
                subset = [r for r in subset if r[role_key]]
            if recent_only:
                subset = [r for r in subset if str(r['year']).isdigit()
                          and int(r['year']) >= cutoff_year]
            dimension_stats.append({
                'role': role_label, 'time': time_label, **calc_subset_stats(subset)})

    return {
        'scholar_id': scholar_id,
        'name': filled.get('name', ''),
        'affiliation': filled.get('affiliation', ''),
        'citedby': filled.get('citedby'),
        'citedby5y': filled.get('citedby5y'),
        'hindex': filled.get('hindex'),
        'hindex5y': filled.get('hindex5y'),
        'i10index': filled.get('i10index'),
        'i10index5y': filled.get('i10index5y'),
        'n_publications': len(pubs),
        'n_nature_index': len(ni_rows),
        'ni_papers': ni_rows,
        'pubs_csv': pubs_csv,
        'near_miss': near_miss,
        'dimension_stats': dimension_stats,
        'n_openalex_matched': n_openalex,
    }


def calc_subset_stats(rows):
    """对一个论文子集计算统计量（引用数为子集论文在 Scholar 的总被引）。"""
    cites = sorted((r['citations'] or 0 for r in rows), reverse=True)
    h = sum(1 for i, c in enumerate(cites, 1) if c >= i)
    return {
        'n_papers': len(rows),
        'citations': sum(cites),
        'h_index': h,
        'i10_index': sum(1 for c in cites if c >= 10),
        'n_nature_index': sum(1 for r in rows if r['is_nature_index']),
    }


def journals_official(key, ni_journals):
    entry = ni_journals.get(key)
    return entry[0] if entry else ''


def print_summary(report):
    print('\n' + '=' * 72)
    print(f"作者:            {report['name']}  ({report['affiliation']})")
    print(f"Scholar ID:      {report['scholar_id']}")
    print('-' * 72)
    print('Google Scholar 主页官方值:')
    print(f"  引用数量:      {report['citedby']}  (近5年 {report['citedby5y']})")
    print(f"  h-index:       {report['hindex']}  (近5年 {report['hindex5y']})")
    print(f"  i10-index:     {report['i10index']}  (近5年 {report['i10index5y']})")
    print('-' * 72)
    print('分维度统计（基于 Scholar 论文列表逐篇统计；h/i10 由桶内论文被引数计算）:')
    header = f"{'作者身份':<16}{'时间':<14}{'论文数':>7}{'引用数':>8}{'h-index':>9}{'i10-index':>10}{'NI论文':>8}"
    print(header)
    print('  ' + '-' * 68)
    for d in report['dimension_stats']:
        print(f"{d['role']:<16}{d['time']:<14}{d['n_papers']:>7}{d['citations']:>8}"
              f"{d['h_index']:>9}{d['i10_index']:>10}{d['n_nature_index']:>8}")
    print('-' * 72)
    print(f"作者身份判定: OpenAlex 匹配成功 {report['n_openalex_matched']}/{report['n_publications']} 篇"
          '（未匹配论文仅计入"全部作者"维度）')
    if report['ni_papers']:
        print('-' * 72)
        print('Nature Index 论文明细:')
        for r in report['ni_papers']:
            print(f"  [{r['year']}] {r['title'][:70]}")
            print(f"        {r['nature_index_journal']} | 被引 {r['citations']}")
    print('-' * 72)
    print(f"论文明细已保存:  {report['pubs_csv']}")
    if report['near_miss']:
        print('提示: 以下刊名与 Nature Index 期刊近似但未计入（可能写法不同，请人工核对）:')
        for venue, official in report['near_miss']:
            print(f'  "{venue}"  ≈  "{official}"')
    print('=' * 72 + '\n')


def main():
    parser = argparse.ArgumentParser(description='Google Scholar 学术报告 + Nature Index 统计 (+ 可选 CitationMap)')
    parser.add_argument('scholar', help='Google Scholar 链接或 12 位 ID')
    parser.add_argument('--map', action='store_true',
                        help='生成 CitationMap（较慢，依赖 Scholar 抓取 + Nominatim 地理编码，默认关闭）')
    parser.add_argument('--no-openalex', action='store_true',
                        help='跳过 OpenAlex 作者身份补充（此时只统计"全部作者"维度）')
    args = parser.parse_args()

    scholar_id = parse_scholar_id(args.scholar)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           f'output_{scholar_id}')

    report = build_report(scholar_id, out_dir, with_openalex=not args.no_openalex)
    print_summary(report)

    if args.map:
        from citation_map import generate_citation_map
        try:
            generate_citation_map(
                scholar_id,
                output_path=os.path.join(out_dir, 'citation_map.html'),
                csv_output_path=os.path.join(out_dir, 'citation_info.csv'),
                print_citing_affiliations=False,
            )
            print(f"CitationMap 已保存: {os.path.join(out_dir, 'citation_map.html')}")
        except Exception as e:
            print(f'CitationMap 生成失败（{type(e).__name__}: {e}）。\n'
                  '学术报告部分不受影响；可稍后单独重跑地图（加 --map）。\n'
                  '注: 地图依赖 Google Scholar 抓取和 Nominatim 地理编码，两者都可能限流。')


if __name__ == '__main__':
    sys.exit(main())
