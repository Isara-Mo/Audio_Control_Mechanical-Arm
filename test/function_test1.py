#!/usr/bin/env python3
# coding=utf-8
"""
语音控制机械臂系统
整合语音识别、大模型理解和机械臂控制
"""

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
from openai import OpenAI
from Arm_Lib import Arm_Device
import threading
import queue

class VoiceControlledArm:
    def __init__(self):
        # 语音识别参数
        self.recording_results = ""
        self.STATUS_FIRST_FRAME = 0
        self.STATUS_CONTINUE_FRAME = 1
        self.STATUS_LAST_FRAME = 2
        
        # 初始化机械臂
        self.arm = Arm_Device()
        time.sleep(0.1)
        
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key="", 
            base_url="https://api.deepseek.com"
        )
        
        # 指令队列
        self.command_queue = queue.Queue()
        
        # 系统状态
        self.is_running = True
        self.is_listening = False
        
        # 预定义位置
        self.positions = {
            "初始位置": [90, 130, 0, 0, 90],
            "准备位置": [90, 80, 50, 50, 270],
            "抓取位置": [90, 53, 33, 36, 270],
            "放置黄色": [65, 22, 64, 56, 270],
            "放置红色": [117, 19, 66, 56, 270],
            "放置绿色": [136, 66, 20, 29, 270],
            "放置蓝色": [44, 66, 20, 28, 270],
        }
        
        # 初始化机械臂位置
        self.init_arm()

    def init_arm(self):
        """初始化机械臂到准备位置"""
        print("正在初始化机械臂...")
        self.arm_clamp_block(0)  # 松开夹爪
        self.arm_move(self.positions["初始位置"], 1000)
        print("机械臂初始化完成")

    def arm_clamp_block(self, enable):
        """控制夹爪，enable=1：夹住，=0：松开"""
        if enable == 0:
            self.arm.Arm_serial_servo_write(6, 60, 400)
            print("松开夹爪")
        else:
            self.arm.Arm_serial_servo_write(6, 130, 400)
            print("夹紧夹爪")
        time.sleep(0.5)

    def arm_move(self, position, s_time=500):
        """移动机械臂到指定位置"""
        for i in range(5):
            servo_id = i + 1
            if servo_id == 5:
                time.sleep(0.1)
                self.arm.Arm_serial_servo_write(servo_id, position[i], int(s_time * 1.2))
            else:
                self.arm.Arm_serial_servo_write(servo_id, position[i], s_time)
            time.sleep(0.01)
        time.sleep(s_time / 1000)

    def arm_move_up(self):
        """机械臂向上移动"""
        self.arm.Arm_serial_servo_write(2, 90, 1500)
        self.arm.Arm_serial_servo_write(3, 90, 1500)
        self.arm.Arm_serial_servo_write(4, 90, 1500)
        time.sleep(0.1)

class Ws_Param:
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vinfo": 1,
            "vad_eos": 1000
        }

    def create_url(self):
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        
        signature_origin = "host: ws-api.xfyun.cn\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET /v2/iat HTTP/1.1"
        
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        url = url + '?' + urlencode(v)
        return url

# 全局变量
voice_arm = None

def understand_command(text):
    """使用大模型理解语音指令"""
    global voice_arm
    
    system_prompt = """你是一个机械臂控制助手。用户会给你语音指令，你需要将其转换为机械臂控制命令。

可用的控制命令：
1. move_to_position: 移动到预定义位置
   - 初始位置, 准备位置, 抓取位置, 放置黄色, 放置红色, 放置绿色, 放置蓝色
2. clamp_open: 松开夹爪
3. clamp_close: 夹紧夹爪
4. move_up: 向上移动
5. move_servo: 单独控制舵机 (需要指定舵机ID和角度)

请根据用户指令返回JSON格式的命令，例如：
{"action": "move_to_position", "position": "准备位置"}
{"action": "clamp_close"}
{"action": "move_servo", "servo_id": 1, "angle": 90, "time": 500}

如果指令不清楚，返回：{"action": "unknown", "message": "指令不清楚，请重新说明"}
"""

    try:
        response = voice_arm.client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"用户说：{text}"}
            ],
            stream=False
        )
        
        result = response.choices[0].message.content.strip()
        print(f"大模型理解结果: {result}")
        
        # 解析JSON命令
        try:
            command = json.loads(result)
            return command
        except json.JSONDecodeError:
            # 如果不是标准JSON，尝试简单解析
            return {"action": "unknown", "message": "无法解析指令"}
            
    except Exception as e:
        print(f"大模型调用错误: {e}")
        return {"action": "error", "message": str(e)}

def execute_command(command):
    """执行机械臂控制命令"""
    global voice_arm
    
    try:
        action = command.get("action")
        
        if action == "move_to_position":
            position_name = command.get("position")
            if position_name in voice_arm.positions:
                print(f"移动到: {position_name}")
                voice_arm.arm_move(voice_arm.positions[position_name], 1000)
            else:
                print(f"未知位置: {position_name}")
                
        elif action == "clamp_open":
            voice_arm.arm_clamp_block(0)
            
        elif action == "clamp_close":
            voice_arm.arm_clamp_block(1)
            
        elif action == "move_up":
            voice_arm.arm_move_up()
            
        elif action == "move_servo":
            servo_id = command.get("servo_id", 1)
            angle = command.get("angle", 90)
            move_time = command.get("time", 500)
            print(f"控制舵机 {servo_id} 到角度 {angle}")
            voice_arm.arm.Arm_serial_servo_write(servo_id, angle, move_time)
            
        elif action == "unknown":
            print(f"指令不清楚: {command.get('message', '请重新说明')}")
            
        elif action == "error":
            print(f"执行错误: {command.get('message', '未知错误')}")
            
        else:
            print(f"未知动作: {action}")
            
    except Exception as e:
        print(f"执行命令时出错: {e}")

