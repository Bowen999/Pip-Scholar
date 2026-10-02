# Figma Make prompt

两条 prompt 各不超过 2000 字。先发第一条生成界面；需要接入本地后端时，再发第二条。

## 1 · 界面

```text
为本地 Web 应用 Pip-Scholar 设计并实现前端：输入 Google Scholar 主页链接或 12 位 ID，生成学术统计与图表。单页，React + TypeScript + Tailwind；文案全部放 strings.ts（中/英两套），页眉右侧 [中文|EN] 分段切换并记住选择。

【风格：参考 Pratt Institute】白底黑字、海报感、严格网格、大留白。标题与界面用 Archivo 700–900（大字号字距 -0.05em），长文本用 Newsreader 衬线，中文用 Noto Sans SC / Noto Serif SC。小标签 12px 大写加字距（h-index 和 ID 不转大写）。颜色：墨 #0A0A0A、纸 #FFFFFF、面板 #F3F3F1、次文字 #6E6E6E、细线 #DEDEDE、弱化 #A6A6A6；唯一强调色电光蓝 #2B44FF，只用于数据高亮（Nature Index、近 5 年、h 核心）、进度条和焦点框，不做文字色。全部直角；1px 黑线分隔，每节顶部 2px 黑线；无渐变、无阴影（仅提示框用 4px 黑色硬投影）；不用图标和插画，只用 → ↗ ↓ ↻。
标志元素：① 搜索区下方通栏黑底白字滚动文字带「学术报告 → 引用 → h-index → Nature Index → …」，减少动效时静止；② 章节号 01–08 为超大描边数字，配实心大标题；③ 黑色页脚，底部超大字标 Pip—Scholar。
出桌面 1440 与手机 390 两版，手机无横向滚动。

【状态】
1 首页：超大标题「学术↵报告」/「Scholar↵Report」，衬线导语；大号无边框输入框（3px 黑下划线，聚焦变蓝）＋黑色按钮「生成报告 →」；复选框「作者身份分析（OpenAlex）」默认开、「忽略缓存，重新抓取」；链接「查看演示报告 →」「导入保存的网页 ↑」（上传 Scholar 主页 .html，POST /api/reports/import {html, query, openalex}，之后流程相同；抓取被限流的错误页也显示这个入口和保存步骤）。非法输入行内报错。开始生成后首屏收成一条搜索栏。
2 加载：4 步横排（Google Scholar / Nature Index / OpenAlex 显示 done/total / 统计），超大编号，当前步闪烁蓝方块，4px 进度条，已用时。
3 出错：粗体大字错误信息＋「重试」。
4 报告：姓名超大字、机构衬线、兴趣标签、描边按钮（Scholar 主页 ↗、下载 CSV ↓、重新抓取 ↻）、生成时间。
01 概览：5 个指标（总引用、h-index、i10-index、论文、NI 论文），数字超大，下附「2021 年起 n」。
02 六维统计：行＝3 种身份（全部作者 / 一作+通讯 / 第一位一作+末位通讯）× 2 时段（全部 / 2021 年起），列＝论文、引用、h-index、i10-index、NI；数字下 6px 细条按列归一，全部黑、近年蓝。手机端身份名独占一行。
03 时间线：每年被引柱图（只标最大值）；每年发表堆叠柱（NI 蓝在底、其他黑，段间 2px 白缝）。
04 影响力：论文按被引排序的柱图，前 h 篇蓝、其余灰，对角线「被引＝排名」，竖线标「h = {h}」。
05 作者身份：横向条（一作、末位、中间为黑；未定位、未匹配为灰）＋通讯作者数、OpenAlex 匹配数两个大数字。
06 Nature Index：编辑式论文列表（年份、衬线标题、期刊、被引）＋学科分布蓝色横条＋灰底提示框「刊名相近但未计入」。
07 期刊与会议：前 10 横条，NI 为蓝色并带「NI」小标。
08 论文明细：搜索、分段筛选（全部 / NI / 一作+通讯 / 第一位一作+末位通讯）、排序，表格每次 25 行＋「显示更多」。
图表通用：柱宽 ≤24px、数据端 4px 圆角，1px 浅灰网格，悬停或 ←/→ 显示提示，每图可切换「表格」视图；文字不用系列色。

【数据】api.ts：POST /api/reports {query, openalex, refresh} 返回任务；每秒轮询 GET /api/jobs/{id}（status 为 running/done/error，含 stage 与 done/total）；完成后 GET /api/reports/{id}。设 USE_MOCK=true 并用演示数据：Demo Scholar，72 篇论文，引用 2422，h-index 27，NI 论文 13 篇。文中「2021 年起」的年份取 recent_since（今年 − 5）。
```

## 2 · 接入后端（可选）

```text
接入真实后端：api.ts 的类型改成下面的结构，字段名保持不变。

type Job = {id: string; status: 'running'|'done'|'error'; stage: 'scholar'|'nature_index'|'openalex'|'stats'|'done'|null; done: number|null; total: number|null; error: {code: string; message: string}|null};

type Report = {
  scholar_id: string; demo: boolean; generated_at: string; recent_since: number;
  profile: {name: string; affiliation: string; interests: string[]; homepage: string; photo: string; url: string};
  official: Record<'citations'|'h_index'|'i10_index', {all: number; recent: number}>;
  totals: {publications: number; nature_index: number};
  authorship: {enabled: boolean; status: 'ok'|'limited'|'error'|'disabled'; matched: number; corresponding: number; positions: Record<'first'|'middle'|'last'|'unknown'|'unmatched', number>};
  dimensions: {role: 'all'|'first_corr'|'first_lastcorr'; period: 'all'|'recent'; papers: number; citations: number; h_index: number; i10_index: number; nature_index: number}[];
  citations_per_year: {year: number; citations: number}[];
  publications_per_year: {year: number; total: number; nature_index: number}[];
  nature_index: {papers: {title: string; year: number|null; journal: string; citations: number; url: string}[]; categories: {name: string; count: number}[]; near_misses: {venue: string; journal: string}[]};
  venues: {name: string; count: number; nature_index: boolean}[];
  publications: {title: string; year: number|null; venue: string; citations: number; url: string; nature_index: boolean; position: 'first'|'middle'|'last'|'unknown'|null; corresponding: boolean|null; first_corr: boolean; first_lastcorr: boolean}[];
};

说明：authorship.enabled 为 false 时，02 节的两种身份行显示「—」，08 节隐藏身份筛选；status 为 limited 时提示申请免费 OpenAlex API key。出错时返回 { error: { code, message } }，code 包括 invalid_query、scholar_unavailable、scholar_failed、report_not_found、internal；前端连不上服务时用 network。每个 code 配中英文提示。CSV 下载：GET /api/reports/{id}/publications.csv。API_BASE 默认为空（与后端同源），本地开发时设为 http://127.0.0.1:8000。
```
