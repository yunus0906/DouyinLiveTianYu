import { FIELD_CANDIDATES, LIB_PATHS, TABLE_HINTS, STOP_WORDS } from "./config.js";
import { minuteKey, normalizeTime, parseNumericText, pickField, pickTable, safeText, topN } from "./utils.js";

export class LiveDatabase {
  constructor() {
    this.SQL = null;
    this.db = null;
    this.schema = { tables: {} };
  }

  async init() {
    if (this.SQL) return;
    if (!window.initSqlJs) throw new Error("sql.js 未加载，请检查 libs/sql-wasm.js");
    this.SQL = await window.initSqlJs({ locateFile: () => LIB_PATHS.sqlWasm });
  }

  async open(file) {
    await this.init();
    const buffer = await file.arrayBuffer();
    this.close();
    this.db = new this.SQL.Database(new Uint8Array(buffer));
    this.schema = this.readSchema();
    return this.schema;
  }

  close() {
    if (this.db) this.db.close();
    this.db = null;
  }

  readSchema() {
    const tables = {};
    const result = this.exec("SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name");
    for (const row of result) {
      const info = this.exec(`PRAGMA table_info(${JSON.stringify(row.name)})`);
      tables[row.name] = {
        name: row.name,
        type: row.type,
        sql: row.sql,
        columns: info.map((item) => item.name),
        info
      };
    }
    return { tables };
  }

  exec(sql, params = []) {
    if (!this.db) return [];
    const statement = this.db.prepare(sql);
    try {
      statement.bind(params);
      const rows = [];
      while (statement.step()) rows.push(statement.getAsObject());
      return rows;
    } finally {
      statement.free();
    }
  }

  table(name) {
    return this.schema.tables[name];
  }

  selectTable(name) {
    if (!name || !this.table(name)) return [];
    return this.exec(`SELECT * FROM ${quoteIdent(name)}`);
  }
}

function quoteIdent(name) {
  return `"${String(name).replace(/"/g, '""')}"`;
}

export class AnalyticsBuilder {
  constructor(liveDb) {
    this.liveDb = liveDb;
    this.schema = liveDb.schema;
    this.tableMap = this.buildTableMap();
  }

  buildTableMap() {
    return Object.fromEntries(Object.entries(TABLE_HINTS).map(([key, hints]) => [key, pickTable(this.schema, hints)]));
  }

  build() {
    const chat = this.normalizeChat();
    const gifts = this.normalizeGifts();
    const members = this.normalizeSimpleRecords("member");
    const follows = this.normalizeSimpleRecords("follow");
    const fansclubs = this.normalizeSimpleRecords("fansclub");
    const likes = this.normalizeLikes();
    const online = this.normalizeOnline();
    const timeBounds = this.getTimeBounds([chat, gifts, members, follows, fansclubs, likes, online]);
    const minuteStats = this.buildMinuteStats(chat, gifts, online);
    const giftUserRank = this.buildGiftUserRank(gifts);
    const commentRank = this.buildCommentRank(chat);
    const giftComposition = this.buildGiftComposition(gifts);
    const words = this.buildWords(chat);
    const kpis = this.buildKpis({ chat, gifts, members, follows, fansclubs, likes, online, timeBounds });
    const timeline = this.buildTimeline({ timeBounds, gifts, follows, fansclubs, online, minuteStats });
    return {
      schema: this.schema,
      tableMap: this.tableMap,
      chat,
      gifts,
      members,
      follows,
      fansclubs,
      likes,
      online,
      minuteStats,
      giftUserRank,
      commentRank,
      giftComposition,
      words,
      kpis,
      timeline
    };
  }

  normalizeChat() {
    const table = this.schema.tables[this.tableMap.chat];
    if (!table) return [];
    const fields = fieldMap(table.columns);
    return this.liveDb.selectTable(table.name).map((row, index) => ({
      id: row.id ?? index,
      time: normalizeTime(row[fields.time]),
      userId: safeText(row[fields.userId], ""),
      username: safeText(row[fields.username], "匿名用户"),
      content: extractContent(row[fields.content]),
      raw: row
    })).filter((item) => item.content).sort((a, b) => a.time - b.time);
  }

  normalizeGifts() {
    const table = this.schema.tables[this.tableMap.gift];
    if (!table) return [];
    const fields = fieldMap(table.columns);
    return this.liveDb.selectTable(table.name).map((row, index) => {
      const count = Number(row[fields.giftCount]) || 1;
      const value = Number(row[fields.giftValue]) || parseNumericText(row[fields.giftValue]);
      return {
        id: row.id ?? index,
        time: normalizeTime(row[fields.time]),
        userId: safeText(row[fields.userId], ""),
        username: safeText(row[fields.username], "匿名用户"),
        giftName: safeText(row[fields.giftName], "未知礼物"),
        count,
        value,
        raw: row
      };
    }).filter((item) => item.giftName || item.value || item.count).sort((a, b) => a.time - b.time);
  }

