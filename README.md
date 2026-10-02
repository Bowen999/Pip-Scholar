# Pip-Scholar

输入 Google Scholar 链接或 ID，一键生成个人学术报告：论文数量、引用数量、h-index、i10-index、Nature Index 论文数量，并可选生成 CitationMap（全球引用地图）。

统计按 **2 个时间维度 × 3 个作者身份维度**（共 6 个维度）展示：

- 时间：全部 / 近 5 年（发表年份 ≥ 当年-5，与 Google Scholar "Since 20xx" 口径一致）
- 作者身份：全部作者 / 第一作者+通讯作者 / 第一位一作+末位通讯作者

## 安装

```bash
pip install scholarly requests
pip install citation-map   # 可选，仅 --map 生成引用地图时需要
```

## 用法

```bash
python3 scholar_report.py "https://scholar.google.ca/citations?user=A4H2UV8AAAAJ&hl=en"
python3 scholar_report.py A4H2UV8AAAAJ            # 裸 ID 也可以
python3 scholar_report.py A4H2UV8AAAAJ --map      # 生成 CitationMap（较慢，默认关闭）
python3 scholar_report.py A4H2UV8AAAAJ --no-openalex  # 跳过作者身份补充
```

输出保存在 `output_<scholar_id>/`：

- `publications.csv` — 全部论文明细（含 Nature Index 标记、作者位置、是否通讯作者）
- `citation_map.html` / `citation_info.csv` — 引用地图（加 `--map` 时生成）

## 数据来源与口径

- **学术指标与论文列表**：Google Scholar（经 [scholarly](https://github.com/scholarly-python-package/scholarly) 抓取；频繁请求会触发验证码限流，请控制频率）
- **Nature Index 期刊名单**：`nature_index_journals.csv`，2026 年扩展版（177 期刊 + 1 会议，178 条），整理自 nature.com 官方 FAQ
- **作者位置 / 通讯作者**：[OpenAlex](https://openalex.org)（出版社上报数据，通讯作者覆盖不全，统计为下限；共同第一作者不可见，"一作"按作者列表第一位认定）
- **引用地图**：[CitationMap](https://github.com/ChenLiu-1996/CitationMap) 包（地理编码用 Nominatim 公共服务，可能限流）

分维度统计中，各桶的引用数 / h-index / i10-index 由桶内论文的 Scholar 单篇被引数计算（"近 5 年"按论文发表年筛选，引用数为这些论文的总被引）。
