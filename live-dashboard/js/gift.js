import { debounce, escapeHtml, formatNumber, formatTime, safeText, VirtualList } from "./utils.js";

export class GiftView {
  constructor() {
    this.cache = null;
    this.filtered = [];
    this.list = new VirtualList(document.getElementById("giftList"), { rowHeight: 62, renderRow: renderGiftRow });
    this.userInput = document.getElementById("giftUserSearch");
    this.nameInput = document.getElementById("giftNameSearch");
    this.sortInput = document.getElementById("giftSort");
    const refresh = debounce(() => this.applyFilters(), 160);
    this.userInput.addEventListener("input", refresh);
    this.nameInput.addEventListener("input", refresh);
    this.sortInput.addEventListener("change", () => this.applyFilters());
  }

  setCache(cache) {
    this.cache = cache;
    this.userInput.value = "";
    this.nameInput.value = "";
    this.applyFilters();
  }

  setRecords(records) {
    this.filtered = records || [];
    this.list.setData(this.filtered);
    document.getElementById("giftCountLabel").textContent = `${this.filtered.length.toLocaleString("zh-CN")} 条`;
  }

  applyFilters() {
    if (!this.cache) return this.setRecords([]);
    const user = this.userInput.value.trim().toLowerCase();
    const name = this.nameInput.value.trim().toLowerCase();
    let rows = this.cache.gifts;
    if (user) rows = rows.filter((item) => safeText(item.username, "").toLowerCase().includes(user) || safeText(item.userId, "").toLowerCase().includes(user));
    if (name) rows = rows.filter((item) => safeText(item.giftName, "").toLowerCase().includes(name));
    rows = rows.slice();
    if (this.sortInput.value === "time-asc") rows.sort((a, b) => a.time - b.time);
    else if (this.sortInput.value === "value-desc") rows.sort((a, b) => b.value - a.value);
    else rows.sort((a, b) => b.time - a.time);
    this.setRecords(rows);
  }
}

export function renderGiftRow(item) {
  return `<div class="list-row">
    <div class="row-meta"><span>${escapeHtml(formatTime(item.time))}</span><span class="row-value">${escapeHtml(formatNumber(item.value))}</span></div>
    <div class="row-user">${escapeHtml(item.username)} · ${escapeHtml(item.giftName)} x ${escapeHtml(item.count)}</div>
    <div class="row-content">用户ID：${escapeHtml(item.userId || "-")}</div>
  </div>`;
}
