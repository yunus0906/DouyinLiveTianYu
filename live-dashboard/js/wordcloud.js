import { escapeHtml, formatNumber } from "./utils.js";

export class WordRankView {
  constructor(onWordClick) {
    this.el = document.getElementById("wordRank");
    this.onWordClick = onWordClick;
  }

  render(words) {
    this.el.innerHTML = words.map((item, index) => `<button class="rank-item" type="button" data-word="${escapeHtml(item.name)}">
      <span class="rank-no">#${index + 1}</span>
      <span class="rank-name">${escapeHtml(item.name)}</span>
      <span class="rank-value">${formatNumber(item.value)}</span>
    </button>`).join("") || `<div class="empty-state"><strong>暂无词频</strong><span>没有可分析的评论。</span></div>`;
    this.el.onclick = (event) => {
      const btn = event.target.closest("[data-word]");
      if (!btn) return;
      const item = words.find((word) => word.name === btn.dataset.word);
      if (item) this.onWordClick(item);
    };
  }
}
