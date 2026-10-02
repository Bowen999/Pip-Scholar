// 极简 DOM 构造：字符串子节点一律作为文本插入（防 XSS），属性值 null/false 时跳过。
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs ?? {})) {
    if (value == null || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key === 'style') el.style.cssText = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else el.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

// 只允许 http(s) 链接（数据来自外部抓取）
export const safeUrl = (url) => (/^https?:\/\//i.test(url ?? '') ? url : null);
