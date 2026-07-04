import { LiveDatabase, AnalyticsBuilder } from "./database.js";
import { ChartManager } from "./charts.js";
import { ChatView } from "./chat.js";
import { GiftView } from "./gift.js";
import { RankingView } from "./ranking.js";
import { WordRankView } from "./wordcloud.js";
import { DashboardView } from "./dashboard.js";
import { formatNumber, sleep } from "./utils.js";

class LiveDashboardApp {
  constructor() {
    this.db = new LiveDatabase();
    this.dashboard = new DashboardView();
    this.charts = new ChartManager();
    this.chatView = new ChatView();
    this.giftView = new GiftView();
    this.currentTrend = "consume";
    this.cache = null;
    this.rankView = new RankingView({
      onGiftUser: (item) => this.dashboard.openGiftDrawer(`${item.username} 的礼物记录`, `共 ${formatNumber(item.count)} 件，价值 ${formatNumber(item.value)}`, item.records),
      onCommentUser: (item) => this.dashboard.openChatDrawer(`${item.username} 的聊天记录`, `共 ${formatNumber(item.count)} 条评论`, item.records)
    });
    this.wordRank = new WordRankView((item) => this.dashboard.openChatDrawer(`包含「${item.name}」的聊天`, `命中 ${formatNumber(item.value)} 次，最多展示 5000 条缓存记录`, item.records));
    this.bindEvents();
  }

  bindEvents() {
    const zone = document.getElementById("uploadZone");
    const input = document.getElementById("dbFile");
    zone.addEventListener("click", () => input.click());
    zone.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") input.click();
    });
    input.addEventListener("change", () => this.loadFile(input.files?.[0]));
    for (const eventName of ["dragenter", "dragover"]) {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        zone.classList.add("dragover");
      });
    }
    for (const eventName of ["dragleave", "drop"]) {
      zone.addEventListener(eventName, (event) => {
        event.preventDefault();
        zone.classList.remove("dragover");
      });
    }
    zone.addEventListener("drop", (event) => this.loadFile(event.dataTransfer?.files?.[0]));
    document.querySelectorAll("[data-trend]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-trend]").forEach((item) => item.classList.remove("active"));
        btn.classList.add("active");
        this.currentTrend = btn.dataset.trend;
        if (this.cache) this.charts.renderTrend(this.cache, this.currentTrend);
      });
    });
    document.getElementById("fullscreenPage").addEventListener("click", () => {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.();
      else document.exitFullscreen?.();
    });
    document.getElementById("resetFilters").addEventListener("click", () => this.resetFilters());
  }

  async loadFile(file) {
    if (!file) return;
    if (!/\.(db|sqlite|sqlite3)$/i.test(file.name)) {
      this.dashboard.setStatus("请选择 live.db / SQLite 文件", "error");
      return;
    }
    try {
      const start = performance.now();
      this.dashboard.setStatus(`正在解析 ${file.name}...`, "loading");
      await sleep(30);
      const schema = await this.db.open(file);
      this.dashboard.setStatus("正在构建分析缓存...", "loading");
      await sleep(30);
      this.cache = new AnalyticsBuilder(this.db).build();
      this.renderAll();
      const cost = Math.round(performance.now() - start);
      this.dashboard.setStatus(`解析完成：${file.name} · ${cost}ms`, "ready");
      this.dashboard.renderSchema(schema, this.cache.tableMap);
    } catch (error) {
      console.error(error);
      this.dashboard.setStatus(`解析失败：${error.message}`, "error");
    }
  }

  renderAll() {
    if (!this.cache) return;
    this.dashboard.renderKpis(this.cache);
    this.dashboard.renderOnlineSummary(this.cache);
    this.dashboard.renderTimeline(this.cache);
    this.chatView.setCache(this.cache);
    this.giftView.setCache(this.cache);
    this.rankView.render(this.cache);
    this.wordRank.render(this.cache.words);
    this.charts.renderTrend(this.cache, this.currentTrend);
    this.charts.renderOnline(this.cache);
    this.charts.renderGiftRank(this.cache);
    this.charts.renderGiftPie(this.cache, (item) => this.dashboard.openGiftDrawer(`${item.name} 送礼记录`, `价值 ${formatNumber(item.value)}，数量 ${formatNumber(item.count)}`, item.records));
    this.charts.renderWordCloud(this.cache, (item) => this.dashboard.openChatDrawer(`包含「${item.name}」的聊天`, `命中 ${formatNumber(item.value)} 次`, item.records));
  }

  resetFilters() {
    this.dashboard.closeDrawer();
    if (!this.cache) return;
    this.chatView.setCache(this.cache);
    this.giftView.setCache(this.cache);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  window.liveDashboardApp = new LiveDashboardApp();
});
