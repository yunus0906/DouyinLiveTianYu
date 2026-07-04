export const LIB_PATHS = {
  sqlWasm: "libs/sql-wasm.wasm"
};

export const FIELD_CANDIDATES = {
  time: ["event_time", "timestamp", "time", "created_at", "ts", "date_time", "datetime"],
  userId: ["user_id", "uid", "sec_uid", "open_id", "userId"],
  username: ["username", "nickname", "user_name", "nick_name", "name", "user"],
  content: ["content", "text", "message", "msg", "comment", "payload"],
  giftName: ["gift_name", "gift", "name", "giftName"],
  giftCount: ["gift_count", "count", "num", "quantity", "repeat_count"],
  giftValue: ["total_value", "fan_ticket_count", "diamond_count", "value", "amount", "score"],
  online: ["current_user", "online", "online_count", "display_value", "total", "viewer_count"],
  totalUser: ["total_user", "total_pv", "display_long", "display_middle", "display_short"],
  likeCount: ["like_count", "count", "total", "like_num"],
  eventType: ["event_type", "type", "message_type", "rank_type"],
  fansclubType: ["fansclub_type", "club_type", "type"]
};

export const TABLE_HINTS = {
  chat: ["chat", "comment", "danmu", "message"],
  gift: ["gift", "present", "reward"],
  member: ["member", "enter", "join"],
  follow: ["follow", "fans"],
  fansclub: ["fansclub", "club"],
  like: ["like", "digg"],
  roomStats: ["room_stats", "stats", "online"],
  event: ["event", "events"],
  roomInfo: ["room_info", "info"]
};

export const STOP_WORDS = new Set([
  "的", "了", "呢", "啊", "呀", "吧", "吗", "嘛", "哈", "哈哈", "哈哈哈", "就是", "这个", "那个", "可以", "不是", "没有", "什么", "怎么", "这么", "一个", "一下", "我们", "你们", "他们", "自己", "然后", "还是", "现在", "今天", "直播", "主播", "老师", "宝贝", "真的", "不要", "起来", "知道", "感觉", "看看", "666", "哈哈哈哈"
]);

export const KPI_DEFS = [
  ["startTime", "开始时间"],
  ["endTime", "结束时间"],
  ["duration", "直播时长"],
  ["memberCount", "进场消息数"],
  ["giftValue", "获得总音浪"],
  ["giftCount", "礼物数量"],
  ["giftUsers", "送礼人数"],
  ["commentUsers", "评论人数"],
  ["commentCount", "评论总条数"],
  ["totalViewers", "累计观众"],
  ["followCount", "新增粉丝"],
  ["fansclubCount", "加团人数"],
  ["likeCount", "总点赞数量"]
];