  normalizeSimpleRecords(kind) {
    const table = this.schema.tables[this.tableMap[kind]];
    if (!table) return [];
    const fields = fieldMap(table.columns);
    return this.liveDb.selectTable(table.name).map((row, index) => ({
      id: row.id ?? index,
      time: normalizeTime(row[fields.time]),
      userId: safeText(row[fields.userId], ""),
      username: safeText(row[fields.username], "匿名用户"),
      content: extractContent(row[fields.content]),
      raw: row
    })).sort((a, b) => a.time - b.time);
  }

  normalizeLikes() {
    const table = this.schema.tables[this.tableMap.like];
    if (!table) return [];
    const fields = fieldMap(table.columns);
    return this.liveDb.selectTable(table.name).map((row, index) => ({
      id: row.id ?? index,
      time: normalizeTime(row[fields.time]),
      username: safeText(row[fields.username], "匿名用户"),
      count: Number(row[fields.likeCount]) || 1,
      raw: row
    }));
  }

  normalizeOnline() {
    const table = this.schema.tables[this.tableMap.roomStats];
    if (!table) return [];
    const fields = fieldMap(table.columns);
    return this.liveDb.selectTable(table.name).map((row, index) => ({
      id: row.id ?? index,
      time: normalizeTime(row[fields.time]),
      online: Number(row[fields.online]) || parseNumericText(row[fields.online]),
      totalUser: parseNumericText(row[fields.totalUser]),
      raw: row
    })).filter((item) => item.time && (item.online || item.totalUser)).sort((a, b) => a.time - b.time);
  }

  getTimeBounds(groups) {
    let start = Infinity;
    let end = 0;
    for (const group of groups) {
      for (const item of group) {
        if (item.time) {
          start = Math.min(start, item.time);
          end = Math.max(end, item.time);
        }
      }
    }
    return { start: Number.isFinite(start) ? start : 0, end };
  }

  buildMinuteStats(chat, gifts, online) {
    const map = new Map();
    const ensure = (time) => {
      const key = minuteKey(time);
      if (!map.has(key)) map.set(key, { time: key, giftValue: 0, giftCount: 0, commentCount: 0, commentUsers: new Set(), online: 0 });
      return map.get(key);
    };
    for (const item of gifts) {
      const row = ensure(item.time);
      row.giftValue += item.value;
      row.giftCount += item.count;
    }
    for (const item of chat) {
      const row = ensure(item.time);
      row.commentCount += 1;
      if (item.userId || item.username) row.commentUsers.add(item.userId || item.username);
    }
    for (const item of online) {
      const row = ensure(item.time);
      row.online = Math.max(row.online, item.online);
    }
    return Array.from(map.values()).sort((a, b) => a.time - b.time).map((item) => ({ ...item, commentUsers: item.commentUsers.size }));
  }

  buildGiftUserRank(gifts) {
    const map = new Map();
    const total = gifts.reduce((sum, item) => sum + item.value, 0) || 1;
    for (const item of gifts) {
      const key = item.userId || item.username;
      if (!map.has(key)) map.set(key, { key, username: item.username, count: 0, value: 0, records: [] });
      const row = map.get(key);
      row.count += item.count;
      row.value += item.value;
      row.records.push(item);
    }
    return topN(map, 100).map((item, index) => ({ ...item, rank: index + 1, percent: item.value / total }));
  }

  buildCommentRank(chat) {
    const map = new Map();
    for (const item of chat) {
      const key = item.userId || item.username;
      if (!map.has(key)) map.set(key, { key, username: item.username, count: 0, firstTime: item.time, lastTime: item.time, records: [] });
      const row = map.get(key);
      row.count += 1;
      row.firstTime = Math.min(row.firstTime || item.time, item.time || row.firstTime);
      row.lastTime = Math.max(row.lastTime || item.time, item.time || row.lastTime);
      row.records.push(item);
    }
    return topN(map, 100).map((item, index) => ({ ...item, rank: index + 1 }));
  }

  buildGiftComposition(gifts) {
    const map = new Map();
    const total = gifts.reduce((sum, item) => sum + item.value, 0) || 1;
    for (const item of gifts) {
      if (!map.has(item.giftName)) map.set(item.giftName, { name: item.giftName, count: 0, value: 0, records: [] });
      const row = map.get(item.giftName);
      row.count += item.count;
      row.value += item.value;
      row.records.push(item);
    }
    return topN(map, 100).map((item) => ({ ...item, percent: item.value / total }));
  }

