// 零依赖 SVG 图表：柱状图（单系列 / 堆叠）、横向条形图、图例与表格视图。
// 规范：柱宽 ≤ 24px、数据端 4px 圆角、堆叠段之间 2px 间隙、细网格线、悬停与键盘（←/→）提示。
import { h } from './dom.js';

const NS = 'http://www.w3.org/2000/svg';

function svgEl(tag, attrs, parent) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) el.setAttribute(k, v);
  parent?.append(el);
  return el;
}

function niceScale(max, ticks = 4) {
  if (!(max > 0)) return { max: 1, step: 1 };
  const raw = max / ticks;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = Math.max(1, [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw));
  return { max: Math.ceil(max / step) * step, step };
}

// 顶部圆角、底部直角的柱子
function barPath(x, y, w, hgt, r) {
  r = Math.min(r, w / 2, hgt);
  return `M${x},${y + hgt}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + hgt}Z`;
}

function tooltipContent(title, rows) {
  return [
    h('div', { class: 'tooltip__title' }, title),
    rows.map((r) => h('div', { class: 'tooltip__row' },
      h('span', { class: 'key key--line', style: `background:${r.color}` }),
      h('strong', {}, r.value),
      h('span', {}, r.label))),
  ];
}

/**
 * 柱状图。
 * opts: labels[], series[{label, color | (i)=>color, values[]}], stacked, height, fmt,
 *       labelMax（标注最大值）, diagonal（y = 排名 参考线）, marker{index, label},
 *       tooltip(i) => {title, rows[{color, value, label}]}, ariaLabel
 */
