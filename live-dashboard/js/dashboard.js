import { KPI_DEFS } from "./config.js";
import { animateNumber, escapeHtml, formatDuration, formatNumber, formatTime, VirtualList } from "./utils.js";
import { renderChatRow } from "./chat.js";
import { renderGiftRow } from "./gift.js";

export class DashboardView {
  constructor() {
    this.drawer = document.getElementById("detailDrawer");
    this.drawerTitle = document.getElementById("drawerTitle");
    this.drawerSubtitle = document.getElementById("drawerSubtitle");
    this.drawerList = new VirtualList(document.getElementById("drawerList"), { rowHeight: 62, renderRow: renderChatRow });
    document.getElementById("closeDrawer").addEventListener("click", () => this.closeDrawer());
  }

  setStatus(text, mode = "loading") {
    document.getElementById("statusText").textContent = text;
    const dot = document.getElementById("statusDot");
    dot.className = `status-dot ${mode === "ready" ? "ready" : mode === "error" ? "error" : ""}`;
  }

  renderSchema(schema, tableMap) {
    const count = Object.keys(schema.tables).length;
    const mapped = Object.entries(tableMap).filter(([, value]) => value).map(([key, value]) => `${key}:${value}`).join(" · ");
    document.getElementById("schemaSummary").textContent = `${count} 张表 · ${mapped || "未匹配到业务表"}`;
  }

  renderKpis(cache) {
    const grid = document.getElementById("kpiGrid");
    grid.innerHTML = KPI_DEFS.map(([key, label], index) => `<article class="kpi-card" style="animation-delay:${index * 24}ms">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value" data-kpi="${key}">-</div>
      <div class="kpi-sub">Live SQLite Analytics</div>
    </article>`).join("");
    for (const [key] of KPI_DEFS) {
      const el = grid.querySelector(`[data-kpi="${key}"]`);
      if (!el) continue;
      if (key === "startTime" || key === "endTime") el.textContent = formatTime(cache.kpis[key]);
      else if (key === "duration") el.textContent = formatDuration(cache.kpis.durationStart, cache.kpis.durationEnd);
      else animateNumber(el, cache.kpis[key], formatNumber);
    }
  }

  renderOnlineSummary(cache) {
    const values = cache.online.map((item) => item.online).filter((value) => value > 0);
    if (!values.length) {
      document.getElementById("onlineSummary").textContent = "暂无在线人数数据";
      return;
    }
    let max = 0;
    let min = Infinity;
    for (const value of values) {
      max = Math.max(max, value);
      min = Math.min(min, value);
    }
    const avg = Math.round(values.reduce((sum, value) => sum + value, 0) / values.length);
    const peak = cache.online.find((item) => item.online === max);
    document.getElementById("onlineSummary").textContent = `峰值 ${formatNumber(max)} · 最低 ${formatNumber(min)} · 平均 ${formatNumber(avg)} · 峰值时间 ${formatTime(peak?.time, "HH:mm:ss")}`;
  }

  renderTimeline(cache) {
    const el = document.getElementById("timeline");
    el.innerHTML = cache.timeline.map((item) => `<div class="timeline-item">
      <div class="timeline-time">${escapeHtml(formatTime(item.time, "HH:mm"))}</div>
      <div><div class="timeline-title">${escapeHtml(item.title)}</div><div class="timeline-desc">${escapeHtml(item.desc)}</div></div>
    </div>`).join("") || `<div class="empty-state"><strong>暂无事件</strong><span>缺少可用于时间轴的数据。</span></div>`;
  }

  openChatDrawer(title, subtitle, records) {
    this.drawerTitle.textContent = title;
    this.drawerSubtitle.textContent = subtitle;
    this.drawerList.renderRow = renderChatRow;
    this.drawerList.rowHeight = 62;
    this.drawerList.setData(records || []);
    this.drawer.classList.add("open");
  }

  openGiftDrawer(title, subtitle, records) {
    this.drawerTitle.textContent = title;
    this.drawerSubtitle.textContent = subtitle;
    this.drawerList.renderRow = renderGiftRow;
    this.drawerList.rowHeight = 62;
    this.drawerList.setData(records || []);
    this.drawer.classList.add("open");
  }

  closeDrawer() {
    this.drawer.classList.remove("open");
  }
}
