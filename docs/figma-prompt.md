# Figma Make prompt

把下面分隔线以下的全部内容粘贴到 Figma Make。prompt 用英文写（Figma 对英文的理解更稳定），界面文案已含中英两种语言。

---

Build the frontend of **Pip-Scholar**: a single-page web app that turns a Google Scholar profile into an academic report (statistics + charts). It runs locally next to a Python JSON API. The UI is bilingual: 中文 / English.

## Tech
- React + TypeScript + Tailwind, one page. View state machine: `home → loading → report`, or `error`.
- Put all API calls in `api.ts` with `API_BASE = ''` (same origin when the backend serves the build; `http://127.0.0.1:8000` in local dev). Add `USE_MOCK = true`: it fakes the 4 progress steps (~3 s) and then returns the sample report at the end of this prompt, so the preview works without the backend.
- Put every UI string in `strings.ts` as `{ zh: {...}, en: {...} }`. No hard-coded copy in components.
- Charts: hand-built SVG, or Recharts styled to the spec below.

## Visual direction: inspired by Pratt Institute
Editorial and poster-like: black on white, confident oversized type, lots of white space, a strict grid, thin black rules.
- **Type.** Display and UI: **Archivo** (stand-in for Pratt's Graphik), weights 700–900, tracking −0.04 to −0.055em at large sizes. Long-form text: **Newsreader** (stand-in for Tiempos), 16–30px. Chinese fallbacks: Noto Sans SC and Noto Serif SC. Eyebrow labels: 12px, weight 600, uppercase, +0.12em tracking. Never uppercase metric names (h-index, i10-index) or Scholar IDs, which are case-sensitive.
- **Color tokens.** paper `#FFFFFF`, panel `#F3F3F1`, ink `#0A0A0A`, ink-2 `#4D4D4D`, ink-3 `#6E6E6E`, hairline `#DEDEDE`, axis `#B8B8B8`, track `#ECECEC`, context gray `#A6A6A6`, accent (electric blue) `#2B44FF`. The accent is reserved for data emphasis (Nature Index, "since {year}", the h-core), the progress bar and focus rings. Text is never set in the accent color. The only exception is white text on an accent badge.
- **Shapes.** Use a 0 border radius everywhere, except the 4px rounded data end of chart bars. Use 1px black rules between rows and tiles, and a 2px black rule above each report section. No gradients and no drop shadows. The one exception is tooltips, which get a hard `4px 4px 0` black offset shadow. No emoji, no illustrations, and no icons other than the arrows → ↗ ↓ ↻ set in the type.
- **Signature motifs.**
  1. A full-bleed black band below the search form. It holds one slowly scrolling line of words separated by arrows, 22–40px Archivo 800 in white. zh: "学术报告 → 引用 → h-index → i10-index → Nature Index → 一作 + 通讯 → Google Scholar → OpenAlex →". en: "Scholar Report → Citations → h-index → … → OpenAlex →". It stops under `prefers-reduced-motion`.
  2. Section numbers 01–09 set as huge outlined numerals (transparent fill, 1.5px black stroke), each next to a huge solid section title.
  3. A black footer with small serif notes, followed by the wordmark "Pip—Scholar" set enormous (≈13vw) across the page.
- **Layout.** Max width 1400px. Side padding clamp(16px, 4vw, 56px). Two-column figure rows on desktop stack below 960px. The second breakpoint is 640px. There must be no horizontal page scroll at 390px. Provide desktop (1440) and mobile (390) frames.

## Header (sticky, white, 1px black bottom rule)
- Left: the wordmark "Pip—Scholar" (Archivo 900, 26px), then a small tagline: "Google Scholar 学术报告 · 本地运行" / "Google Scholar reports · runs locally".
- Right: a segmented language switch `[中文 | EN]` with a 1px black border. The active option has a black fill and white text.
- Default to the browser language and remember the user's choice.

## Screens

### 1 · Home
- Eyebrow: "Google Scholar × Nature Index × OpenAlex".
- Giant headline (≈14vw, line-height .84): zh "学术↵报告", en "Scholar↵Report".
- Serif lede (max 28em):
  - zh: "粘贴 Google Scholar 主页链接或 12 位学者 ID，生成引用、h-index、Nature Index 论文与作者身份的统计和图表。"
  - en: "Paste a Google Scholar profile link or 12-character ID to get citations, h-index, Nature Index papers and authorship as numbers and charts."
- Search form:
  - Label: "Google Scholar 链接或 ID" / "Google Scholar link or ID".
  - One large borderless input (20–34px) with a 3px black underline that turns accent on focus.
  - Black submit button "生成报告 →" / "Generate →". On hover it fills with the accent and the arrow moves 4px right.
  - Below the input: a checkbox "作者身份分析（OpenAlex）" / "Authorship analysis (OpenAlex)", on by default.
  - A second checkbox: "忽略缓存，重新抓取" / "Ignore cache and re-fetch".
  - A text link "查看演示报告 →" / "See a demo report →" that submits the query `demo`.
  - On mobile these stack and the button goes full width.
- Accepted input: a URL containing `user=` followed by a 12-character ID, a bare 12-character ID (`[A-Za-z0-9_-]{12}`), or `demo`. For anything else, show inline: "✕ 无法识别：请输入 Scholar 主页链接（含 user=）或 12 位 ID。" / "✕ Not recognised: enter a Scholar profile link (with user=) or a 12-character ID."
- Once a search starts, the hero collapses to just the search bar.

### 2 · Loading
- Eyebrow "正在生成报告" / "Generating report", with the Scholar ID as a big title.
- A 4-column step row with huge numerals 01–04:
  1. Google Scholar — 主页与论文列表 / Profile and publications
  2. Nature Index — 匹配期刊名单 / Match the journal list
  3. OpenAlex — 作者位置与通讯作者 / Author position & corresponding. While running it shows "done / total". It is struck through when authorship analysis is off.
  4. 统计 / Statistics — 计算六个维度 / Six dimensions
- Step states: done (ink with ✓), current (ink with a small pulsing accent square), pending (gray).
- Below the steps, a 4px progress bar (track `#ECECEC`, accent fill).
- Serif note: "已用时 m:ss · Google Scholar 抓取通常需要 1–3 分钟，请保持页面打开。" / "Elapsed m:ss · Fetching from Google Scholar usually takes 1–3 minutes. Keep this page open."
- The steps become a 2×2 grid on mobile.

### 3 · Error
- Eyebrow "出错了" / "Something went wrong".
- The message as a 24–44px bold headline, the raw detail in small serif below it, and an outlined button "重试 ↻" / "Try again ↻".
- Map `error.code` to a message:
  - `invalid_query`
  - `scholar_unavailable`: "the ID may not exist, or Scholar is rate-limiting this network (CAPTCHA); try later or from another network"
  - `scholar_failed`
  - `scholarly_missing`: "run pip install -r requirements.txt"
  - `report_not_found`
  - `network`: "cannot reach the local server — is python run.py running?"
  - `internal`

### 4 · Report
**Profile header**
- Eyebrow "Scholar ID · {id}", plus an accent badge "演示数据" / "Demo data" when `demo` is true.
- Name at 52–140px, Archivo 900. Affiliation in serif, 20–28px. Interests as outlined tags.
- Outlined buttons: "Scholar 主页 ↗" / "Scholar profile ↗", "个人主页 ↗" / "Homepage ↗" (only when present), "下载 CSV ↓" / "Download CSV ↓", "重新抓取 ↻" / "Re-fetch ↻".
- Meta line: "生成于 {date}" / "Generated {date}".
- Optional grayscale square photo on the right.

Then come the numbered sections. Each has an outlined number and a solid title.

**01 概览 / Overview**
- Five KPI tiles in one row (2 columns on mobile), separated by 1px black rules:
  - 总引用 / Citations, h-index and i10-index, from `official.*.all`.
  - 论文 / Publications, from `totals.publications`.
  - Nature Index 论文 / Nature Index papers, from `totals.nature_index`.
- Values are 44–104px Archivo 900 with proportional figures.
- Each tile has a sub-line "{year} 年起 {value}" / "Since {year}: {value}". It uses `official.*.recent`; for papers and NI it uses the dimension with role=all, period=recent.
- Footnote: these are the official Scholar profile values, and papers are counted by publication year.

**02 六维统计 / Six dimensions** — the core table.
- Rows are 3 roles × 2 periods:
  - Roles: 全部作者 / All authorships; 一作 + 通讯 / First or corresponding; 第一位一作 + 末位通讯 / First, or last + corresponding.
  - Periods: 全部 / All time; {year} 年起 / Since {year}.
- Columns: 论文 / Papers, 引用 / Citations, h-index, i10-index, Nature Index.
- Each cell holds a big bold number with a 6px bar under it, scaled to the column maximum. Bars are black for all-time rows and accent for recent rows. The legend sits above the table.
- On desktop the role name spans its two rows. On mobile it becomes a full-width group row so the table fits in 390px.
- When `authorship.enabled` is false, the role rows show "—" and a note.

**03 时间线 / Timeline** — two charts side by side.
- "每年被引次数 / Citations per year": black columns. Label only the maximum. Add a note that the current year is year-to-date.
- "每年发表论文 / Publications per year": stacked columns with Nature Index in accent at the bottom and Other in black on top, separated by a 2px white gap.
- Both plots share one baseline. Reserve a legend row on both charts so they line up.

**04 影响力 / Impact**
- Title: "论文按被引排序（前 {n} 篇）" / "Papers ranked by citations (top {n})", where n = max(2h, 20).
- Columns by rank. The first h columns are accent (the h-core) and the rest are context gray.
- A thin black diagonal labeled "被引 = 排名" / "Citations = rank", and a vertical marker at rank h labeled "h = {h}".
- Serif note: "{h} papers have at least {h} citations each, so the h-index is {h}."

**05 作者身份 / Authorship**
- Left: horizontal bars titled "本人在作者列表中的位置" / "Position in the author list".
  - In black: 第一作者 / First author, 末位作者 / Last author, 中间作者 / Middle author.
  - In gray: 未定位到本人 / Not located, 未匹配到 OpenAlex / Not in OpenAlex.
  - The value sits at the end of each bar.
- Right: two big stats, "通讯作者论文 / Corresponding-author papers" and "OpenAlex 匹配 / Matched in OpenAlex", each with "共 N 篇" / "of N".
- Gray notice boxes:
  - When `authorship.status` is `limited`: the OpenAlex quota ran out; suggest a free API key.
  - When it is `error`: the OpenAlex requests failed.
- Caveat note: the data comes from OpenAlex; corresponding-author coverage is incomplete, so counts are a lower bound; "first" means listed first.

**06 Nature Index**
- Left: an editorial list of NI papers. Each item shows the year in bold sans, the title in serif linking out, the journal in small gray, and the citation count large on the right. Show the first 10, then a button "显示全部 N 篇" / "Show all N".
- Right: horizontal accent bars titled "学科分布 / Subject areas", using Chinese names: 物理科学 Physical sciences, 化学 Chemistry, 生命科学 Biological sciences, 地球与环境科学 Earth & environmental sciences, 健康科学 Health sciences, 社会科学 Social sciences, 应用科学 Applied sciences. Note that multidisciplinary journals count toward several subjects.
- A gray notice box lists `near_misses` as “venue” ≈ “journal”.
- Empty state: "没有发表在 Nature Index 期刊上的论文。" / "No papers in Nature Index journals."

**07 期刊与会议 / Venues**
- Horizontal bars for the top 10 venues.
- NI venues are accent and carry a small white-on-accent "NI" badge. Other venues are black. Include a legend.

**08 论文明细 / Publications**
- Controls row:
  - An underlined search input, "搜索标题或期刊" / "Search title or venue".
  - A segmented filter `[全部 All | Nature Index | 一作 + 通讯 | 第一位一作 + 末位通讯]`. Hide the last two when authorship is off.
  - A sort select: `[按被引 Most cited | 按年份 Newest]`.
- Table columns:
  - #
  - Title (serif, links out, NI badge), with the venue in gray under it
  - Year
  - Citations (bold)
  - Position (一作/中间/末位, First/Middle/Last)
  - Corresponding (✓)
- Show 25 rows, then "显示更多 / Show more". Footer: "显示 {shown} / {total} 篇" / "Showing {shown} of {total}".
- On mobile the table scrolls horizontally inside its container.

**09 引用地图 / Citation map**
- Show only when `citation_map.available` or `citation_map.ready` is true.
- Contents: a description, a button "生成引用地图 / Generate citation map" (POST, then poll), and then the map in an iframe.

## Charts (all)
- Bars are at most 24px wide, with a 4px rounded data end, a square base and gaps of at least 2px.
- Gridlines are 1px solid hairlines (`#DEDEDE`); the axis is `#B8B8B8`.
- Tick labels are 11px ink-3 with tabular numerals.
- Every chart has a "表格 / Table" text toggle that swaps in an accessible data table.
- Hovering, or using the ←/→ keys, shows a tooltip: a title, then value rows each keyed by a short colored line.
- Text never wears a series color. Show a legend whenever there are 2 or more series.

## Accessibility
- Visible 3px accent focus rings.
- `aria-live` on the progress section.
- Table views for every chart.
- Hit targets of at least 44px.
- Respect `prefers-reduced-motion`.

## API (Python backend, JSON)
- `POST /api/reports` with body `{"query": string, "openalex": boolean, "refresh": boolean}` returns a `Job`. On a cache hit the job is already `done`. Bad input returns 400 with `{"error": {"code": "invalid_query", "message": "…"}}`.
- `GET /api/jobs/{id}` returns a `Job`. Poll every 1 s while `status === "running"`.
- `GET /api/reports/{scholar_id}` returns a `Report`.
- `GET /api/reports/{scholar_id}/publications.csv` is the CSV download link.
- `POST /api/reports/{scholar_id}/map` returns a `Job`. `GET /api/reports/{scholar_id}/map` returns the map HTML, used as the iframe `src`.
- After a report loads, keep `?id={scholar_id}` in the URL. When the page opens with `?id=`, GET the report directly and fall back to POST.

```ts
type Job = {
  id: string; kind: 'report' | 'map'; scholar_id: string;
  status: 'running' | 'done' | 'error';
  stage: 'scholar' | 'nature_index' | 'openalex' | 'stats' | 'map' | 'done' | null;
  done: number | null; total: number | null;  // OpenAlex progress
  error: { code: string; message: string } | null;
};
type Role = 'all' | 'first_corr' | 'first_lastcorr';
type Report = {
  scholar_id: string; demo: boolean; generated_at: string; recent_since: number;  // recent_since = this year − 5
  profile: { name: string; affiliation: string; interests: string[]; homepage: string; photo: string; url: string };
  official: Record<'citations' | 'h_index' | 'i10_index', { all: number; recent: number }>;
  totals: { publications: number; nature_index: number; citations: number };
  authorship: { enabled: boolean; status: 'ok' | 'limited' | 'error' | 'disabled'; matched: number; corresponding: number;
    positions: Record<'first' | 'middle' | 'last' | 'unknown' | 'unmatched', number> };
  dimensions: { role: Role; period: 'all' | 'recent'; papers: number; citations: number;
    h_index: number; i10_index: number; nature_index: number }[];  // always 6 rows
  citations_per_year: { year: number; citations: number }[];
  publications_per_year: { year: number; total: number; nature_index: number }[];
  nature_index: {
    papers: { title: string; year: number | null; journal: string; citations: number; categories: string[]; url: string }[];
    categories: { name: string; count: number }[];
    near_misses: { venue: string; journal: string }[];
  };
  venues: { name: string; count: number; nature_index: boolean }[];  // top 10
  publications: { title: string; year: number | null; venue: string; citations: number; url: string;
    nature_index: boolean; ni_journal: string; position: 'first' | 'middle' | 'last' | 'unknown' | null;
    corresponding: boolean | null; first_corr: boolean; first_lastcorr: boolean }[];  // sorted by citations
  citation_map: { available: boolean; ready: boolean };
};
```

Sample report for the mock (the paper, venue and publication lists are truncated):

```json
{
  "scholar_id": "demo", "demo": true, "generated_at": "2026-10-02T12:00:00+00:00", "recent_since": 2021,
  "profile": {"name": "Demo Scholar", "affiliation": "Pip-Scholar Example University (fictional)",
    "interests": ["Materials informatics", "Catalysis", "Machine learning"], "homepage": "", "photo": "", "url": ""},
  "official": {"citations": {"all": 2422, "recent": 1689}, "h_index": {"all": 27, "recent": 24}, "i10_index": {"all": 44, "recent": 41}},
  "totals": {"publications": 72, "nature_index": 13, "citations": 2422},
  "authorship": {"enabled": true, "status": "ok", "matched": 64, "corresponding": 28,
    "positions": {"first": 31, "middle": 17, "last": 15, "unknown": 1, "unmatched": 8}},
  "dimensions": [
    {"role": "all", "period": "all", "papers": 72, "citations": 2422, "h_index": 27, "i10_index": 44, "nature_index": 13},
    {"role": "all", "period": "recent", "papers": 44, "citations": 589, "h_index": 12, "i10_index": 19, "nature_index": 5},
    {"role": "first_corr", "period": "all", "papers": 46, "citations": 1570, "h_index": 20, "i10_index": 30, "nature_index": 7},
    {"role": "first_corr", "period": "recent", "papers": 28, "citations": 485, "h_index": 11, "i10_index": 14, "nature_index": 3},
    {"role": "first_lastcorr", "period": "all", "papers": 43, "citations": 1417, "h_index": 19, "i10_index": 29, "nature_index": 7},
    {"role": "first_lastcorr", "period": "recent", "papers": 27, "citations": 479, "h_index": 11, "i10_index": 14, "nature_index": 3}
  ],
  "citations_per_year": [{"year": 2013, "citations": 10}, {"year": 2014, "citations": 14}, {"year": 2015, "citations": 36},
    {"year": 2016, "citations": 59}, {"year": 2017, "citations": 83}, {"year": 2018, "citations": 148}, {"year": 2019, "citations": 193},
    {"year": 2020, "citations": 190}, {"year": 2021, "citations": 261}, {"year": 2022, "citations": 251}, {"year": 2023, "citations": 280},
    {"year": 2024, "citations": 328}, {"year": 2025, "citations": 328}, {"year": 2026, "citations": 241}],
  "publications_per_year": [{"year": 2013, "total": 3, "nature_index": 0}, {"year": 2014, "total": 1, "nature_index": 1},
    {"year": 2015, "total": 3, "nature_index": 2}, {"year": 2016, "total": 3, "nature_index": 0}, {"year": 2017, "total": 4, "nature_index": 1},
    {"year": 2018, "total": 5, "nature_index": 2}, {"year": 2019, "total": 3, "nature_index": 1}, {"year": 2020, "total": 6, "nature_index": 1},
    {"year": 2021, "total": 6, "nature_index": 1}, {"year": 2022, "total": 9, "nature_index": 3}, {"year": 2023, "total": 12, "nature_index": 0},
    {"year": 2024, "total": 12, "nature_index": 1}, {"year": 2025, "total": 4, "nature_index": 0}, {"year": 2026, "total": 1, "nature_index": 0}],
  "nature_index": {
    "papers": [
      {"title": "Adaptive charge transport in catalyst discovery", "year": 2024, "journal": "Physical Review Letters", "citations": 14, "categories": ["Physical sciences"], "url": ""},
      {"title": "Interpretable spectroscopy in thermal transport", "year": 2022, "journal": "Nature Communications", "citations": 74,
        "categories": ["Biological sciences", "Chemistry", "Earth & environmental sciences", "Health sciences", "Physical sciences"], "url": ""}
    ],
    "categories": [{"name": "Chemistry", "count": 10}, {"name": "Physical sciences", "count": 9}, {"name": "Biological sciences", "count": 5},
      {"name": "Earth & environmental sciences", "count": 5}, {"name": "Health sciences", "count": 5}],
    "near_misses": [{"venue": "Nature communication", "journal": "Nature Communications"}]
  },
  "venues": [{"name": "Scientific Reports", "count": 14, "nature_index": false}, {"name": "arXiv preprint", "count": 11, "nature_index": false},
    {"name": "Journal of Materials Chemistry A", "count": 8, "nature_index": false}, {"name": "Journal of the American Chemical Society", "count": 4, "nature_index": true}],
  "publications": [
    {"title": "Low-cost charge transport in porous frameworks", "year": 2018, "venue": "Advanced Materials", "citations": 195, "url": "",
      "nature_index": true, "ni_journal": "Advanced Materials", "position": null, "corresponding": null, "first_corr": false, "first_lastcorr": false},
    {"title": "Ultrafast synthesis of perovskite solar cells", "year": 2018, "venue": "Physical Review Letters", "citations": 187, "url": "",
      "nature_index": true, "ni_journal": "Physical Review Letters", "position": "first", "corresponding": true, "first_corr": true, "first_lastcorr": true},
    {"title": "High-throughput self-assembly for 2D semiconductors", "year": 2018, "venue": "Journal of Materials Chemistry A", "citations": 141, "url": "",
      "nature_index": false, "ni_journal": "", "position": "middle", "corresponding": true, "first_corr": true, "first_lastcorr": false}
  ],
  "citation_map": {"available": false, "ready": false}
}
```
