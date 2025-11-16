#!/usr/bin/env python3
# coding=utf-8
"""
语音控制机械臂系统 - 改进版
使用预定义动作命令，简化模型理解过程
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
import re

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
        
        # 预定义动作命令集
        self.action_commands = {
            # 基础动作
            "初始化": self.action_init,
            "复位": self.action_init,
            "重置": self.action_init,
            
            "准备": self.action_ready,
            "待机": self.action_ready,
            
            "抓取": self.action_grab,
            "夹取": self.action_grab,
            "夹住": self.action_grab,
            
            "松开": self.action_release,
            "放开": self.action_release,
            "释放": self.action_release,
            
            "向上": self.action_move_up,
            "上升": self.action_move_up,
            "升高": self.action_move_up,
            
            # 颜色分类动作
            "黄色": self.action_place_yellow,
            "放黄色": self.action_place_yellow,
            "黄色区域": self.action_place_yellow,
            
            "红色": self.action_place_red,
            "放红色": self.action_place_red,
            "红色区域": self.action_place_red,
            
            "绿色": self.action_place_green,
            "放绿色": self.action_place_green,
            "绿色区域": self.action_place_green,
            
            "蓝色": self.action_place_blue,
            "放蓝色": self.action_place_blue,
            "蓝色区域": self.action_place_blue,
            
            # 组合动作
            "完整抓取": self.action_full_grab_sequence,
            "抓取流程": self.action_full_grab_sequence,
            "执行抓取": self.action_full_grab_sequence,
            
            "分拣黄色": self.action_sort_yellow,
            "分拣红色": self.action_sort_red,
            "分拣绿色": self.action_sort_green,
            "分拣蓝色": self.action_sort_blue,
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
        time.sleep(1.5)

    # 预定义动作命令
    def action_init(self):
        """初始化动作"""
        print("执行初始化动作")
        self.arm_clamp_block(0)
        self.arm_move(self.positions["初始位置"], 1000)

    def action_ready(self):
        """准备动作"""
        print("执行准备动作")
        self.arm_move(self.positions["准备位置"], 1000)

    def action_grab(self):
        """抓取动作"""
        print("执行抓取动作")
        self.arm_move(self.positions["抓取位置"], 1000)
        self.arm_clamp_block(1)

    def action_release(self):
        """释放动作"""
        print("执行释放动作")
        self.arm_clamp_block(0)

    def action_move_up(self):
        """向上移动动作"""
        print("执行向上移动动作")
        self.arm_move_up()

    def action_place_yellow(self):
        """放置到黄色区域"""
        print("执行放置黄色动作")
        self.arm_move(self.positions["放置黄色"], 1000)

    def action_place_red(self):
        """放置到红色区域"""
        print("执行放置红色动作")
        self.arm_move(self.positions["放置红色"], 1000)

    def action_place_green(self):
        """放置到绿色区域"""
        print("执行放置绿色动作")
        self.arm_move(self.positions["放置绿色"], 1000)

    def action_place_blue(self):
        """放置到蓝色区域"""
        print("执行放置蓝色动作")
        self.arm_move(self.positions["放置蓝色"], 1000)

    def action_full_grab_sequence(self):
        """完整的抓取序列"""
        print("执行完整抓取序列")
        self.action_ready()
        time.sleep(0.5)
        self.action_grab()
        time.sleep(0.5)
        self.action_move_up()

    def action_sort_yellow(self):
        """分拣到黄色区域的完整流程"""
        print("执行黄色分拣流程")
        self.action_full_grab_sequence()
        self.action_place_yellow()
        self.action_release()
        self.action_move_up()

    def action_sort_red(self):
        """分拣到红色区域的完整流程"""
        print("执行红色分拣流程")
        self.action_full_grab_sequence()
        self.action_place_red()
        self.action_release()
        self.action_move_up()

    def action_sort_green(self):
        """分拣到绿色区域的完整流程"""
        print("执行绿色分拣流程")
        self.action_full_grab_sequence()
        self.action_place_green()
        self.action_release()
        self.action_move_up()

    def action_sort_blue(self):
        """分拣到蓝色区域的完整流程"""
        print("执行蓝色分拣流程")
        self.action_full_grab_sequence()
        self.action_place_blue()
        self.action_release()
        self.action_move_up()

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
    """使用大模型理解语音指令，返回动作关键词"""
    global voice_arm
    
    # 获取所有可用的动作命令
    available_actions = list(voice_arm.action_commands.keys())
    actions_str = "、".join(available_actions)
    
    system_prompt = f"""你是一个机械臂控制助手。用户会给你语音指令，你需要从以下预定义的动作命令中选择最合适的一个：

可用动作命令：
{actions_str}

请根据用户指令，只返回一个最匹配的动作关键词。如果无法匹配，返回"未知"。

示例：
- 用户说"向上移动" -> 返回：向上
- 用户说"夹住物体" -> 返回：夹取  
- 用户说"放到红色区域" -> 返回：红色
- 用户说"开始抓取流程" -> 返回：完整抓取
- 用户说"分拣蓝色物品" -> 返回：分拣蓝色

