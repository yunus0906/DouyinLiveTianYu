-- 直播数据分析 SQLite 表结构。
-- 设计说明：明细表服务高频统计，event 表提供统一事件流和后续扩展入口。

CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    event_type TEXT NOT NULL,
    user_id TEXT,
    username TEXT,
    ref_table TEXT,
    ref_id INTEGER,
    payload TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    user_id TEXT,
    username TEXT,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS gift (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    user_id TEXT,
    username TEXT,
    gift_id TEXT,
    gift_name TEXT,
    gift_count INTEGER NOT NULL DEFAULT 0,
    diamond_count INTEGER NOT NULL DEFAULT 0,
    fan_ticket_count INTEGER NOT NULL DEFAULT 0,
    total_value INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS like (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    user_id TEXT,
    username TEXT,
    like_count INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS member (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    user_id TEXT,
    username TEXT,
    gender INTEGER,
    enter_type INTEGER,
    action INTEGER,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS follow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    user_id TEXT,
    username TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fansclub (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    user_id TEXT,
    username TEXT,
    fansclub_type INTEGER,
    content TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS room_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    current_user INTEGER,
    total_user TEXT,
    total_pv TEXT,
    display_short TEXT,
    display_middle TEXT,
    display_long TEXT,
    display_value INTEGER,
    total INTEGER,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS room_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    content TEXT,
    room_message_type INTEGER,
    biz_scene TEXT,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS rank (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time INTEGER NOT NULL,
    room_id TEXT,
    msg_id TEXT,
    rank_type TEXT NOT NULL,
    rank_no INTEGER,
    user_id TEXT,
    username TEXT,
    score TEXT,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_event_time ON event(event_time);
CREATE INDEX IF NOT EXISTS idx_event_type_time ON event(event_type, event_time);
CREATE INDEX IF NOT EXISTS idx_event_user_time ON event(user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_chat_time ON chat(event_time);
CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat(user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_gift_time ON gift(event_time);
CREATE INDEX IF NOT EXISTS idx_gift_rank ON gift(gift_name, total_value);
CREATE INDEX IF NOT EXISTS idx_gift_user_value ON gift(user_id, total_value);
CREATE INDEX IF NOT EXISTS idx_like_user_time ON like(user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_member_time ON member(event_time);
CREATE INDEX IF NOT EXISTS idx_follow_user_time ON follow(user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_fansclub_user_time ON fansclub(user_id, event_time);
CREATE INDEX IF NOT EXISTS idx_room_stats_time ON room_stats(event_time);
CREATE INDEX IF NOT EXISTS idx_room_info_time ON room_info(event_time);
CREATE INDEX IF NOT EXISTS idx_rank_type_time ON rank(rank_type, event_time);
CREATE INDEX IF NOT EXISTS idx_rank_user_time ON rank(user_id, event_time);
