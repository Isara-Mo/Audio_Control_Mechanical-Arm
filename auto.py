import time
import json
import re
import threading
import queue
import ssl
import hashlib
import base64
import hmac
from urllib.parse import urlencode
from datetime import datetime
from time import mktime
import _thread as thread
import pyaudio
import websocket
from typing import List, Dict, Any

# --- 1. 导入 LangChain 核心组件 ---
from langchain_community.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.documents import Document
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import FakeEmbeddings # 使用假嵌入进行演示
from langchain_core.retrievers import BaseRetriever

# =======================================================
# ========== 硬件模拟与 LangChain Tools (与上一版本相同) ==========
# =======================================================

class ArmDeviceSimulator:
    """模拟 Arm_Lib 机械臂设备"""
    def __init__(self):
        print("🛠️ ArmDeviceSimulator: 机械臂硬件模拟初始化。")
        self.positions = {
            "初始位置": [90, 130, 0, 0, 90],
            "准备位置": [90, 80, 50, 50, 270],
            "抓取位置": [90, 53, 33, 36, 270],
            "放置黄色": [65, 22, 64, 56, 270],
            "放置红色": [117, 19, 66, 56, 270],
            "放置绿色": [136, 66, 20, 29, 270],
            "放置蓝色": [44, 66, 20, 28, 270],
        }
        self.current_action = "init"
        self.init_arm()

    def Arm_serial_servo_write(self, servo_id, angle, s_time):
        print(f"  [ARM_MOVE_SIM] 舵机 {servo_id} 移动到 {angle} (耗时: {s_time/1000}s)")

    def arm_clamp_block(self, enable: int):
        action = "夹紧夹爪" if enable == 1 else "松开夹爪"
        print(f"  [ARM_CLAMP_SIM] {action}")
        self.Arm_serial_servo_write(6, 130 if enable == 1 else 60, 400)

    def arm_move(self, position: List[int], s_time: int = 500):
        print(f"  [ARM_MOVE_SIM] 移动到位置: {position} (耗时: {s_time/1000}s)")
        for i, angle in enumerate(position):
            servo_id = i + 1
            self.Arm_serial_servo_write(servo_id, angle, s_time)

    def arm_move_up(self):
        print("  [ARM_MOVE_SIM] 机械臂向上抬升...")
        self.Arm_serial_servo_write(2, 90, 1500)
        self.Arm_serial_servo_write(3, 90, 1500)
        self.Arm_serial_servo_write(4, 90, 1500)

    def init_arm(self):
        print("  [SYSTEM] 正在初始化机械臂...")
        self.arm_clamp_block(0)
        self.arm_move(self.positions["初始位置"], 1000)
        self.current_action = "init"
        print("  [SYSTEM] 机械臂初始化完成")

ARM_DEVICE = ArmDeviceSimulator()

# 机械臂动作工具 (LangChain Tool) - 仅列举部分，其余类似
@tool
def action_init() -> str:
    """初始化机械臂到初始位置，执行复位或重置操作。"""
    print("✅ Tool Call: action_init")
    ARM_DEVICE.arm_clamp_block(0)
    ARM_DEVICE.arm_move(ARM_DEVICE.positions["初始位置"], 1000)
    return "机械臂已初始化并复位到初始位置。"

@tool
def action_ready() -> str:
    """移动机械臂到准备/待机位置，准备接收抓取指令。"""
    print("✅ Tool Call: action_ready")
    ARM_DEVICE.arm_move(ARM_DEVICE.positions["准备位置"], 1000)
    return "机械臂已移动到准备/待机位置。"

@tool
def action_grab() -> str:
    """移动机械臂到抓取位置，并夹紧夹爪，执行夹取操作。"""
    print("✅ Tool Call: action_grab")
    ARM_DEVICE.arm_move(ARM_DEVICE.positions["抓取位置"], 1000)
    ARM_DEVICE.arm_clamp_block(1)
    return "机械臂已移动到抓取位置并夹紧夹爪。"

@tool
def action_release() -> str:
    """松开夹爪，释放夹取的物体。"""
    print("✅ Tool Call: action_release")
    ARM_DEVICE.arm_clamp_block(0)
    return "机械臂已松开夹爪，释放物体。"

@tool
def action_sort_yellow() -> str:
    """执行分拣黄色物品的完整流程：完整抓取序列 -> 放置黄色 -> 释放 -> 向上抬升。"""
    print("✅ Tool Call: action_sort_yellow")
    # 模拟组合动作的调用
    action_ready()
    action_grab()
    ARM_DEVICE.arm_move_up() 
    ARM_DEVICE.arm_move(ARM_DEVICE.positions["放置黄色"], 1000)
    action_release()
    ARM_DEVICE.arm_move_up() 
    return "黄色分拣流程已执行。"

