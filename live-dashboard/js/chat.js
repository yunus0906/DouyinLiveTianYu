import { debounce, escapeHtml, formatTime, safeText, VirtualList } from "./utils.js";

export class ChatView {
  constructor(onReady) {
    this.cache = null;
    this.filtered = [];
    this.list = new VirtualList(document.getElementById("chatList"), { rowHeight: 58, renderRow: renderChatRow });
    this.userInput = document.getElementById("chatUserSearch");
    this.keywordInput = document.getElementById("chatKeywordSearch");
    this.sortInput = document.getElementById("chatSort");
    const refresh = debounce(() => this.applyFilters(), 160);
    this.userInput.addEventListener("input", refresh);
    this.keywordInput.addEventListener("input", refresh);
    this.sortInput.addEventListener("change", () => this.applyFilters());
    if (onReady) onReady(this);
  }

  setCache(cache) {
    this.cache = cache;
    this.userInput.value = "";
    this.keywordInput.value = "";
    this.applyFilters();
  }

  setRecords(records) {
    this.filtered = records || [];
    this.list.setData(this.filtered);
    document.getElementById("chatCountLabel").textContent = `${this.filtered.length.toLocaleString("zh-CN")} 条`;
  }

  applyFilters() {
    if (!this.cache) return this.setRecords([]);
    const user = this.userInput.value.trim().toLowerCase();
    const keyword = this.keywordInput.value.trim().toLowerCase();
    const desc = this.sortInput.value === "desc";
    let rows = this.cache.chat;
    if (user) rows = rows.filter((item) => safeText(item.username, "").toLowerCase().includes(user) || safeText(item.userId, "").toLowerCase().includes(user));
    if (keyword) rows = rows.filter((item) => safeText(item.content, "").toLowerCase().includes(keyword));
    rows = desc ? rows.slice().reverse() : rows.slice();
    this.setRecords(rows);
  }
}

export function renderChatRow(item) {
  return `<div class="list-row">
    <div class="row-meta"><span>${escapeHtml(formatTime(item.time))}</span><span>${escapeHtml(item.userId)}</span></div>
    <div class="row-user">${escapeHtml(item.username)}</div>
    <div class="row-content">${escapeHtml(item.content)}</div>
  </div>`;
}
