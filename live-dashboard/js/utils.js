/** @param {number} ms */
export const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

export function $(selector, root = document) {
  return root.querySelector(selector);
}

export function $all(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

export function debounce(fn, wait = 180) {
  let timer = 0;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), wait);
  };
}

export function pickField(columns, candidates) {
  const lowerMap = new Map(columns.map((column) => [String(column).toLowerCase(), column]));
  for (const name of candidates) {
    const found = lowerMap.get(String(name).toLowerCase());
    if (found) return found;
  }
  return "";
}

export function pickTable(schema, hints) {
  const tableNames = Object.keys(schema.tables);
  const lowerMap = new Map(tableNames.map((name) => [name.toLowerCase(), name]));
  for (const hint of hints) {
    if (lowerMap.has(hint.toLowerCase())) return lowerMap.get(hint.toLowerCase());
  }
  return tableNames.find((name) => hints.some((hint) => name.toLowerCase().includes(hint.toLowerCase()))) || "";
}

export function normalizeTime(value) {
  if (value == null || value === "") return 0;
  if (typeof value === "string" && /\d{4}-\d{1,2}-\d{1,2}/.test(value)) {
    const parsed = Date.parse(value.replace(/-/g, "/"));
    return Number.isFinite(parsed) ? parsed : 0;
  }
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) return 0;
  if (number > 1000000000000) return number;
  if (number > 10000000000) return number;
  return number * 1000;
}

export function minuteKey(ms) {
  return ms ? Math.floor(ms / 60000) * 60000 : 0;
}

export function formatTime(ms, pattern = "YYYY-MM-DD HH:mm:ss") {
  if (!ms) return "-";
  return window.dayjs ? window.dayjs(ms).format(pattern) : new Date(ms).toLocaleString();
}

export function formatMinute(ms) {
  return formatTime(ms, "HH:mm");
}

export function formatNumber(value) {
  const n = Number(value) || 0;
  if (Math.abs(n) >= 100000000) return `${(n / 100000000).toFixed(2)}亿`;
  if (Math.abs(n) >= 10000) return `${(n / 10000).toFixed(1)}万`;
  return n.toLocaleString("zh-CN");
}

export function formatDuration(start, end) {
  if (!start || !end || end < start) return "-";
  const total = Math.floor((end - start) / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${h}时${String(m).padStart(2, "0")}分${String(s).padStart(2, "0")}秒`;
}

export function parseNumericText(value) {
  if (value == null) return 0;
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const text = String(value).replace(/,/g, "").trim();
  const match = text.match(/([\d.]+)\s*([万亿wW]?)/);
  if (!match) return 0;
  const base = Number(match[1]);
  if (!Number.isFinite(base)) return 0;
  if (match[2] === "亿") return base * 100000000;
  if (match[2] === "万" || match[2].toLowerCase() === "w") return base * 10000;
  return base;
}

export function safeText(value, fallback = "-") {
  if (value == null || value === "") return fallback;
  return String(value);
}

export function escapeHtml(value) {
  return safeText(value, "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    "\"": "&quot;"
  }[char]));
}

export function animateNumber(el, endValue, formatter = formatNumber) {
  const target = Number(endValue) || 0;
  const start = performance.now();
  const duration = 720;
  const step = (now) => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = formatter(Math.round(target * eased));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export class VirtualList {
  constructor(container, options) {
    this.container = container;
    this.rowHeight = options.rowHeight || 58;
    this.renderRow = options.renderRow;
    this.overscan = options.overscan || 8;
    this.data = [];
    this.spacer = document.createElement("div");
    this.spacer.className = "virtual-spacer";
    this.content = document.createElement("div");
    this.content.className = "virtual-content";
    this.container.innerHTML = "";
    this.container.append(this.spacer, this.content);
    this.onScroll = () => this.render();
    this.container.addEventListener("scroll", this.onScroll, { passive: true });
  }

  setData(data) {
    this.data = Array.isArray(data) ? data : [];
    this.spacer.style.height = `${this.data.length * this.rowHeight}px`;
    this.container.scrollTop = 0;
    this.render();
  }

  render() {
    if (!this.data.length) {
      this.content.style.transform = "translateY(0)";
      this.content.innerHTML = document.getElementById("emptyStateTemplate")?.innerHTML || "";
      this.spacer.style.height = "120px";
      return;
    }
    this.spacer.style.height = `${this.data.length * this.rowHeight}px`;
    const viewport = this.container.clientHeight || 300;
    const start = Math.max(0, Math.floor(this.container.scrollTop / this.rowHeight) - this.overscan);
    const count = Math.ceil(viewport / this.rowHeight) + this.overscan * 2;
    const end = Math.min(this.data.length, start + count);
    const rows = [];
    for (let i = start; i < end; i += 1) rows.push(this.renderRow(this.data[i], i));
    this.content.style.transform = `translateY(${start * this.rowHeight}px)`;
    this.content.innerHTML = rows.join("");
  }
}

export function topN(map, n = 100) {
  return Array.from(map.values()).sort((a, b) => (b.value || b.count || 0) - (a.value || a.count || 0)).slice(0, n);
}