# 完整的工具列表
ALL_ARM_TOOLS = [
    action_init, action_ready, action_grab, action_release, 
    action_sort_yellow, # ... 其他所有动作都应该在此处列出
]

# RAG 数据源创建 (用于增强 Agent 的意图识别)
action_data = [
    ("初始化", "action_init", "执行初始化动作，复位，重置，回到初始位置"),
    ("准备", "action_ready", "执行准备动作，待机，准备接收指令"),
    ("抓取", "action_grab", "移动到抓取位置并夹紧，夹取，夹住"),
    ("释放", "action_release", "松开夹爪，放开，释放物体"),
    ("向上移动", "action_move_up", "向上抬升，上升，升高，抬高机械臂"),
    ("分拣黄色", "action_sort_yellow", "分拣到黄色区域的完整流程，黄色分拣，将物体放到黄色的地方"),
    # ... 其他动作
]

rag_documents = []
for name, id_func, description in action_data:
    content = f"动作名: {name}. 功能描述/别名: {description}"
    rag_documents.append(
        Document(
            page_content=content,
            metadata={"action_name": name, "tool_name": id_func}
        )
    )

vector_store = InMemoryVectorStore.from_documents(
    rag_documents,
    embedding=FakeEmbeddings(size=128)
)
RAG_RETRIEVER = vector_store.as_retriever(k=3)

