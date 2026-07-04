import { escapeHtml, formatNumber, formatTime } from "./utils.js";

export class RankingView {
  constructor(callbacks) {
    this.callbacks = callbacks;
    this.giftList = document.getElementById("giftRankList");
    this.commentList = document.getElementById("commentRankList");
  }

  render(cache) {
    this.renderGiftRank(cache.giftUserRank);
    this.renderCommentRank(cache.commentRank);
  }

  renderGiftRank(rows) {
    this.giftList.innerHTML = rows.map((item) => `<button class="rank-item" type="button" data-gift-user="${escapeHtml(item.key)}">
      <span class="rank-no">#${item.rank}</span>
      <span><span class="rank-name">${escapeHtml(item.username)}</span><span class="rank-meta">礼物 ${formatNumber(item.count)} · 占比 ${(item.percent * 100).toFixed(1)}%</span></span>
      <span class="rank-value">${formatNumber(item.value)}</span>
    </button>`).join("") || emptyRank();
    this.giftList.onclick = (event) => {
      const btn = event.target.closest("[data-gift-user]");
      if (!btn) return;
      const item = rows.find((row) => row.key === btn.dataset.giftUser);
      if (item) this.callbacks.onGiftUser(item);
    };
  }

  renderCommentRank(rows) {
    this.commentList.innerHTML = rows.map((item) => `<button class="rank-item" type="button" data-comment-user="${escapeHtml(item.key)}">
      <span class="rank-no">#${item.rank}</span>
      <span><span class="rank-name">${escapeHtml(item.username)}</span><span class="rank-meta">${formatTime(item.firstTime, "HH:mm")} - ${formatTime(item.lastTime, "HH:mm")}</span></span>
      <span class="rank-value">${formatNumber(item.count)}</span>
    </button>`).join("") || emptyRank();
    this.commentList.onclick = (event) => {
      const btn = event.target.closest("[data-comment-user]");
      if (!btn) return;
      const item = rows.find((row) => row.key === btn.dataset.commentUser);
      if (item) this.callbacks.onCommentUser(item);
    };
  }
}

function emptyRank() {
  return `<div class="empty-state"><strong>暂无排行</strong><span>数据库中没有可统计记录。</span></div>`;
}
