import websocket
import hashlib
import base64
import hmac
import json
from urllib.parse import urlencode
import time
import ssl
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread
import pyaudio

recording_results = ""  # 识别结果
STATUS_FIRST_FRAME = 0  # 第一帧的标识
STATUS_CONTINUE_FRAME = 1  # 中间帧标识
STATUS_LAST_FRAME = 2  # 最后一帧的标识

class Ws_Param(object):
    # 初始化接口对象
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret

        self.CommonArgs = {"app_id": self.APPID}

        # 业务参数，调整vad_eos为500ms，缩短无声音断句时间，避免超时关闭
        self.BusinessArgs = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vinfo": 1,
            "vad_eos": 500
        }

    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = "host: ws-api.xfyun.cn\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET /v2/iat HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode('utf-8'),
                                 signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode('utf-8')
        authorization_origin = ('api_key="%s", algorithm="hmac-sha256", headers="host date request-line", signature="%s"'
                               ) % (self.APIKey, signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        url = url + '?' + urlencode(v)
        return url


def on_open(ws):
    def run(*args):
        status = STATUS_FIRST_FRAME
        CHUNK = 520
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000

        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            frames_per_buffer=CHUNK)
        except Exception as e:
            print("打开麦克风失败:", e)
            ws.close()
            return

        print("---------------开始录音-----------------")

        global recording_results

        try:
            for i in range(0, int(RATE / CHUNK * 60)):  # 录制60秒
                buf = stream.read(CHUNK, exception_on_overflow=False)
                if not buf:
                    status = STATUS_LAST_FRAME

                if status == STATUS_FIRST_FRAME:
                    d = {
                        "common": wsParam.CommonArgs,
                        "business": wsParam.BusinessArgs,
                        "data": {
                            "status": 0,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode('utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    status = STATUS_CONTINUE_FRAME
                elif status == STATUS_CONTINUE_FRAME:
                    d = {
                        "data": {
                            "status": 1,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode('utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
            # 录音结束，发送最后一帧通知服务器
            d = {
                "data": {
                    "status": 2,
                    "format": "audio/L16;rate=16000",
                    "audio": "",
                    "encoding": "raw"
                }
            }
            ws.send(json.dumps(d))
            time.sleep(1)
        except websocket.WebSocketConnectionClosedException:
            print("websocket连接已关闭，停止发送数据")
        except Exception as e:
            print("录音线程异常:", e)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()
            ws.close()  # 关闭连接，让程序自然退出

    thread.start_new_thread(run, ())


def on_message(ws, message):
    try:
        msg = json.loads(message)
        code = msg.get("code")
        sid = msg.get("sid")
        if code != 0:
            errMsg = msg.get("message")
            print(f"sid:{sid} call error:{errMsg} code is:{code}")
            return

        data = msg.get("data", {}).get("result", {}).get("ws", [])
        result = ""
        for item in data:
            for w in item.get("cw", []):
                result += w.get("w", "")
        if result.strip() and result not in ['。', '.。', ' .。', ' 。']:
            print(f"翻译结果: {result}。")
            global recording_results
            recording_results = result
    except Exception as e:
        print("receive msg,but parse exception:", e)


def on_error(ws, error):
    print("### error ### : ", error)


def on_close(ws, close_status_code, close_msg):
    print(f"### websocket closed ### code: {close_status_code}, reason: {close_msg}")
    print("2秒后尝试重连...")
    time.sleep(2)
    run()


def run():
    global wsParam
    wsParam = Ws_Param(APPID='45099785',
                      APIKey='33a475906a78026f4e272057c31a1486',
                      APISecret='ZGYxYWM4ZThjZjE0ZjY1NTY2OGRlYTI1')
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_timeout=2)


if __name__ == '__main__':
    run()