# Agent 执行函数
def setup_langchain_agent(llm, tools: List, retriever: BaseRetriever):
    """设置 LangChain Agent"""
    RAG_CONTEXT_PROMPT = """
    你是一个机械臂控制助手。你的任务是根据用户的指令（来自语音或文本），选择合适的工具（机械臂动作）来执行。
    
    请参考以下从RAG数据库中检索到的相关机械臂动作描述，它们包含动作名称、对应的工具ID和别名描述：
    
    --- RAG 上下文 (动作描述和ID) ---
    {context}
    ---
    
    请根据用户的最终指令，选择最合适的工具进行调用。如果指令与机械臂动作无关，请礼貌地回复。
    
    用户指令:
    """

    prompt = ChatPromptTemplate.from_messages([
        ("system", RAG_CONTEXT_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_openai_tools_agent(llm=llm, tools=tools, prompt=prompt)

    # 返回一个可调用的函数，用于执行 Agent
    def run_agent(input_text: str):
        print(f"\n🧠 Agent 正在处理指令: '{input_text}'...")
        # 1. 执行 RAG 检索
        retrieved_docs = retriever.invoke(input_text)
        context = "\n".join([f"- 动作名: {doc.metadata['action_name']}, 对应ID: {doc.metadata['tool_name']}, 描述: {doc.page_content}" for doc in retrieved_docs])
        
        # 2. 调用 Agent Executor
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        try:
            result = agent_executor.invoke({"input": input_text, "context": context})
            print(f"🤖 Agent 最终响应: {result['output']}")
            return result
        except Exception as e:
            print(f"🚨 Agent 执行失败: {e}")
            return {"output": "抱歉，执行机械臂动作时发生错误。"}

    return run_agent

# =======================================================
# ========== 讯飞语音识别模块 (集成) ==========
# =======================================================

class ASRClient:
    """集成语音识别和 Agent 逻辑的客户端"""
    
    def __init__(self, run_agent_func):
        self.run_agent_func = run_agent_func
        
        # 语音识别参数
        self.STATUS_FIRST_FRAME = 0
        self.STATUS_CONTINUE_FRAME = 1
        self.STATUS_LAST_FRAME = 2
        self.is_running = True
        self.is_listening = False
        
        # 讯飞 API 参数 (请替换为您的真实密钥)
        self.APPID = '45099785'
        self.APIKey = ''
        self.APISecret = ''
        self.ws_param = self._get_ws_param()

    def _get_ws_param(self):
        """生成讯飞 WebSocket 连接参数"""
        class Ws_Param_Internal:
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
                
                signature_origin = f"host: ws-api.xfyun.cn\ndate: {date}\nGET /v2/iat HTTP/1.1"
                
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
                return url + '?' + urlencode(v)
        return Ws_Param_Internal(self.APPID, self.APIKey, self.APISecret)

    def on_open(self, ws):
        """WebSocket连接建立时的处理"""
        def run(*args):
            status = self.STATUS_FIRST_FRAME
            
            CHUNK = 520
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            
            p = None
            stream = None
            try:
                p = pyaudio.PyAudio()
                # 尝试使用默认设备
                stream = p.open(
                    format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    exception_on_overflow=False # 容忍缓冲区溢出
                )
                print("🔊 麦克风已打开，开始录音...")
                self.is_listening = True
                
                # 10秒录音循环
                for i in range(0, int(RATE/CHUNK*10)):
                    if not self.is_running:
                        break
                        
                    buf = stream.read(CHUNK, exception_on_overflow=False)
                    
                    if status == self.STATUS_FIRST_FRAME:
                        d = {
                            "common": self.ws_param.CommonArgs,
                            "business": self.ws_param.BusinessArgs,
                            "data": {
                                "status": 0,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                        ws.send(json.dumps(d))
                        status = self.STATUS_CONTINUE_FRAME
                        
                    elif status == self.STATUS_CONTINUE_FRAME:
                        d = {
                            "data": {
                                "status": 1,
                                "format": "audio/L16;rate=16000",
                                "audio": str(base64.b64encode(buf), 'utf-8'),
                                "encoding": "raw"
                            }
                        }
                        ws.send(json.dumps(d))
                        
                # 最后一帧
                if self.is_running:
                    d = {
                        "data": {
                            "status": 2,
                            "format": "audio/L16;rate=16000",
                            "audio": str(base64.b64encode(buf), 'utf-8'),
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(d))
                    time.sleep(1) # 等待结果返回
            
            except Exception as e:
                print(f"🚨 录音或WebSocket发送出错: {e}")
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if p:
                    p.terminate()
                self.is_listening = False
                print("🎙️ 录音结束，等待识别结果...")
                
        thread.start_new_thread(run, ())

    def on_message(self, ws, message):
        """收到语音识别结果的处理 - 意图识别的核心入口"""
        try:
            data_json = json.loads(message)
            code = data_json["code"]
            
            if code != 0:
                print(f"🚨 讯飞 API 错误: {data_json.get('message', '未知错误')}")
            else:
                ws_data = data_json["data"]["result"]["ws"]
                final_text = "".join([w["w"] for i in ws_data for w in i["cw"]])
                
                if final_text and final_text not in ['。', '.。', ' .。', ' 。']:
                    print(f"\n🗣️ 识别结果: {final_text}")
                    # --- 核心：将 ASR 结果传递给 LangChain Agent ---
                    self.run_agent_func(final_text)
                    
        except Exception as e:
            print(f"🚨 解析语音识别结果时出错: {e}")

    def on_error(self, ws, error):
        print(f"🚨 WebSocket错误: {error}")

    def on_close(self, ws, close_status_code=None, close_msg=None):
        print("🔌 语音识别连接已关闭")
        self.is_listening = False
        
    def start_voice_recognition_thread(self):
        """在独立线程中启动 WebSocket"""
        if self.is_listening:
            print("⚠️ 语音识别已在运行中。")
            return
            
        print("🌐 正在连接讯飞语音识别服务...")
        wsUrl = self.ws_param.create_url()
        ws = websocket.WebSocketApp(
            wsUrl,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        ws.on_open = self.on_open
        # 使用单独的线程运行，不阻塞主程序
        threading.Thread(target=ws.run_forever, daemon=True, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}, "ping_timeout": 2}).start()

# =======================================================
# ========== 主程序与命令行界面 ==========
# =======================================================

def main():
    """主函数"""
    
    # 初始化 LLM (请替换为您的真实密钥)
    try:
        llm = ChatOpenAI(
            model="deepseek-chat",
            openai_api_key="",
            openai_api_base="https://api.deepseek.com",
            temperature=0
        )
        print("✅ LangChain LLM 初始化成功。")
    except Exception as e:
        print(f"❌ LangChain LLM 初始化失败，请检查密钥或网络: {e}")
        return

    # 设置 Agent
    run_agent_function = setup_langchain_agent(llm, ALL_ARM_TOOLS, RAG_RETRIEVER)
    
    # 初始化 ASR 客户端 (包含 LangChain Agent 的调用逻辑)
    asr_client = ASRClient(run_agent_function)
    
    print("\n" + "="*50)
    print("=== LangChain Agent + RAG + 语音控制系统启动 ===")
    print("="*50)

    # 命令行界面循环
    while asr_client.is_running:
        try:
            cmd = input("\n请输入命令 ('start' 语音识别, 'quit' 退出): ").strip()
            
            if cmd == 'quit':
                print("正在关闭系统...")
                asr_client.is_running = False
                break
            
            elif cmd == 'start':
                asr_client.start_voice_recognition_thread()
            
            elif cmd == 'test':
                print("执行测试动作: 分拣黄色")
                run_agent_function("请帮我分拣黄色的物品")
            
            elif cmd == 'reset':
                print("重置机械臂位置...")
                action_init()
                
            elif cmd:
                # 文本指令直接进入 Agent 流程
                run_agent_function(cmd)
                
        except KeyboardInterrupt:
            print("\n用户中断，系统退出。")
            asr_client.is_running = False
            break
        except Exception as e:
            print(f"命令处理错误: {e}")
            
if __name__ == '__main__':
    main()