  buildWords(chat) {
    const map = new Map();
    for (const item of chat) {
      const tokens = tokenizeChinese(item.content);
      for (const token of tokens) {
        if (!map.has(token)) map.set(token, { name: token, value: 0, records: [] });
        const row = map.get(token);
        row.value += 1;
        if (row.records.length < 5000) row.records.push(item);
      }
    }
    return topN(map, 100);
  }

  buildKpis({ chat, gifts, members, follows, fansclubs, likes, online, timeBounds }) {
    const giftUsers = new Set(gifts.map((item) => item.userId || item.username).filter(Boolean));
    const commentUsers = new Set(chat.map((item) => item.userId || item.username).filter(Boolean));
    let maxTotalUser = 0;
    for (const item of online) maxTotalUser = Math.max(maxTotalUser, item.totalUser || 0);
    return {
      startTime: timeBounds.start,
      endTime: timeBounds.end,
      durationStart: timeBounds.start,
      durationEnd: timeBounds.end,
      memberCount: members.length,
      giftValue: gifts.reduce((sum, item) => sum + item.value, 0),
      giftCount: gifts.reduce((sum, item) => sum + item.count, 0),
      giftUsers: giftUsers.size,
      commentUsers: commentUsers.size,
      commentCount: chat.length,
      totalViewers: maxTotalUser || members.length,
      followCount: follows.length,
      fansclubCount: fansclubs.length,
      likeCount: likes.reduce((sum, item) => sum + item.count, 0)
    };
  }

  buildTimeline({ timeBounds, gifts, follows, fansclubs, online, minuteStats }) {
    const events = [];
    if (timeBounds.start) events.push({ time: timeBounds.start, title: "开播", desc: "检测到首条直播数据" });
    const bigGift = gifts.filter((item) => item.value > 0).sort((a, b) => b.value - a.value)[0];
    if (bigGift) events.push({ time: bigGift.time, title: bigGift.giftName, desc: `${bigGift.username} 送出，价值 ${bigGift.value}` });
    const peak = online.slice().sort((a, b) => b.online - a.online)[0];
    if (peak) events.push({ time: peak.time, title: `在线突破 ${peak.online}`, desc: "本场峰值在线人数" });
    const followMilestone = milestoneEvent(follows, 100, "新增粉丝100");
    if (followMilestone) events.push(followMilestone);
    const clubMilestone = milestoneEvent(fansclubs, 20, "加团人数20");
    if (clubMilestone) events.push(clubMilestone);
    const consumePeak = minuteStats.slice().sort((a, b) => b.giftValue - a.giftValue)[0];
    if (consumePeak?.giftValue) events.push({ time: consumePeak.time, title: "消费峰值分钟", desc: `该分钟礼物价值 ${consumePeak.giftValue}` });
    if (timeBounds.end && timeBounds.end !== timeBounds.start) events.push({ time: timeBounds.end, title: "下播", desc: "检测到最后一条直播数据" });
    return events.filter((item) => item.time).sort((a, b) => a.time - b.time);
  }
}

function fieldMap(columns) {
  return Object.fromEntries(Object.entries(FIELD_CANDIDATES).map(([key, candidates]) => [key, pickField(columns, candidates)]));
}

function extractContent(value) {
  if (value == null) return "";
  const text = String(value);
  if (!text.startsWith("{") && !text.startsWith("[")) return text;
  try {
    const obj = JSON.parse(text);
    return obj.content || obj.text || obj.msg || obj.message || text;
  } catch {
    return text;
  }
}

function tokenizeChinese(text) {
  const tokens = [];
  const segments = String(text).match(/[\u4e00-\u9fa5]{2,}|[a-zA-Z0-9]{2,}/g) || [];
  for (const segment of segments) {
    const lower = segment.toLowerCase();
    if (STOP_WORDS.has(lower)) continue;
    if (/^[\u4e00-\u9fa5]+$/.test(lower) && lower.length > 4) {
      for (let i = 0; i <= lower.length - 2; i += 1) {
        const token = lower.slice(i, i + 2);
        if (!STOP_WORDS.has(token)) tokens.push(token);
      }
      for (let i = 0; i <= lower.length - 3; i += 1) {
        const token = lower.slice(i, i + 3);
        if (!STOP_WORDS.has(token)) tokens.push(token);
      }
    } else {
      tokens.push(lower);
    }
  }
  return tokens;
}

function milestoneEvent(records, count, title) {
  if (records.length < count) return null;
  const row = records[count - 1];
  return { time: row.time, title, desc: `累计达到 ${count}` };
}
