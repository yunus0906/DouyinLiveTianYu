#!/usr/bin/python
# coding:utf-8

# @FileName:    liveMan.py
# @Time:        2024/1/2 21:51
# @Author:      bubu
# @Project:     douyinLiveWebFetcher

import codecs
import gzip
import hashlib
import random
import re
import string
import subprocess
import threading
import time
import execjs
import urllib.parse
from contextlib import contextmanager
from unittest.mock import patch

import requests
import websocket
from py_mini_racer import MiniRacer

from ac_signature import get__ac_signature
from protobuf.douyin import *

from urllib3.util.url import parse_url

from db import LiveDatabase


def execute_js(js_file: str):
    """
    执行 JavaScript 文件
    :param js_file: JavaScript 文件路径
    :return: 执行结果
    """
    with open(js_file, 'r', encoding='utf-8') as file:
        js_code = file.read()
    
    ctx = execjs.compile(js_code)
    return ctx


@contextmanager
def patched_popen_encoding(encoding='utf-8'):
    original_popen_init = subprocess.Popen.__init__
    
    def new_popen_init(self, *args, **kwargs):
        kwargs['encoding'] = encoding
        original_popen_init(self, *args, **kwargs)
    
    with patch.object(subprocess.Popen, '__init__', new_popen_init):
        yield


def generateSignature(wss, script_file='sign.js'):
    """
    出现gbk编码问题则修改 python模块subprocess.py的源码中Popen类的__init__函数参数encoding值为 "utf-8"
    """
    params = ("live_id,aid,version_code,webcast_sdk_version,"
              "room_id,sub_room_id,sub_channel_id,did_rule,"
              "user_unique_id,device_platform,device_type,ac,"
              "identity").split(',')
    wss_params = urllib.parse.urlparse(wss).query.split('&')
    wss_maps = {i.split('=')[0]: i.split("=")[-1] for i in wss_params}
    tpl_params = [f"{i}={wss_maps.get(i, '')}" for i in params]
    param = ','.join(tpl_params)
    md5 = hashlib.md5()
    md5.update(param.encode())
    md5_param = md5.hexdigest()
    
    with codecs.open(script_file, 'r', encoding='utf8') as f:
        script = f.read()
    
    ctx = MiniRacer()
    ctx.eval(script)
    
    try:
        signature = ctx.call("get_sign", md5_param)
        return signature
    except Exception as e:
        print(e)
    
    # 以下代码对应js脚本为sign_v0.js
    # context = execjs.compile(script)
    # with patched_popen_encoding(encoding='utf-8'):
    #     ret = context.call('getSign', {'X-MS-STUB': md5_param})
    # return ret.get('X-Bogus')


def generateMsToken(length=182):
    """
    产生请求头部cookie中的msToken字段，其实为随机的107位字符
    :param length:字符位数
    :return:msToken
    """
    random_str = ''
    base_str = string.ascii_letters + string.digits + '-_'
    _len = len(base_str) - 1
    for _ in range(length):
        random_str += base_str[random.randint(0, _len)]
    return random_str