def on_open(ws):
    """WebSocket连接建立时的处理"""
    def run(*args):
        global voice_arm
        status = voice_arm.STATUS_FIRST_FRAME
        
        CHUNK = 520
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        p = pyaudio.PyAudio()
        stream = p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )
        
        print("开始语音识别...")
        voice_arm.is_listening = True
        
        for i in range(0, int(RATE/CHUNK*10)):  # 10秒录音
            if not voice_arm.is_running:
                break
                
            buf = stream.read(CHUNK)
            if not buf:
                status = voice_arm.STATUS_LAST_FRAME
                
            if status == voice_arm.STATUS_FIRST_FRAME:
                d = {
                    "common": wsParam.CommonArgs,
                    "business": wsParam.BusinessArgs,
                    "data": {
                        "status": 0,
                        "format": "audio/L16;rate=16000",
                        "audio": str(base64.b64encode(buf), 'utf-8'),
                        "encoding": "raw"
                    }
                }
                ws.send(json.dumps(d))
                status = voice_arm.STATUS_CONTINUE_FRAME
                
            elif status == voice_arm.STATUS_CONTINUE_FRAME:
                d = {
                    "data": {
                        "status": 1,
                        "format": "audio/L16;rate=16000",
                        "audio": str(base64.b64encode(buf), 'utf-8'),
                        "encoding": "raw"
                    }
                }
                ws.send(json.dumps(d))
                
            elif status == voice_arm.STATUS_LAST_FRAME:
                d = {
                    "data": {
                        "status": 2,
                        "format": "audio/L16;rate=16000",
                        "audio": str(base64.b64encode(buf), 'utf-8'),
                        "encoding": "raw"
                    }
                }
                ws.send(json.dumps(d))
                time.sleep(1)
                break
                
        stream.stop_stream()
        stream.close()
        p.terminate()
        voice_arm.is_listening = False
        
    thread.start_new_thread(run, ())

def on_message(ws, message):
    """收到语音识别结果的处理"""
    global voice_arm
    
    try:
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        
        if code != 0:
            errMsg = json.loads(message)["message"]
            print(f"sid:{sid} call error:{errMsg} code is:{code}")
        else:
            data = json.loads(message)["data"]["result"]["ws"]
            result = ""
            for i in data:
                for w in i["cw"]:
                    result += w["w"]
                    
            if result and result not in ['。', '.。', ' .。', ' 。']:
                print(f"识别结果: {result}")
                voice_arm.recording_results = result
                
                # 理解并执行命令
                command = understand_command(result)
                execute_command(command)
                
    except Exception as e:
        print(f"解析语音识别结果时出错: {e}")

def on_error(ws, error):
    """WebSocket错误处理"""
    print(f"WebSocket错误: {error}")

def on_close(ws):
    """WebSocket关闭处理"""
    print("语音识别连接已关闭")

def start_voice_recognition():
    """启动语音识别"""
    global wsParam, voice_arm
    
    wsParam = Ws_Param(
        APPID='45099785',
        APIKey='33a475906a78026f4e272057c31a1486',
        APISecret='ZGYxYWM4ZThjZjE0ZjY1NTY2OGRlYTI1'
    )
    
    websocket.enableTrace(False)
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(
        wsUrl,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_timeout=2)

def command_interface():
    """命令行界面"""
    global voice_arm
    
    print("\n=== 语音控制机械臂系统 ===")
    print("可用命令:")
    print("1. 'start' - 开始语音识别")
    print("2. 'test' - 测试机械臂动作")
    print("3. 'reset' - 重置机械臂位置") 
    print("4. 'quit' - 退出系统")
    print("5. 或直接说出控制指令，如：'移动到准备位置'、'夹紧夹爪'等")
    
    while voice_arm.is_running:
        try:
            cmd = input("\n请输入命令: ").strip()
            
            if cmd == 'quit':
                print("正在关闭系统...")
                voice_arm.is_running = False
                break
                
            elif cmd == 'start':
                if not voice_arm.is_listening:
                    print("启动语音识别...")
                    threading.Thread(target=start_voice_recognition, daemon=True).start()
                else:
                    print("语音识别已在运行中")
                    
            elif cmd == 'test':
                print("执行测试动作...")
                voice_arm.arm_move(voice_arm.positions["准备位置"], 1000)
                time.sleep(1)
                voice_arm.arm_clamp_block(1)
                time.sleep(1)
                voice_arm.arm_clamp_block(0)
                voice_arm.arm_move(voice_arm.positions["初始位置"], 1000)
                print("测试完成")
                
            elif cmd == 'reset':
                print("重置机械臂位置...")
                voice_arm.init_arm()
                
            elif cmd:
                # 直接处理文本指令
                print(f"处理指令: {cmd}")
                command = understand_command(cmd)
                execute_command(command)
                
        except KeyboardInterrupt:
            print("\n检测到中断信号，正在退出...")
            voice_arm.is_running = False
            break
        except Exception as e:
            print(f"命令处理错误: {e}")

def main():
    """主函数"""
    global voice_arm
    
    try:
        # 初始化系统
        voice_arm = VoiceControlledArm()
        
        # 启动命令界面
        command_interface()
        
    except Exception as e:
        print(f"系统启动错误: {e}")
    finally:
        # 清理资源
        if voice_arm:
            try:
                del voice_arm.arm
            except:
                pass
        print("系统已关闭")

if __name__ == '__main__':
    main()