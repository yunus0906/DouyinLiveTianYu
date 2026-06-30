#!/usr/bin/python
# coding:utf-8

# @FileName:    main.py
# @Time:        2024/1/2 22:27
# @Author:      bubu
# @Project:     douyinLiveWebFetcher

from liveMan import DouyinLiveWebFetcher
from LiveSession import LiveSession

if __name__ == '__main__':
    live_id = '537251005287'
    session = LiveSession(room_id=live_id)
    room = DouyinLiveWebFetcher(live_id, live_session=session)
    # room.get_room_status() # 失效
    room.start()