export function columnChart(host, opts) {
  const fmt = opts.fmt ?? String;
  const color = (se, i) => (typeof se.color === 'function' ? se.color(i) : se.color);
  let lastWidth = 0;

  const draw = () => {
    const W = Math.max(280, Math.round(host.clientWidth));
    if (W === lastWidth) return;
    lastWidth = W;
    host.replaceChildren();

    const n = opts.labels.length;
    if (!n) {
      host.replaceChildren(h('p', { class: 'note' }, '—'));
      return;
    }
    const H = opts.height ?? 240;
    const m = { t: 22, r: 10, b: 26, l: 42 };
    const pw = W - m.l - m.r;
    const ph = H - m.t - m.b;
    const totals = opts.labels.map((_, i) => (opts.stacked
      ? opts.series.reduce((sum, se) => sum + se.values[i], 0)
      : Math.max(...opts.series.map((se) => se.values[i]))));
    const { max, step } = niceScale(Math.max(...totals));
    const y = (v) => m.t + ph - (v / max) * ph;
    const bw = pw / Math.max(n, 1);
    const barW = Math.min(24, Math.max(1, bw - Math.max(2, bw * 0.3)));

    const svg = svgEl('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: 'img', tabindex: 0, 'aria-label': opts.ariaLabel }, host);
    for (let v = 0; v <= max + 1e-9; v += step) {
      svgEl('line', { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: v === 0 ? 'axis' : 'grid' }, svg);
      svgEl('text', { x: m.l - 8, y: y(v), 'text-anchor': 'end', 'dominant-baseline': 'middle' }, svg).textContent = fmt(v);
    }
    const every = Math.max(1, Math.ceil((n * (opts.labelWidth ?? 36)) / pw));
    opts.labels.forEach((label, i) => {
      if ((n - 1 - i) % every) return;  // 从最新一项往前隔项标注
      svgEl('text', { x: m.l + bw * (i + 0.5), y: H - 6, 'text-anchor': 'middle' }, svg).textContent = label;
    });

    const band = svgEl('rect', { y: m.t, width: bw, height: ph, class: 'hover-band', visibility: 'hidden' }, svg);

    const maxIndex = totals.indexOf(Math.max(...totals));
    opts.labels.forEach((_, i) => {
      const x = m.l + bw * i + (bw - barW) / 2;
      let base = y(0);
      const visible = opts.series.map((se) => se.values[i] > 0);
      opts.series.forEach((se, k) => {
        const v = se.values[i];
        if (!(v > 0)) return;
        const top = opts.stacked ? base - (v / max) * ph : y(v);
        const bottom = opts.stacked && base !== y(0) ? base - 2 : base;  // 段间 2px 间隙
        if (bottom - top >= 0.5) {
          const isTop = !opts.stacked || !visible.slice(k + 1).some(Boolean);
          const d = isTop ? barPath(x, top, barW, bottom - top, 4) : `M${x},${top}H${x + barW}V${bottom}H${x}Z`;
          svgEl('path', { d, style: `fill:${color(se, i)}` }, svg);
        }
        base = top;
      });
    });

    if (opts.labelMax && totals[maxIndex] > 0) {
      svgEl('text', { x: m.l + bw * (maxIndex + 0.5), y: y(totals[maxIndex]) - 7, 'text-anchor': 'middle', class: 'value-label' }, svg)
        .textContent = fmt(totals[maxIndex]);
    }
    if (opts.diagonal) {
      const k = Math.min(n, max);
      svgEl('line', { x1: m.l, y1: y(0), x2: m.l + bw * k, y2: y(k), class: 'ref' }, svg);
    }
    if (opts.marker) {
      const mx = m.l + bw * opts.marker.index;
      svgEl('line', { x1: mx, x2: mx, y1: m.t - 6, y2: y(0), class: 'marker' }, svg);
      const label = svgEl('text', { x: mx + 6, y: m.t + 4, class: 'marker-label' }, svg);
      label.textContent = opts.marker.label;
      if (mx + 70 > W) {
        label.setAttribute('text-anchor', 'end');
        label.setAttribute('x', mx - 6);
      }
    }

    // 提示框：悬停或键盘 ←/→
    const tip = h('div', { class: 'tooltip', hidden: true });
    host.append(tip);
    const content = opts.tooltip ?? ((i) => ({
      title: opts.labels[i],
      rows: opts.series.map((se) => ({ color: color(se, i), value: fmt(se.values[i]), label: se.label })).reverse(),
    }));
    let current = -1;
    const show = (i) => {
      current = i;
      band.setAttribute('x', m.l + bw * i);
      band.setAttribute('visibility', 'visible');
      const { title, rows } = content(i);
      tip.replaceChildren(...tooltipContent(title, rows));
      tip.hidden = false;
      const scale = svg.getBoundingClientRect().width / W || 1;
      const cx = (m.l + bw * (i + 0.5)) * scale;
      const left = cx + 14 + tip.offsetWidth > host.clientWidth ? cx - 14 - tip.offsetWidth : cx + 14;
      tip.style.left = `${Math.max(0, left)}px`;
      tip.style.top = `${m.t * scale}px`;
    };
    const hide = () => { tip.hidden = true; band.setAttribute('visibility', 'hidden'); };
    svg.addEventListener('pointermove', (e) => {
      const rect = svg.getBoundingClientRect();
      const i = Math.floor(((e.clientX - rect.left) * (W / rect.width) - m.l) / bw);
      if (i >= 0 && i < n) { if (i !== current || tip.hidden) show(i); } else hide();
    });
    svg.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', () => show(current >= 0 ? current : n - 1));
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        show(Math.min(n - 1, Math.max(0, current + (e.key === 'ArrowRight' ? 1 : -1))));
      } else if (e.key === 'Escape') hide();
    });
  };

  draw();
  const ro = new ResizeObserver(() => {
    if (!host.isConnected) { ro.disconnect(); return; }
    requestAnimationFrame(draw);
  });
  ro.observe(host);
}

/** 横向条形图：items[{label, value, color}]，数值直接标在条末端。 */
export function hbarChart(host, items, { fmt = String } = {}) {
  const max = Math.max(1, ...items.map((d) => d.value));
  host.replaceChildren(h('ul', { class: 'hbars' }, items.map((d) => h('li', { class: 'hbar' },
    h('span', { class: 'hbar__label' }, d.label),
    h('span', { class: 'hbar__plot' },
      d.value > 0 && h('span', { class: 'hbar__fill', style: `width:${(d.value / max) * 82}%;background:${d.color}` }),
      h('span', { class: 'hbar__value' }, fmt(d.value)))))));
}

/** 图例：items[{label, color, line}] */
export function legend(items) {
  return h('ul', { class: 'legend' }, items.map((d) => h('li', {},
    h('span', { class: d.line ? 'key key--line' : 'key', style: `background:${d.color}` }), d.label)));
}

/** 表格视图（图表的无障碍替代）：columns[{label, num}], rows[[...]] */
export function dataTable(columns, rows) {
  return h('div', { class: 'table-wrap' }, h('table', { class: 'datatable' },
    h('thead', {}, h('tr', {}, columns.map((c) => h('th', { scope: 'col', class: c.num ? 'num' : null }, c.label)))),
    h('tbody', {}, rows.map((row) => h('tr', {}, row.map((cell, i) => h('td', { class: columns[i].num ? 'num' : null }, cell)))))));
}
