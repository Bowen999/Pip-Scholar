// 后端接口。前端与后端同源；单独部署的前端（如 Figma 导出的项目）把 BASE 改成 'http://127.0.0.1:8000'。
const BASE = '';
const enc = encodeURIComponent;

export class ApiError extends Error {
  constructor(code, message = '') {
    super(message || code);
    this.code = code;
  }
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(BASE + path, options);
  } catch {
    throw new ApiError('network');
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data.error?.code ?? 'internal', data.error?.message ?? res.statusText);
  return data;
}

const post = (path, body) => request(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: body ? JSON.stringify(body) : undefined,
});

export const createReport = (query, { openalex = true, refresh = false } = {}) =>
  post('/api/reports', { query, openalex, refresh });
export const getJob = (id) => request(`/api/jobs/${enc(id)}`);
export const getReport = (sid) => request(`/api/reports/${enc(sid)}`);
export const createMap = (sid) => post(`/api/reports/${enc(sid)}/map`);
export const csvUrl = (sid) => `${BASE}/api/reports/${enc(sid)}/publications.csv`;
export const mapUrl = (sid) => `${BASE}/api/reports/${enc(sid)}/map`;
