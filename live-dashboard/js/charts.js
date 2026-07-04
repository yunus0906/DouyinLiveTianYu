import { formatMinute, formatNumber } from "./utils.js";

const palette = ["#3b82f6", "#22c55e", "#f59e0b", "#22d3ee", "#a78bfa", "#ef4444", "#14b8a6"];

export class ChartManager {
  constructor() {
    this.instances = new Map();
    window.addEventListener("resize", () => this.resizeAll());
  }

  get(id) {
    const el = document.getElementById(id);
    if (!el || !window.echarts) return null;
    if (!this.instances.has(id)) this.instances.set(id, window.echarts.init(el, "dark"));
    return this.instances.get(id);
  }

  resizeAll() {
    for (const chart of this.instances.values()) chart.resize();
  }

  renderTrend(cache, type = "consume") {
    const chart = this.get("trendChart");
    if (!chart) return;
    const x = cache.minuteStats.map((item) => formatMinute(item.time));
    const base = baseOption();
    const option = {
      ...base,
      tooltip: { trigger: "axis", axisPointer: { type: "cross" } },
      toolbox: toolbox("trendChart"),
      dataZoom: dataZoom(),
      legend: { top: 0, textStyle: { color: "#cbd5e1" } },
      xAxis: { type: "category", boundaryGap: false, data: x, axisLabel: { color: "#94a3b8" } },
      yAxis: [],
      series: []
    };
    if (type === "interaction") {
      option.yAxis = [axis("评论数量"), axis("评论人数")];
      option.series = [
        line("评论数量", cache.minuteStats.map((item) => item.commentCount), 0, palette[0]),
        line("评论人数", cache.minuteStats.map((item) => item.commentUsers), 1, palette[3])
      ];
    } else if (type === "online") {
      option.yAxis = [axis("在线人数")];
      option.series = [area("在线人数", cache.minuteStats.map((item) => item.online), 0, palette[1])];
    } else {
      option.yAxis = [axis("礼物价值"), axis("礼物数量")];
      option.series = [
        area("礼物价值", cache.minuteStats.map((item) => item.giftValue), 0, palette[2]),
        line("礼物数量", cache.minuteStats.map((item) => item.giftCount), 1, palette[0])
      ];
    }
    chart.setOption(option, true);
  }

  renderOnline(cache) {
    const chart = this.get("onlineAreaChart");
    if (!chart) return;
    chart.setOption({
      ...baseOption(),
      tooltip: { trigger: "axis" },
      toolbox: toolbox("onlineAreaChart"),
      dataZoom: dataZoom(),
      xAxis: { type: "category", boundaryGap: false, data: cache.minuteStats.map((item) => formatMinute(item.time)), axisLabel: { color: "#94a3b8" } },
      yAxis: [axis("在线人数")],
      series: [area("在线人数", cache.minuteStats.map((item) => item.online), 0, palette[1])]
    }, true);
  }

  renderGiftRank(cache) {
    const chart = this.get("giftRankChart");
    if (!chart) return;
    const data = cache.giftUserRank.slice(0, 10).reverse();
    chart.setOption({
      ...baseOption(),
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 80, right: 20, top: 18, bottom: 20 },
      xAxis: { type: "value", axisLabel: { color: "#94a3b8", formatter: formatNumber } },
      yAxis: { type: "category", data: data.map((item) => item.username), axisLabel: { color: "#cbd5e1", width: 72, overflow: "truncate" } },
      series: [{ type: "bar", data: data.map((item) => item.value), itemStyle: { color: gradient(palette[0], palette[3]), borderRadius: [0, 8, 8, 0] }, label: { show: true, position: "right", formatter: ({ value }) => formatNumber(value), color: "#e2e8f0" } }]
    }, true);
  }

  renderGiftPie(cache, onClick) {
    const chart = this.get("giftPieChart");
    if (!chart) return;
    chart.off("click");
    chart.setOption({
      ...baseOption(),
      tooltip: { trigger: "item", formatter: ({ name, value, percent }) => `${name}<br/>${formatNumber(value)} (${percent}%)` },
      legend: { bottom: 0, type: "scroll", textStyle: { color: "#cbd5e1" } },
      series: [{
        type: "pie",
        radius: ["42%", "72%"],
        center: ["50%", "45%"],
        roseType: "radius",
        data: cache.giftComposition.slice(0, 30).map((item) => ({ name: item.name, value: item.value })),
        itemStyle: { borderColor: "#0f172a", borderWidth: 2 },
        label: { color: "#e2e8f0" }
      }]
    }, true);
    chart.on("click", (params) => {
      const item = cache.giftComposition.find((entry) => entry.name === params.name);
      if (item) onClick(item);
    });
  }

  renderWordCloud(cache, onClick) {
    const chart = this.get("wordCloudChart");
    if (!chart) return;
    chart.off("click");
    const canWordCloud = window.echarts && chart && Boolean(window.echarts.getMap || true);
    chart.setOption({
      ...baseOption(),
      tooltip: { show: true },
      series: [{
        type: canWordCloud ? "wordCloud" : "bar",
        shape: "circle",
        gridSize: 6,
        sizeRange: [12, 46],
        rotationRange: [-35, 35],
        width: "100%",
        height: "100%",
        textStyle: { color: () => palette[Math.floor(Math.random() * palette.length)] },
        emphasis: { focus: "self", textStyle: { textShadowBlur: 12, textShadowColor: "#60a5fa" } },
        data: cache.words.map((item) => ({ name: item.name, value: item.value }))
      }]
    }, true);
    chart.on("click", (params) => {
      const item = cache.words.find((entry) => entry.name === params.name);
      if (item) onClick(item);
    });
  }
}

function baseOption() {
  return {
    color: palette,
    backgroundColor: "transparent",
    animationDuration: 700,
    grid: { left: 56, right: 56, top: 46, bottom: 72 },
    textStyle: { fontFamily: "HarmonyOS Sans, Microsoft YaHei, sans-serif" }
  };
}

function axis(name) {
  return { type: "value", name, nameTextStyle: { color: "#94a3b8" }, axisLabel: { color: "#94a3b8", formatter: formatNumber }, splitLine: { lineStyle: { color: "rgba(148,163,184,0.14)" } } };
}

function line(name, data, yAxisIndex, color) {
  return { name, type: "line", smooth: true, yAxisIndex, data, symbol: "none", lineStyle: { width: 3, color }, itemStyle: { color } };
}

function area(name, data, yAxisIndex, color) {
  return { ...line(name, data, yAxisIndex, color), areaStyle: { color: gradient(color, "rgba(15,23,42,0.05)") } };
}

function gradient(start, end) {
  return new window.echarts.graphic.LinearGradient(0, 0, 1, 1, [{ offset: 0, color: start }, { offset: 1, color: end }]);
}

function dataZoom() {
  return [{ type: "inside", throttle: 50 }, { type: "slider", height: 24, bottom: 28, borderColor: "rgba(148,163,184,0.18)", textStyle: { color: "#94a3b8" } }];
}

function toolbox(targetId) {
  return { right: 12, feature: { myFull: { show: true, title: "全屏", icon: "path://M128 128h320v64H238v210h-64V128zm640 0v274h-64V192H494v-64h274zM174 622h64v210h210v64H174V622zm530 0h64v274H494v-64h210V622z", onclick: () => document.getElementById(targetId)?.requestFullscreen?.() }, saveAsImage: { title: "下载图片", backgroundColor: "#0f172a" }, restore: { title: "还原" }, dataZoom: { title: { zoom: "区域缩放", back: "缩放还原" } } }, iconStyle: { borderColor: "#94a3b8" } };
}