只返回动作关键词，不要返回其他内容。"""

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
        
        # 清理可能的markdown格式
        result = re.sub(r'```.*?```', '', result, flags=re.DOTALL)
        result = re.sub(r'`([^`]+)`', r'\1', result)
        result = result.strip()
        
        print(f"大模型理解结果: {result}")
        return result
            
    except Exception as e:
        print(f"大模型调用错误: {e}")
        return "未知"

def execute_command(action_keyword):
    """根据动作关键词执行对应的机械臂动作"""
    global voice_arm
    
    try:
        if action_keyword in voice_arm.action_commands:
            print(f"执行动作: {action_keyword}")
            voice_arm.action_commands[action_keyword]()
        else:
            print(f"未知动作: {action_keyword}")
            print(f"可用动作: {', '.join(voice_arm.action_commands.keys())}")
            
    except Exception as e:
        print(f"执行动作时出错: {e}")

def get_audio_devices():
    """获取可用的音频设备"""
    p = pyaudio.PyAudio()
    devices = []
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if device_info['maxInputChannels'] > 0:  # 只显示输入设备
            devices.append({
                'index': i,
                'name': device_info['name'],
                'channels': device_info['maxInputChannels'],
                'rate': device_info['defaultSampleRate']
            })
    p.terminate()
    return devices

def test_audio_device(device_index=None):
    """测试音频设备是否可用"""
    try:
        p = pyaudio.PyAudio()
        
        # 如果没有指定设备，使用默认设备
        if device_index is None:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024
            )
        else:
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=1024
            )
        
        # 测试录音
        data = stream.read(1024)
        stream.stop_stream()
        stream.close()
        p.terminate()
        return True, "音频设备测试成功"
        
    except Exception as e:
        if p:
            p.terminate()
        return False, f"音频设备测试失败: {e}"

def on_open(ws):
    """WebSocket连接建立时的处理"""
    def run(*args):
        global voice_arm
        status = voice_arm.STATUS_FIRST_FRAME
        
        CHUNK = 520
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        try:
            # 获取可用音频设备
            devices = get_audio_devices()
            print(f"找到 {len(devices)} 个音频输入设备:")
            for device in devices:
                print(f"  设备 {device['index']}: {device['name']}")
            
            # 尝试使用音频设备
            p = pyaudio.PyAudio()
            stream = None
            
            # 首先尝试默认设备
            try:
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK
                )
                print("使用默认音频设备")
            except Exception as e:
                print(f"默认音频设备失败: {e}")
                
                # 尝试其他可用设备
                for device in devices:
                    try:
                        stream = p.open(
                            format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            input=True,
                            input_device_index=device['index'],
                            frames_per_buffer=CHUNK
                        )
                        print(f"使用音频设备: {device['name']}")
                        break
                    except Exception as device_error:
                        print(f"设备 {device['index']} 失败: {device_error}")
                        continue
            
            if stream is None:
                print("错误: 无法找到可用的音频设备")
                print("请检查麦克风连接或尝试文本模式")
                voice_arm.is_listening = False
                p.terminate()
                return
                
        except Exception as init_error:
            print(f"音频初始化失败: {init_error}")
            print("切换到文本输入模式")
            voice_arm.is_listening = False
            return
        
        print("开始语音识别...")
        voice_arm.is_listening = True
        
        try:
            for i in range(0, int(RATE/CHUNK*10)):  # 10秒录音
                if not voice_arm.is_running:
                    break
                    
                try:
                    buf = stream.read(CHUNK, exception_on_overflow=False)
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
                        
                except Exception as read_error:
                    print(f"读取音频数据出错: {read_error}")
                    break
                    
        except Exception as record_error:
            print(f"录音过程出错: {record_error}")
        finally:
            try:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if p:
                    p.terminate()
            except:
                pass
            voice_arm.is_listening = False
            print("录音结束")
        
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
                action_keyword = understand_command(result)
                execute_command(action_keyword)
                
    except Exception as e:
        print(f"解析语音识别结果时出错: {e}")

def on_error(ws, error):
    """WebSocket错误处理"""
    print(f"WebSocket错误: {error}")

def on_close(ws, close_status_code=None, close_msg=None):
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
    print("4. 'audio' - 检测音频设备")
    print("5. 'actions' - 显示所有可用动作")
    print("6. 'quit' - 退出系统")
    print("7. 或直接说出控制指令，如：'准备'、'抓取'、'分拣红色'等")
    
    # 首先检测音频设备
    print("\n正在检测音频设备...")
    try:
        devices = get_audio_devices()
        if devices:
            print(f"找到 {len(devices)} 个可用音频设备:")
            for device in devices:
                print(f"  设备 {device['index']}: {device['name']}")
            
            # 测试默认音频设备
            success, message = test_audio_device()
            if success:
                print("✓ 音频设备正常，可以使用语音控制")
            else:
                print(f"✗ 音频设备测试失败: {message}")
                print("建议使用文本输入模式进行测试")
        else:
            print("✗ 未找到可用的音频输入设备")
            print("系统将只支持文本输入模式")
    except Exception as e:
        print(f"✗ 音频设备检测失败: {e}")
        print("系统将只支持文本输入模式")
    
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
                voice_arm.action_ready()
                time.sleep(1)
                voice_arm.action_grab()
                time.sleep(1)
                voice_arm.action_release()
                voice_arm.action_init()
                print("测试完成")
                
            elif cmd == 'reset':
                print("重置机械臂位置...")
                voice_arm.init_arm()
                
            elif cmd == 'actions':
                print("可用动作命令:")
                for i, action in enumerate(voice_arm.action_commands.keys(), 1):
                    print(f"  {i:2d}. {action}")
                
            elif cmd == 'audio':
                print("检测音频设备...")
                try:
                    devices = get_audio_devices()
                    if devices:
                        print(f"找到 {len(devices)} 个音频设备:")
                        for device in devices:
                            success, message = test_audio_device(device['index'])
                            status = "✓" if success else "✗"
                            print(f"  {status} 设备 {device['index']}: {device['name']} - {message}")
                    else:
                        print("未找到音频输入设备")
                except Exception as e:
                    print(f"音频设备检测失败: {e}")
                
            elif cmd:
                # 直接处理文本指令
                print(f"处理指令: {cmd}")
                action_keyword = understand_command(cmd)
                execute_command(action_keyword)
                
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