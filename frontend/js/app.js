// 页面逻辑：输入 → 创建任务 → 轮询进度 → 渲染报告（统计 + 图表），中英切换时整页重绘。
import * as api from './api.js';
import { columnChart, dataTable, hbarChart, legend } from './charts.js';
import { h, safeUrl } from './dom.js';
import { category, fmt, fmtDate, initialLang, onLangChange, setLang, t } from './i18n.js';

const $ = (sel) => document.querySelector(sel);
const STAGES = ['scholar', 'nature_index', 'openalex', 'stats'];
const ROLES = ['all', 'first_corr', 'first_lastcorr'];
const METRICS = ['papers', 'citations', 'h_index', 'i10_index', 'nature_index'];
const PAGE = 25;
const NI_PAGE = 10;
const INK = 'var(--ink)';
const ACCENT = 'var(--accent)';
const CONTEXT = 'var(--context)';

const state = {
  run: 0,  // 每次新查询 +1，作废旧的轮询
  query: '',
  options: { openalex: true, refresh: false },
  job: null,
  started: 0,
  report: null,
  error: null,
  pubs: { q: '', filter: 'all', sort: 'citations', limit: PAGE },
  niAll: false,
  mapRunning: false,
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const external = (href, ...children) => h('a', { href, target: '_blank', rel: 'noopener noreferrer' }, ...children);

function parseQuery(text) {
  const q = text.trim();
  if (q.toLowerCase() === 'demo') return 'demo';
  const m = q.match(/[?&]user=([\w-]{12})(?![\w-])/);
  if (m) return m[1];
  return /^[\w-]{12}$/.test(q) ? q : null;
}

function setView(view) {
  document.body.dataset.view = view;
  $('#status').hidden = view !== 'loading';
  $('#error').hidden = view !== 'error';
  $('#report').hidden = view !== 'report';
}

// ---------- 流程 ----------

async function start(query, { refresh = false } = {}) {
  const sid = parseQuery(query);
  const err = $('#query-error');
  if (!sid) {
    err.textContent = t('form.invalid');
    err.hidden = false;
    $('#query').focus();
    return;
  }
  err.hidden = true;
  const run = ++state.run;
  state.query = query.trim();
  state.options = { openalex: $('#opt-openalex').checked, refresh: refresh || $('#opt-refresh').checked };
  state.job = { scholar_id: sid, status: 'running', stage: null };
  state.started = Date.now();
  state.pubs = { q: '', filter: 'all', sort: 'citations', limit: PAGE };
  $('#query').value = state.query;
  renderStatus();
  setView('loading');
  window.scrollTo({ top: 0 });

  try {
    let job = await api.createReport(state.query, state.options);
    while (job.status === 'running') {
      if (run !== state.run) return;
      state.job = job;
      renderStatus();
      await sleep(1000);
      job = await api.getJob(job.id);
    }
    if (run !== state.run) return;
    if (job.status === 'error') throw job.error;
    const report = await api.getReport(job.scholar_id);
    if (run === state.run) showReport(report);
  } catch (e) {
    if (run !== state.run) return;
    state.error = { code: e.code ?? 'internal', message: e.message ?? '' };
    renderError();
    setView('error');
  }
}

function showReport(report) {
  state.report = report;
  state.niAll = false;
  renderReport();
  setView('report');
  document.title = `${report.profile.name || report.scholar_id} — Pip-Scholar`;
  const url = new URL(location.href);
  url.searchParams.set('id', report.scholar_id);
  history.replaceState(null, '', url);
  window.scrollTo({ top: 0 });
  $('#report-name')?.focus({ preventScroll: true });
}

// ---------- 进度 / 错误 ----------

function renderStatus() {
  const job = state.job;
  const stage = job.stage ?? 'scholar';
  const current = stage === 'done' ? STAGES.length : Math.max(0, STAGES.indexOf(stage));
  $('#status-title').textContent = job.scholar_id === 'demo' ? t('report.demo') : job.scholar_id;
  $('#steps').replaceChildren(...STAGES.map((s, i) => {
    const st = s === 'openalex' && !state.options.openalex ? 'skipped'
      : i < current ? 'done' : i === current ? 'current' : 'pending';
    const counting = s === 'openalex' && stage === 'openalex' && job.total;
    return h('li', { 'data-state': st, 'aria-current': st === 'current' ? 'step' : null },
      h('span', { class: 'step__num' }, String(i + 1).padStart(2, '0')),
      h('span', { class: 'name' }, t(`stage.${s}`)),
      h('span', { class: 'desc' }, counting ? `${fmt(job.done ?? 0)} / ${fmt(job.total)}` : t(`stage.${s}.desc`)));
  }));
  const frac = stage === 'openalex' && job.total
    ? 0.6 + (0.35 * (job.done ?? 0)) / job.total
    : { scholar: 0.04, nature_index: 0.55, openalex: 0.6, stats: 0.95, done: 1 }[stage] ?? 0;
  $('#meter').style.width = `${Math.round(frac * 100)}%`;
  updateElapsed();
}

function updateElapsed() {
  const s = Math.floor((Date.now() - state.started) / 1000);
  $('#elapsed').textContent = t('status.elapsed', { time: `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` });
}

function errorText({ code }) {
  const text = t(`error.${code}`);
  return text === `error.${code}` ? t('error.internal') : text;
}

function renderError() {
  $('#error-title').textContent = errorText(state.error);
  const { code, message } = state.error;
  $('#error-detail').textContent = message && message !== code ? message : '';
}

// ---------- 报告 ----------

function renderReport() {
  const r = state.report;
  const draws = [];
  let num = 0;

  const section = (key, ...content) => h('section', { class: 'sec', 'aria-labelledby': `h-${key}` },
    h('header', { class: 'sec__head' },
      h('span', { class: 'sec__num', 'aria-hidden': 'true' }, String(++num).padStart(2, '0')),
      h('h2', { class: 'sec__title', id: `h-${key}` }, t(`sec.${key}`))),
    ...content);

  // 图表卡片：标题 + 图例 + 图表 + 可切换的表格视图
  const figure = ({ title, legendItems, draw, table, note }) => {
    const host = h('div', { class: 'chart' });
    const tableView = dataTable(table.columns, table.rows);
    tableView.hidden = true;
    const toggle = h('button', { type: 'button', class: 'link', 'aria-pressed': 'false' }, t('chart.table'));
    toggle.addEventListener('click', () => {
      const showTable = tableView.hidden;
      tableView.hidden = !showTable;
      host.hidden = showTable;
      toggle.setAttribute('aria-pressed', String(showTable));
      toggle.textContent = t(showTable ? 'chart.chart' : 'chart.table');
    });
    draws.push(() => draw(host));
    return h('figure', { class: 'fig' },
      h('figcaption', { class: 'fig__head' }, h('h3', { class: 'fig__title' }, title), toggle),
      legend(legendItems ?? []), host, tableView, note && h('p', { class: 'note' }, note));
  };

  const since = r.recent_since;
  const dim = (role, period) => r.dimensions.find((d) => d.role === role && d.period === period);
  const off = !r.authorship.enabled;
  const col = (key, num) => ({ label: t(key), num });

  // 01 概览：Scholar 官方指标 + 论文数
  const recent = dim('all', 'recent');
  const kpis = [
    ['citations', r.official.citations.all, r.official.citations.recent],
    ['h_index', r.official.h_index.all, r.official.h_index.recent],
    ['i10_index', r.official.i10_index.all, r.official.i10_index.recent],
    ['publications', r.totals.publications, recent.papers],
    ['nature_index', r.totals.nature_index, recent.nature_index],
  ];
  const overview = section('overview',
    h('div', { class: 'kpis' }, kpis.map(([key, all, rec]) => h('div', { class: 'kpi' },
      h('p', { class: 'eyebrow' }, t(`kpi.${key}`)),
      h('p', { class: 'kpi__value' }, fmt(all)),
      h('p', { class: 'kpi__sub' }, t('kpi.since', { year: since, value: fmt(rec) }))))),
    h('p', { class: 'note' }, t('kpi.note', { year: since })));

  // 02 六维统计：3 种作者身份 × 2 个时间段，数字下方是按列归一化的条
  const max = Object.fromEntries(METRICS.map((m) => [m, Math.max(1, ...r.dimensions.map((d) => d[m]))]));
  const matrixRow = (role, period) => {
    const d = dim(role, period);
    const disabled = off && role !== 'all';
    return h('tr', { class: period === 'recent' ? 'recent is-last' : null },
      period === 'all' && h('th', { scope: 'rowgroup', rowspan: 2, class: 'role role-col' }, t(`role.${role}`)),
      h('th', { scope: 'row', class: 'period' }, t(`period.${period}`, { year: since })),
      METRICS.map((m) => h('td', { class: disabled ? 'cell--off' : null },
        h('span', { class: 'cell__num' }, disabled ? '—' : fmt(d[m])),
        !disabled && h('span', { class: 'cell__bar', style: `width:${(d[m] / max[m]) * 100}%` }))));
  };
  // 窄屏隐藏跨行的身份列，改用 group-row 单独一行显示身份名
  const matrixRows = ROLES.flatMap((role) => [
    h('tr', { class: 'group-row' }, h('th', { scope: 'rowgroup', colspan: METRICS.length + 1 }, t(`role.${role}`))),
    matrixRow(role, 'all'),
    matrixRow(role, 'recent'),
  ]);
  const dimensions = section('dimensions',
    legend([{ label: t('legend.all'), color: INK }, { label: t('legend.recent', { year: since }), color: ACCENT }]),
    h('div', { class: 'matrix-wrap' }, h('table', { class: 'matrix' },
      h('thead', {}, h('tr', {}, h('td', { class: 'role-col' }), h('td'), METRICS.map((m) => h('th', { scope: 'col' }, t(`metric.${m}`))))),
      h('tbody', {}, matrixRows))),
    h('p', { class: 'note' }, t('dims.note', { year: since }), off && ` ${t('dims.disabled')}`));

  // 03 时间线
  const cpy = r.citations_per_year;
  const ppy = r.publications_per_year;
  const thisYear = new Date(r.generated_at).getFullYear();
  const timeline = section('timeline', h('div', { class: 'grid-2' },
    figure({
      title: t('chart.cpy'),
      draw: (host) => columnChart(host, {
        labels: cpy.map((d) => String(d.year)), labelMax: true, fmt, ariaLabel: t('chart.cpy'),
        series: [{ label: t('col.citations'), color: INK, values: cpy.map((d) => d.citations) }],
      }),
      table: { columns: [col('col.year'), col('col.citations', true)], rows: cpy.map((d) => [d.year, fmt(d.citations)]) },
      note: cpy.at(-1)?.year === thisYear ? t('chart.cpy.note', { year: thisYear }) : null,
    }),
    figure({
      title: t('chart.ppy'),
      legendItems: [{ label: t('legend.ni'), color: ACCENT }, { label: t('legend.other'), color: INK }],
      draw: (host) => columnChart(host, {
        labels: ppy.map((d) => String(d.year)), stacked: true, fmt, ariaLabel: t('chart.ppy'),
        series: [
          { label: t('legend.ni'), color: ACCENT, values: ppy.map((d) => d.nature_index) },
          { label: t('legend.other'), color: INK, values: ppy.map((d) => d.total - d.nature_index) },
        ],
      }),
      table: {
        columns: [col('col.year'), col('legend.ni', true), col('col.papers', true)],
        rows: ppy.map((d) => [d.year, fmt(d.nature_index), fmt(d.total)]),
      },
    })));

  // 04 影响力：按被引排序的论文，前 h 篇（h 核心）高亮，对角线 y = 排名
  const hIndex = dim('all', 'all').h_index;
  const ranked = [...r.publications].sort((a, b) => b.citations - a.citations);
  const top = ranked.slice(0, Math.max(2 * hIndex, 20));
  const hColor = (i) => (i < hIndex ? ACCENT : CONTEXT);
  const impact = section('impact', figure({
    title: t('chart.h', { n: top.length }),
    legendItems: [
      { label: t('legend.hcore'), color: ACCENT },
      { label: t('legend.rest'), color: CONTEXT },
      { label: t('legend.diagonal'), color: INK, line: true },
    ],
    draw: (host) => columnChart(host, {
      labels: top.map((_, i) => String(i + 1)), height: 300, fmt, diagonal: true, labelWidth: 26,
      ariaLabel: t('chart.h', { n: top.length }),
      series: [{ label: t('col.citations'), color: hColor, values: top.map((p) => p.citations) }],
      marker: { index: hIndex, label: `h = ${hIndex}` },
      tooltip: (i) => ({
        title: `#${i + 1} · ${top[i].title}`,
        rows: [{ color: hColor(i), value: fmt(top[i].citations), label: t('col.citations') }],
      }),
    }),
    table: {
      columns: [col('col.rank', true), col('col.title'), col('col.year', true), col('col.citations', true)],
      rows: top.map((p, i) => [i + 1, p.title, p.year ?? '—', fmt(p.citations)]),
    },
    note: t('chart.h.note', { h: hIndex }),
  }));

  // 05 作者身份
  const a = r.authorship;
  const positions = ['first', 'last', 'middle', 'unknown', 'unmatched'].map((k) => ({
    label: t(`pos.${k}`), value: a.positions[k], color: k === 'unknown' || k === 'unmatched' ? CONTEXT : INK,
  }));
  const stat = (label, value) => h('div', { class: 'stat' },
    h('p', { class: 'eyebrow' }, label),
    h('p', { class: 'stat__value' }, fmt(value)),
    h('p', { class: 'stat__sub' }, t('auth.of', { total: fmt(r.totals.publications) })));
  const authorship = section('authorship', off ? h('p', { class: 'empty' }, t('auth.disabled')) : [
    h('div', { class: 'grid-2' },
      figure({
        title: t('chart.positions'),
        draw: (host) => hbarChart(host, positions, { fmt }),
        table: { columns: [col('col.position'), col('col.count', true)], rows: positions.map((d) => [d.label, fmt(d.value)]) },
      }),
      h('div', { class: 'stats' }, stat(t('auth.corresponding'), a.corresponding), stat(t('auth.matched'), a.matched))),
    a.status === 'limited' && h('p', { class: 'notice' }, t('auth.limited')),
    a.status === 'error' && h('p', { class: 'notice' }, t('auth.error')),
    h('p', { class: 'note' }, t('auth.note')),
  ]);

  // 06 Nature Index
  const ni = r.nature_index;
  const cats = ni.categories.map((c) => ({ label: category(c.name), value: c.count, color: ACCENT }));
  const niItem = (p) => h('li', { class: 'ni-item' },
    h('span', { class: 'ni-item__year' }, p.year ?? '—'),
    h('div', {},
      h('p', { class: 'ni-item__title' }, safeUrl(p.url) ? external(p.url, p.title) : p.title),
      h('p', { class: 'ni-item__journal' }, p.journal)),
    h('span', { class: 'ni-item__cites' }, fmt(p.citations), h('small', {}, t('col.citations'))));
  const niList = h('ol', { class: 'ni-list' }, (state.niAll ? ni.papers : ni.papers.slice(0, NI_PAGE)).map(niItem));
  const natureIndex = section('nature_index',
    ni.papers.length ? h('div', { class: 'grid-2' },
      h('div', {},
        h('div', { class: 'fig__head' }, h('h3', { class: 'fig__title' }, t('ni.papers'))),
        niList,
        ni.papers.length > niList.children.length && h('div', { class: 'actions' }, h('button', {
          class: 'btn', type: 'button',
          onclick: (e) => { state.niAll = true; niList.replaceChildren(...ni.papers.map(niItem)); e.currentTarget.remove(); },
        }, t('ni.all', { n: fmt(ni.papers.length) }), ' ↓'))),
      figure({
        title: t('chart.categories'),
        draw: (host) => hbarChart(host, cats, { fmt }),
        table: { columns: [col('col.category'), col('col.papers', true)], rows: cats.map((d) => [d.label, fmt(d.value)]) },
        note: t('ni.multi'),
      })) : h('p', { class: 'empty' }, t('ni.none')),
    ni.near_misses.length > 0 && h('div', { class: 'notice' }, t('ni.near'),
      h('ul', {}, ni.near_misses.map((x) => h('li', {}, `“${x.venue}” ≈ “${x.journal}”`)))),
    h('p', { class: 'note' }, t('ni.note')));

  // 07 期刊与会议
  const venueItems = r.venues.map((v) => ({
    label: [v.name, v.nature_index && h('span', { class: 'tag-ni' }, 'NI')],
    value: v.count, color: v.nature_index ? ACCENT : INK,
  }));
  const venues = section('venues', figure({
    title: t('chart.venues', { n: r.venues.length }),
    legendItems: [{ label: t('legend.ni'), color: ACCENT }, { label: t('legend.other'), color: INK }],
    draw: (host) => hbarChart(host, venueItems, { fmt }),
    table: {
      columns: [col('col.venue'), col('legend.ni'), col('col.papers', true)],
      rows: r.venues.map((v) => [v.name, v.nature_index ? '✓' : '', fmt(v.count)]),
    },
  }));

  // 08 论文明细
  const publications = section('publications', ...publicationsView(r, off));

  // 09 引用地图（安装了 citation-map 时才出现）
  const map = mapView(r, section);

  $('#report').replaceChildren(profileView(r),
    h('div', { class: 'wrap' }, overview, dimensions, timeline, impact, authorship, natureIndex, venues, publications, map));
  draws.forEach((draw) => draw());
}

function profileView(r) {
  const p = r.profile;
  return h('header', { class: 'profile wrap' },
    h('div', {},
      h('p', { class: 'eyebrow' }, `${t('report.id')} · `, h('span', { class: 'id' }, r.scholar_id),
        r.demo && h('span', { class: 'badge' }, t('report.demo'))),
      h('h1', { class: 'profile__name', id: 'report-name', tabindex: '-1' }, p.name || r.scholar_id),
      p.affiliation && h('p', { class: 'profile__aff' }, p.affiliation),
      p.interests?.length > 0 && h('ul', { class: 'tags' }, p.interests.map((x) => h('li', {}, x))),
      h('div', { class: 'actions' },
        safeUrl(p.url) && h('a', { class: 'btn', href: p.url, target: '_blank', rel: 'noopener noreferrer' }, t('report.scholar'), ' ↗'),
        safeUrl(p.homepage) && h('a', { class: 'btn', href: p.homepage, target: '_blank', rel: 'noopener noreferrer' }, t('report.homepage'), ' ↗'),
        h('a', { class: 'btn', href: api.csvUrl(r.scholar_id), download: '' }, t('report.csv'), ' ↓'),
        h('button', { class: 'btn', type: 'button', onclick: () => start(r.scholar_id, { refresh: true }) }, t('report.refresh'), ' ↻')),
      h('p', { class: 'meta' }, t('report.generated', { date: fmtDate(r.generated_at) }))),
    safeUrl(p.photo) && h('img', {
      class: 'profile__photo', src: p.photo, alt: '', referrerpolicy: 'no-referrer', onerror: (e) => e.target.remove(),
    }));
}

function publicationsView(r, off) {
  const p = state.pubs;
  const body = h('div');
  const refresh = () => body.replaceChildren(...publicationsBody(r, off, refresh));
  const filters = ['all', 'ni', ...(off ? [] : ['first_corr', 'first_lastcorr'])];
  const seg = h('div', { class: 'seg seg--wrap', role: 'group', 'aria-label': t('filter.label') },
    filters.map((f) => h('button', {
      type: 'button',
      'aria-pressed': String(p.filter === f),
      onclick: () => {
        p.filter = f;
        p.limit = PAGE;
        seg.querySelectorAll('button').forEach((b, i) => b.setAttribute('aria-pressed', String(filters[i] === f)));
        refresh();
      },
    }, t(`filter.${f}`))));
  const search = h('input', {
    type: 'search', value: p.q, placeholder: t('pubs.search'), 'aria-label': t('pubs.search'),
    oninput: (e) => { p.q = e.target.value; p.limit = PAGE; refresh(); },
  });
  const sort = h('select', { 'aria-label': t('pubs.sort'), onchange: (e) => { p.sort = e.target.value; refresh(); } },
    ['citations', 'year'].map((s) => h('option', { value: s, selected: p.sort === s }, t(`pubs.sort.${s}`))));
  refresh();
  return [h('div', { class: 'controls' }, search, seg, sort), body];
}

function publicationsBody(r, off, refresh) {
  const p = state.pubs;
  const q = p.q.trim().toLowerCase();
  let list = r.publications.filter((x) => (p.filter === 'all' || (p.filter === 'ni' ? x.nature_index : x[p.filter]))
    && (!q || x.title.toLowerCase().includes(q) || x.venue.toLowerCase().includes(q)));
  if (p.sort === 'year') list = [...list].sort((a, b) => (b.year ?? 0) - (a.year ?? 0) || b.citations - a.citations);
  if (!list.length) return [h('p', { class: 'empty' }, t('pubs.empty'))];
  const shown = list.slice(0, p.limit);
  const table = h('div', { class: 'table-wrap' }, h('table', { class: 'pubs' },
    h('thead', {}, h('tr', {},
      h('th', { scope: 'col', class: 'num' }, '#'),
      h('th', { scope: 'col' }, t('col.title')),
      h('th', { scope: 'col', class: 'num' }, t('col.year')),
      h('th', { scope: 'col', class: 'num' }, t('col.citations')),
      !off && h('th', { scope: 'col' }, t('col.position')),
      !off && h('th', { scope: 'col' }, t('col.corresponding')))),
    h('tbody', {}, shown.map((x, i) => h('tr', {},
      h('td', { class: 'rank num' }, i + 1),
      h('td', {},
        h('div', { class: 't' }, safeUrl(x.url) ? external(x.url, x.title) : x.title,
          x.nature_index && h('span', { class: 'tag-ni', title: x.ni_journal }, 'NI')),
        h('div', { class: 'v' }, x.venue || '—')),
      h('td', { class: 'num' }, x.year ?? '—'),
      h('td', { class: 'num c' }, fmt(x.citations)),
      !off && h('td', {}, x.position ? t(`short.${x.position}`) : '—'),
      !off && h('td', {}, x.corresponding ? '✓' : ''))))));
  const foot = h('div', { class: 'pubs__foot' },
    h('span', {}, t('pubs.count', { shown: fmt(shown.length), total: fmt(list.length) })),
    list.length > shown.length && h('button', {
      class: 'btn', type: 'button', onclick: () => { p.limit += 50; refresh(); },
    }, t('pubs.more'), ' ↓'));
  return [table, foot];
}

function mapView(r, section) {
  const cm = r.citation_map ?? {};
  if (!cm.available && !cm.ready) return null;
  if (cm.ready) {
    return section('map',
      h('iframe', { class: 'map-frame', src: api.mapUrl(r.scholar_id), title: t('sec.map'), loading: 'lazy', sandbox: 'allow-scripts allow-popups' }),
      h('p', { class: 'note' }, external(api.mapUrl(r.scholar_id), t('map.open'), ' ↗')));
  }
  const status = h('p', { class: 'note', 'aria-live': 'polite' }, state.mapRunning ? t('map.running') : '');
  const button = h('button', { class: 'btn', type: 'button', disabled: state.mapRunning }, t('map.generate'), ' →');
  button.addEventListener('click', async () => {
    state.mapRunning = true;
    button.disabled = true;
    status.textContent = t('map.running');
    try {
      let job = await api.createMap(r.scholar_id);
      while (job.status === 'running') {
        await sleep(3000);
        job = await api.getJob(job.id);
      }
      if (job.status === 'error') throw job.error;
      state.mapRunning = false;
      if (state.report?.scholar_id === r.scholar_id) {
        state.report = await api.getReport(r.scholar_id);
        renderReport();
      }
    } catch (e) {
      state.mapRunning = false;
      button.disabled = false;
      status.textContent = errorText({ code: e.code ?? 'map_failed' });
    }
  });
  return section('map', h('p', { class: 'note' }, t('map.desc')), h('div', { class: 'actions' }, button), status);
}

// ---------- 初始化 ----------

function renderBand() {
  const items = [...t('band'), ...t('band')];
  const seq = items.flatMap((x) => [h('span', {}, x), h('span', {}, ' → ')]);
  $('#band').replaceChildren(...seq, ...seq.map((node) => node.cloneNode(true)));
}

async function openFromUrl(id) {
  $('#query').value = id;
  try {
    showReport(await api.getReport(id));  // 已缓存：直接打开
  } catch {
    start(id);
  }
}

function init() {
  setLang(initialLang());
  renderBand();
  onLangChange(() => {
    renderBand();
    const view = document.body.dataset.view;
    if (view === 'report' && state.report) renderReport();
    if (view === 'loading') renderStatus();
    if (view === 'error') renderError();
    if (!$('#query-error').hidden) $('#query-error').textContent = t('form.invalid');
  });
  document.querySelectorAll('[data-lang]').forEach((b) => b.addEventListener('click', () => setLang(b.dataset.lang)));
  $('#search').addEventListener('submit', (e) => {
    e.preventDefault();
    start($('#query').value);
  });
  $('#demo').addEventListener('click', () => start('demo'));
  $('#retry').addEventListener('click', () => start(state.query));
  setInterval(() => document.body.dataset.view === 'loading' && updateElapsed(), 1000);

  const id = new URLSearchParams(location.search).get('id');
  if (id) openFromUrl(id);
}

init();
