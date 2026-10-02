# Pip-Scholar

本地运行的 Web 应用：输入 Google Scholar 主页链接或 ID，生成学术统计与图表，界面支持中文 / English。

## 运行

```bash
pip install -r requirements.txt
python run.py          # 自动打开 http://127.0.0.1:8000
```

输入 `demo` 可离线查看演示报告。

## 输出

- 指标：引用、h-index、i10-index、论文数、Nature Index 论文数（全部 / 近 5 年）
- 六维统计：时间（全部 / 近 5 年，即发表年份 ≥ 今年 − 5）× 作者身份（全部作者 / 一作 + 通讯 / 第一位一作 + 末位通讯）
- 图表：每年被引、每年发表、h-index 排序图、作者位置、Nature Index 学科、常发期刊；论文明细可筛选，并可导出 CSV

## 结构

```
run.py      启动服务
backend/    FastAPI：Scholar 抓取、Nature Index 匹配、OpenAlex 作者身份、统计、任务与缓存（接口文档 /docs）
frontend/   静态前端（原生 JS + SVG，无需构建）
tests/      pytest
docs/       用 Figma 生成前端的 prompt
```

## 说明

- 数据来源
  - Google Scholar：经 scholarly 抓取，频繁请求会触发验证码。
  - OpenAlex：提供作者位置与通讯作者。通讯作者覆盖不全，统计结果为下限。
  - Nature Index 名单：共 178 种，见 `backend/data/`。
- OpenAlex 自 2026 年起按量计费，无 key 每天 $0.10。建议申请免费 key（每天 $1）后这样启动：`OPENALEX_API_KEY=… python run.py`。
- 引用地图（可选）：`pip install citation-map` 后，在报告页底部生成。
- 换用其他前端：`PIP_SCHOLAR_FRONTEND=<构建目录> python run.py`。
- 测试：`pip install pytest httpx && pytest`