class DouyinLiveWebFetcher:
    
    def __init__(self, live_id, abogus_file='a_bogus.js'):
        """
        直播间弹幕抓取对象
        :param live_id: 直播间的直播id，打开直播间web首页的链接如：https://live.douyin.com/261378947940，
                        其中的261378947940即是live_id
        """
        self.abogus_file = abogus_file
        self.__ttwid = None
        self.__room_id = None
        self.session = requests.Session()
        self.db = LiveDatabase()
        self.live_id = live_id
        self.host = "https://www.douyin.com/"
        self.live_url = "https://live.douyin.com/"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
        self.headers = {
            'User-Agent': self.user_agent
        }
    
    def start(self):
        self._connectWebSocket()
    
    def stop(self):
        self.ws.close()
    
    @property
    def ttwid(self):
        """
        产生请求头部cookie中的ttwid字段，访问抖音网页版直播间首页可以获取到响应cookie中的ttwid
        :return: ttwid
        """
        if self.__ttwid:
            return self.__ttwid
        headers = {
            "User-Agent": self.user_agent,
        }
        try:
            response = self.session.get(self.live_url, headers=headers)
            response.raise_for_status()
        except Exception as err:
            print("【X】Request the live url error: ", err)
        else:
            self.__ttwid = response.cookies.get('ttwid')
            return self.__ttwid
    
    @property
    def room_id(self):
        """
        根据直播间的地址获取到真正的直播间roomId，有时会有错误，可以重试请求解决
        :return:room_id
        """
        if self.__room_id:
            return self.__room_id
        url = self.live_url + self.live_id
        headers = {
            "User-Agent": self.user_agent,
            "cookie": f"ttwid={self.ttwid}&msToken={generateMsToken()}; __ac_nonce=0123407cc00a9e438deb4",
        }
        try:
            response = self.session.get(url, headers=headers)
            response.raise_for_status()
        except Exception as err:
            print("【X】Request the live room url error: ", err)
        else:
            match = re.search(r'roomId\\":\\"(\d+)\\"', response.text)
            if match is None or len(match.groups()) < 1:
                print("【X】No match found for roomId")
            
            self.__room_id = match.group(1)
            
            return self.__room_id
    
    def get_ac_nonce(self):
        """
        获取 __ac_nonce
        """
        resp_cookies = self.session.get(self.host, headers=self.headers).cookies
        return resp_cookies.get("__ac_nonce")
    
    def get_ac_signature(self, __ac_nonce: str = None) -> str:
        """
        获取 __ac_signature
        """
        __ac_signature = get__ac_signature(self.host[8:], __ac_nonce, self.user_agent)
        self.session.cookies.set("__ac_signature", __ac_signature)
        return __ac_signature
    
    def get_a_bogus(self, url_params: dict):
        """
        获取 a_bogus
        """
        url = urllib.parse.urlencode(url_params)
        ctx = execute_js(self.abogus_file)
        _a_bogus = ctx.call("get_ab", url, self.user_agent)
        return _a_bogus
    
    def get_room_status(self):
        """
        获取直播间开播状态:
        room_status: 2 直播已结束
        room_status: 0 直播进行中
        """
        msToken = generateMsToken()
        nonce = self.get_ac_nonce()
        signature = self.get_ac_signature(nonce)
        url = ('https://live.douyin.com/webcast/room/web/enter/?aid=6383'
               '&app_name=douyin_web&live_id=1&device_platform=web&language=zh-CN&enter_from=page_refresh'
               '&cookie_enabled=true&screen_width=5120&screen_height=1440&browser_language=zh-CN&browser_platform=Win32'
               '&browser_name=Edge&browser_version=140.0.0.0'
               f'&web_rid={self.live_id}'
               f'&room_id_str={self.room_id}'
               '&enter_source=&is_need_double_stream=false&insert_task_id=&live_reason=&msToken=' + msToken)
        query = parse_url(url).query
        params = {i[0]: i[1] for i in [j.split('=') for j in query.split('&')]}
        a_bogus = self.get_a_bogus(params)  # 计算a_bogus,成功率不是100%，出现失败时重试即可
        url += f"&a_bogus={a_bogus}"
        headers = self.headers.copy()
        headers.update({
            'Referer': f'https://live.douyin.com/{self.live_id}',
            'Cookie': f'ttwid={self.ttwid};__ac_nonce={nonce}; __ac_signature={signature}',
        })
        resp = self.session.get(url, headers=headers)
        data = resp.json().get('data')
        if data:
            room_status = data.get('room_status')
            user = data.get('user')
            user_id = user.get('id_str')
            nickname = user.get('nickname')
            print(f"【{nickname}】[{user_id}]直播间：{['正在直播', '已结束'][bool(room_status)]}.")
    
    def _connectWebSocket(self):
        """
        连接抖音直播间websocket服务器，请求直播间数据
        """
        wss = ("wss://webcast100-ws-web-lq.douyin.com/webcast/im/push/v2/?app_name=douyin_web"
               "&version_code=180800&webcast_sdk_version=1.0.14-beta.0"
               "&update_version_code=1.0.14-beta.0&compress=gzip&device_platform=web&cookie_enabled=true"
               "&screen_width=1536&screen_height=864&browser_language=zh-CN&browser_platform=Win32"
               "&browser_name=Mozilla"
               "&browser_version=5.0%20(Windows%20NT%2010.0;%20Win64;%20x64)%20AppleWebKit/537.36%20(KHTML,"
               "%20like%20Gecko)%20Chrome/126.0.0.0%20Safari/537.36"
               "&browser_online=true&tz_name=Asia/Shanghai"
               "&cursor=d-1_u-1_fh-7392091211001140287_t-1721106114633_r-1"
               f"&internal_ext=internal_src:dim|wss_push_room_id:{self.room_id}|wss_push_did:7319483754668557238"
               f"|first_req_ms:1721106114541|fetch_time:1721106114633|seq:1|wss_info:0-1721106114633-0-0|"
               f"wrds_v:7392094459690748497"
               f"&host=https://live.douyin.com&aid=6383&live_id=1&did_rule=3&endpoint=live_pc&support_wrds=1"
               f"&user_unique_id=7319483754668557238&im_path=/webcast/im/fetch/&identity=audience"
               f"&need_persist_msg_count=15&insert_task_id=&live_reason=&room_id={self.room_id}&heartbeatDuration=0")
        
        signature = generateSignature(wss)
        wss += f"&signature={signature}"
        
        headers = {
            "cookie": f"enter_pc_once=1; UIFID_TEMP=3b6adaced0a588dab6f51c731af48a99e86229cd7fa27db4535ff73b415f88b5beffcd25f96948dbad750c70f00e4857b46d9d3216230089ac2d80506cc14f8243b81e1377893f8a9abb8aa6b6466e976dd5422bea41a8f1d393b2d4bda91bb68e69e17696435f0dd0926d9594e73f47; x-web-secsdk-uid=573246b8-2c78-4c32-84d3-ab9be34f159b; douyin.com; s_v_web_id=verify_molidmlf_MPMEvY9U_eqJv_4ThW_9hRl_LydJYyfBsFrc; device_web_cpu_core=8; device_web_memory_size=16; architecture=amd64; is_support_rtm_web_ts=1; hevc_supported=true; dy_swidth=1536; dy_sheight=864; fpk1=U2FsdGVkX1814NP9rAJ+4kFqgVT74OKbHy/w2UdtQz7uBuncpzz6IU8//6i0G1pfs+O+ZkwbYx43Z/6b2FV1Iw==; fpk2=4238b62bcd3c1a9c24ccf656e6ace824; strategyABtestKey=%221777555047.271%22; passport_csrf_token=91e469069833e5e16ef8d91b4adf93e5; passport_csrf_token_default=91e469069833e5e16ef8d91b4adf93e5; UIFID=3b6adaced0a588dab6f51c731af48a99e86229cd7fa27db4535ff73b415f88b5beffcd25f96948dbad750c70f00e4857b46d9d3216230089ac2d80506cc14f821d30d774d198782b2f183e816f97685e440559a3c6f8922cc8f48bd8c8590e831f7630bf15aef993c3cff792e50ce755ec852c620157b4fc2aa24269157ba89c9aa545ad2c304c139dbeeb7d44763bd6cab3fb6a62f4b543bdfce38c5054f95ed7691dee5f3ee681f83000234158d75316eadd16a3bf3ce9854a1ae1dfd84102; stream_recommend_feed_params=%22%7B%5C%22cookie_enabled%5C%22%3Atrue%2C%5C%22screen_width%5C%22%3A1536%2C%5C%22screen_height%5C%22%3A864%2C%5C%22browser_online%5C%22%3Atrue%2C%5C%22cpu_core_num%5C%22%3A8%2C%5C%22device_memory%5C%22%3A16%2C%5C%22downlink%5C%22%3A10%2C%5C%22effective_type%5C%22%3A%5C%224g%5C%22%2C%5C%22round_trip_time%5C%22%3A50%7D%22; bd_ticket_guard_client_web_domain=2; passport_assist_user=CkFC34r-eYdEVUEtsIRR8etlOT1O4P-64NqT4Wj2waS2PERzG0CezBz5TSwgCf-yX05fbuOWQNmLsvwmFHPgrEPDvRpKCjwAAAAAAAAAAAAAUF0ftcadOi-Uwyr89Bujd_SeuTrZYA6tiD6qOryIobftmiA86fkFLSN8SJQispUz9-sQ_JuQDhiJr9ZUIAEiAQPAHYQc; n_mh=EQkS9pKVPyBJLjKnKdU4kezQMmtonkap1urL876xDDI; sid_guard=30f3d6026bb4d067c0b4081793dc47b3%7C1777555078%7C5184000%7CMon%2C+29-Jun-2026+13%3A17%3A58+GMT; uid_tt=9fc0c38b238020457ba18ac3db3ae9b4; uid_tt_ss=9fc0c38b238020457ba18ac3db3ae9b4; sid_tt=30f3d6026bb4d067c0b4081793dc47b3; sessionid=30f3d6026bb4d067c0b4081793dc47b3; sessionid_ss=30f3d6026bb4d067c0b4081793dc47b3; session_tlb_tag=sttt%7C2%7CMPPWAmu00GfAtAgXk9xHs__________XB9SDmMpAfYxM5EpX3NkJDsU01ns9fAaYu0B4E76W93Q%3D; is_staff_user=false; has_biz_token=false; sid_ucp_v1=1.0.0-KDVkMDRiNGY3MGYxZTJhYTU5OWE5ZjVkZWRiM2U3ZDE3MGRhY2RmMDkKIQiukLC_xMzYBhCGrc3PBhjvMSAMMLb9kaIGOAdA9AdIBBoCaGwiIDMwZjNkNjAyNmJiNGQwNjdjMGI0MDgxNzkzZGM0N2Iz; ssid_ucp_v1=1.0.0-KDVkMDRiNGY3MGYxZTJhYTU5OWE5ZjVkZWRiM2U3ZDE3MGRhY2RmMDkKIQiukLC_xMzYBhCGrc3PBhjvMSAMMLb9kaIGOAdA9AdIBBoCaGwiIDMwZjNkNjAyNmJiNGQwNjdjMGI0MDgxNzkzZGM0N2Iz; _bd_ticket_crypt_cookie=7362949f7722b91203160b45bf0d8352; __security_mc_1_s_sdk_sign_data_key_web_protect=0389cc26-4597-b3b0; __security_mc_1_s_sdk_cert_key=629387f9-495c-889e; __security_mc_1_s_sdk_crypt_sdk=cb460e95-4121-8a87; __security_server_data_status=1; login_time=1777555079052; publish_badge_show_info=%220%2C0%2C0%2C1777555079387%22; DiscoverFeedExposedAd=%7B%7D; SelfTabRedDotControl=%5B%7B%22id%22%3A%227616557969206937652%22%2C%22u%22%3A92%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227613762559497226259%22%2C%22u%22%3A112%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227426412497073178676%22%2C%22u%22%3A26%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227591872198793496586%22%2C%22u%22%3A9%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227461595303297157158%22%2C%22u%22%3A20%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227350912524990023690%22%2C%22u%22%3A18%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227441633559661512730%22%2C%22u%22%3A154%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227347584802515585062%22%2C%22u%22%3A93%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227439392261869144074%22%2C%22u%22%3A13%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227468634777730418738%22%2C%22u%22%3A15%2C%22c%22%3A0%7D%2C%7B%22id%22%3A%227333583823206090761%22%2C%22u%22%3A38%2C%22c%22%3A0%7D%5D; ttwid=1%7CV3sylPDxrCqBY5mxT1kHXOYtw49ajVp9WjjBfafvBO8%7C1777555086%7C5f8c1a10c1848cfe5e303a7d76057045905057fa3cca46514489e3bc76dc6071; is_dash_user=1; download_guide=%221%2F20260430%2F0%22; FOLLOW_LIVE_POINT_INFO=%22MS4wLjABAAAAGyRrVAtkZCv1fek-E6yAONipA5tdCJdW76wACE2pCsSZ-BfzWLEHA86gGGoMhFRf%2F1777564800000%2F0%2F0%2F1777556210711%22; FOLLOW_NUMBER_YELLOW_POINT_INFO=%22MS4wLjABAAAAGyRrVAtkZCv1fek-E6yAONipA5tdCJdW76wACE2pCsSZ-BfzWLEHA86gGGoMhFRf%2F1777564800000%2F0%2F1777555610711%2F0%22; bd_ticket_guard_client_data=eyJiZC10aWNrZXQtZ3VhcmQtdmVyc2lvbiI6MiwiYmQtdGlja2V0LWd1YXJkLWl0ZXJhdGlvbi12ZXJzaW9uIjoxLCJiZC10aWNrZXQtZ3VhcmQtcmVlLXB1YmxpYy1rZXkiOiJCT2ZLeEpubkdLamhWNmtUUUtCVFkzekYrclB1Sm5hNHI2RFhHMHNJU0M1WDBGRWJvTHlJS09ZakUvMW1laDJMNldyS2dwNzhrY2xJRUxCeXo2cjBaVWs9IiwiYmQtdGlja2V0LWd1YXJkLXdlYi12ZXJzaW9uIjoyfQ%3D%3D; home_can_add_dy_2_desktop=%221%22; odin_tt=d6459913e8e7a38c6fc4f56a51deb563e65d8cae5f0ede707ba078f0d5bf42f760b2800085baed757b6e948c486a28114c133ecf4c7c75ba6e03da7691fa4201015f8a52666d38f2bec1b9303efe25d0; biz_trace_id=60eac114; sdk_source_info=7e276470716a68645a606960273f276364697660272927676c715a6d6069756077273f276364697660272927666d776a68605a607d71606b766c6a6b5a7666776c7571273f275e58272927666a6b766a69605a696c6061273f27636469766027292762696a6764695a7364776c6467696076273f275e582729277672715a646971273f2763646976602729277f6b5a666475273f2763646976602729276d6a6e5a6b6a716c273f2763646976602729276c6b6f5a7f6367273f27636469766027292771273f273730373d343330303032323234272927676c715a75776a716a666a69273f2763646976602778; bit_env=HPCwqr4BfS2FURTv5hRJ8h_GKDnXjdrzV9e6OK_GiLa0Fb85icGnM-PpfPPfJ_cpkCh4TQwKWgN2AZ4TDuvYORWVvPmM7fON-bmMykl3nDb7sTFDU-i-T753o8GFGLpPrddn4VCSmpaAMDf0WqbYPhdMjtvCqLxfabNfWl6GdVmb43WMNpjvvsMB2CkrDLVQ6UHk2NiKhkCeQ5tzUP5gFWLb6gjS476nrX8CYjtrvNukd13ZWhaWiisTAwVKRXk1n6EAm3SpNlAeRmHu-9-_YKYx473zK6rJOJMpE-u8fZasbct2uCLqijafsLBiGxwmEDJt4FfAYkZDVPgYZoI4IEiXEq94toNU-j7jyhywwVHVQS_28qhBO6pBmOqfkczipGX3X7G51txLAbd_XeVEjPiqQUuDp17Y6JUvWBku6kPTv8bjbjR58vW7ugPqSFdfKdCJz28ZyAraT-UujqwCB7ji2enGCZV_dFQf4HlAH0mdM1TIfv0i7T89AiXLp1Dyb8CA6-MI0FYq6TiwqJ6X08vy8cDFuyssRJcfeu9DrJM%3D; gulu_source_res=eyJwX2luIjoiYzA3ZDQzMmJmM2E3YmU5Mjc0ZjBmODA2OGQwZjQ3N2M1Y2I2Mzc2NjNlZTdhOTBiMjlhZWNjZWE3YzQxMjgxYSJ9; passport_auth_mix_state=l7655ykbtmv70va0oyz6jgnqvsc6jkv7; bd_ticket_guard_client_data_v2=eyJyZWVfcHVibGljX2tleSI6IkJPZkt4Sm5uR0tqaFY2a1RRS0JUWTN6RityUHVKbmE0cjZEWEcwc0lTQzVYMEZFYm9MeUlLT1lqRS8xbWVoMkw2V3JLZ3A3OGtjbElFTEJ5ejZyMFpVaz0iLCJ0c19zaWduIjoidHMuMi5mNmE3OTBjMTk0NzQ0NmZkYTgxYjg0ZGIxYzZmNTdiMTdiZDgyYjJhMmVkMmI5NjkyMjVjY2IwODE5ZTA0MTQxYzRmYmU4N2QyMzE5Y2YwNTMxODYyNGNlZGExNDkxMWNhNDA2ZGVkYmViZWRkYjJlMzBmY2U4ZDRmYTAyNTc1ZCIsInJlcV9jb250ZW50Ijoic2VjX3RzIiwicmVxX3NpZ24iOiJkQ0UwdjJ6UWN0Y3NLRW9veER5Sjg1bklSRit4VzJoZHZGaldhR2lvZUZjPSIsInNlY190cyI6IiNMbk52S0kzekRtbm4wY2wyRVRkTXZVdW81azljTyt2RDVTU1dJK09JazRRekV1ME9vaHFxSzZPVzFBK0MifQ%3D%3D; IsDouyinActive=false",
            'user-agent': self.user_agent,
        }
        self.ws = websocket.WebSocketApp(wss,
                                         header=headers,
                                         on_open=self._wsOnOpen,
                                         on_message=self._wsOnMessage,
                                         on_error=self._wsOnError,
                                         on_close=self._wsOnClose)
        try:
            self.ws.run_forever()
        except Exception:
            self.stop()
            raise
    
    def _sendHeartbeat(self):
        """
        发送心跳包
        """
        while True:
            try:
                heartbeat = PushFrame(payload_type='hb').SerializeToString()
                self.ws.send(heartbeat, websocket.ABNF.OPCODE_PING)
                print("【√】发送心跳包")
            except Exception as e:
                print("【X】心跳包检测错误: ", e)
                break
            else:
                time.sleep(5)
    
    def _wsOnOpen(self, ws):
        """
        连接建立成功
        """
        print("【√】WebSocket连接成功.")
        threading.Thread(target=self._sendHeartbeat).start()
    
    def _wsOnMessage(self, ws, message):
        """
        接收到数据
        :param ws: websocket实例
        :param message: 数据
        """
        
        # 根据proto结构体解析对象
        package = PushFrame().parse(message)
        response = Response().parse(gzip.decompress(package.payload))
        
        # 返回直播间服务器链接存活确认消息，便于持续获取数据
        if response.need_ack:
            ack = PushFrame(log_id=package.log_id,
                            payload_type='ack',
                            payload=response.internal_ext.encode('utf-8')
                            ).SerializeToString()
            ws.send(ack, websocket.ABNF.OPCODE_BINARY)
        
        # 根据消息类别解析消息体
        parser_map = {
            'WebcastChatMessage': self._parseChatMsg,  # 聊天消息
            'WebcastGiftMessage': self._parseGiftMsg,  # 礼物消息
            'WebcastLikeMessage': self._parseLikeMsg,  # 点赞消息
            'WebcastMemberMessage': self._parseMemberMsg,  # 进入直播间消息
            'WebcastSocialMessage': self._parseSocialMsg,  # 关注消息
            'WebcastRoomUserSeqMessage': self._parseRoomUserSeqMsg,  # 直播间统计
            'WebcastFansclubMessage': self._parseFansclubMsg,  # 粉丝团消息
            'WebcastControlMessage': self._parseControlMsg,  # 直播间状态消息
            'WebcastEmojiChatMessage': self._parseEmojiChatMsg,  # 聊天表情包消息
            'WebcastRoomStatsMessage': self._parseRoomStatsMsg,  # 直播间统计信息
            'WebcastRoomMessage': self._parseRoomMsg,  # 直播间信息
            'WebcastRoomRankMessage': self._parseRankMsg,  # 直播间排行榜信息
            'WebcastRoomStreamAdaptationMessage': self._parseRoomStreamAdaptationMsg,  # 直播间流配置
        }
        for msg in response.messages_list:
            method = msg.method
            parser = parser_map.get(method)
            if parser is None:
                continue
            try:
                parser(msg.payload)
            except Exception:
                pass
    
    def _wsOnError(self, ws, error):
        print("WebSocket error: ", error)
    
    def _wsOnClose(self, ws, *args):
        self.get_room_status()
        print("WebSocket connection closed.")
    
    def _parseChatMsg(self, payload):
        """聊天消息"""
        message = ChatMessage().parse(payload)
        common = message.common
        user_name = message.user.nick_name
        user_id = message.user.id
        content = message.content
        self.db.insert_chat(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            user_id=user_id,
            username=user_name,
            content=content,
        )
        print(f"【聊天msg】[{user_id}]{user_name}: {content}")
    
    def _parseGiftMsg(self, payload):
        """礼物消息"""
        message = GiftMessage().parse(payload)
        common = message.common
        user_name = message.user.nick_name
        user_id = message.user.id
        gift_id = message.gift_id or message.gift.id
        gift_name = message.gift.name
        gift_cnt = message.combo_count
        self.db.insert_gift(
            event_time=common.create_time or message.send_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            user_id=user_id,
            username=user_name,
            gift_id=gift_id,
            gift_name=gift_name,
            gift_count=gift_cnt,
            diamond_count=message.gift.diamond_count,
            fan_ticket_count=message.fan_ticket_count,
        )
        print(f"【礼物msg】{user_name} 送出了 {gift_name}x{gift_cnt}")
    
    def _parseLikeMsg(self, payload):
        '''点赞消息'''
        message = LikeMessage().parse(payload)
        common = message.common
        user_name = message.user.nick_name
        user_id = message.user.id
        count = message.count
        self.db.insert_like(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            user_id=user_id,
            username=user_name,
            like_count=count,
        )
        print(f"【点赞msg】{user_name} 点了{count}个赞")
    
    def _parseMemberMsg(self, payload):
        '''进入直播间消息'''
        message = MemberMessage().parse(payload)
        common = message.common
        user_name = message.user.nick_name
        user_id = message.user.id
        gender = {0: "女", 1: "男"}.get(message.user.gender, "未知")
        self.db.insert_member(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            user_id=user_id,
            username=user_name,
            gender=message.user.gender,
            enter_type=message.enter_type,
            action=message.action,
        )
        print(f"【进场msg】[{user_id}][{gender}]{user_name} 进入了直播间")
    
    def _parseSocialMsg(self, payload):
        '''关注消息'''
        message = SocialMessage().parse(payload)
        common = message.common
        user_name = message.user.nick_name
        user_id = message.user.id
        self.db.insert_follow(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            user_id=user_id,
            username=user_name,
        )
        print(f"【关注msg】[{user_id}]{user_name} 关注了主播")
    
    def _parseRoomUserSeqMsg(self, payload):
        '''直播间统计'''
        message = RoomUserSeqMessage().parse(payload)
        common = message.common
        current = message.total
        total = message.total_pv_for_anchor
        self.db.insert_room_stats(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            current_user=current,
            total_user=message.total_user_str,
            total_pv=total,
        )
        print(f"【统计msg】当前观看人数: {current}, 累计观看人数: {total}")
    
    def _parseFansclubMsg(self, payload):
        '''粉丝团消息'''
        message = FansclubMessage().parse(payload)
        common = message.common_info
        content = message.content
        self.db.insert_fansclub(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            user_id=message.user.id,
            username=message.user.nick_name,
            fansclub_type=message.type,
            content=content,
        )
        print(f"【粉丝团msg】 {content}")
    
    def _parseEmojiChatMsg(self, payload):
        '''聊天表情包消息'''
        message = EmojiChatMessage().parse(payload)
        emoji_id = message.emoji_id
        user = message.user
        common = message.common
        default_content = message.default_content
        print(f"【聊天表情包id】 {emoji_id},user：{user},common:{common},default_content:{default_content}")
    
    def _parseRoomMsg(self, payload):
        message = RoomMessage().parse(payload)
        common = message.common
        room_id = common.room_id
        self.db.insert_room_info(
            event_time=common.create_time,
            room_id=room_id,
            msg_id=common.msg_id,
            content=message.content,
            room_message_type=message.roommessagetype,
            biz_scene=message.biz_scene,
        )
        print(f"【直播间msg】直播间id:{room_id}")
    
    def _parseRoomStatsMsg(self, payload):
        message = RoomStatsMessage().parse(payload)
        common = message.common
        display_long = message.display_long
        self.db.insert_room_stats(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            display_short=message.display_short,
            display_middle=message.display_middle,
            display_long=display_long,
            display_value=message.display_value,
            total=message.total,
        )
        print(f"【直播间统计msg】{display_long}")
    
    def _parseRankMsg(self, payload):
        message = RoomRankMessage().parse(payload)
        common = message.common
        ranks_list = message.ranks_list
        for rank_no, rank_item in enumerate(ranks_list, start=1):
            self.db.insert_rank(
                event_time=common.create_time,
                room_id=common.room_id,
                msg_id=common.msg_id,
                rank_type="room",
                rank_no=rank_no,
                user_id=rank_item.user.id,
                username=rank_item.user.nick_name,
                score=rank_item.score_str,
            )
        print(f"【直播间排行榜msg】{ranks_list}")
    
    def _parseControlMsg(self, payload):
        '''直播间状态消息'''
        message = ControlMessage().parse(payload)
        common = message.common
        self.db.insert_control(
            event_time=common.create_time,
            room_id=common.room_id,
            msg_id=common.msg_id,
            status=message.status,
        )
        
        if message.status == 3:
            print("直播间已结束")
            self.stop()
    
    def _parseRoomStreamAdaptationMsg(self, payload):
        message = RoomStreamAdaptationMessage().parse(payload)
        adaptationType = message.adaptation_type
        print(f'直播间adaptation: {adaptationType}')
