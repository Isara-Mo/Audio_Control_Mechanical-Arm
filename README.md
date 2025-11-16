# Audio Control Mechanical Arm / 语音控制机械臂系统

<div align="right">
[English](#english) | [中文](#中文)
</div>

---

<a name="english"></a>
# Audio Control Mechanical Arm

A voice-controlled robotic arm system that uses speech recognition and AI to understand and execute commands. The system supports predefined actions such as grabbing, placing, and sorting objects by color.

## ✨ Key Features

- 🎤 **Voice Recognition**: Real-time speech-to-text using Xunfei (iFlytek) API
- 🤖 **AI Command Understanding**: Uses DeepSeek AI to interpret natural language commands
- 🦾 **Predefined Actions**: Supports multiple predefined arm movements and sequences
- 🎨 **Color Sorting**: Automatic sorting of objects by color (yellow, red, green, blue)
- ⌨️ **Text Input Mode**: Fallback to text commands when audio is unavailable
- 🔧 **Audio Device Detection**: Automatic detection and testing of audio input devices

## 📋 Requirements

- Python 3.7+
- Mechanical arm hardware (compatible with Arm_Lib)
- Microphone for voice input
- Xunfei (iFlytek) API credentials for speech recognition
- DeepSeek API key for AI command understanding

## 📦 Installation

### 1. Install Dependencies

```bash
pip install websocket-client pyaudio openai
```

### 2. Configure API Keys

Edit `auto.py` and update the following:

- **Xunfei API**: Update `APPID`, `APIKey`, and `APISecret` in the `start_voice_recognition()` function
- **DeepSeek API**: Update `api_key` in the `VoiceControlledArm.__init__()` method

> ⚠️ **Warning**: Make sure to keep your API keys secure. Consider using environment variables or a configuration file instead of hardcoding them.

## 🚀 Usage

### Basic Usage

```bash
python auto.py
```

### Available Commands

| Command | Description |
|---------|-------------|
| `start` | Start voice recognition |
| `test` | Test arm movements |
| `reset` | Reset arm to initial position |
| `audio` | Detect and test audio devices |
| `actions` | Display all available actions |
| `quit` | Exit the system |

### Voice Commands

You can also directly speak commands or type them in the console. Supported commands include:

- **Basic Actions**: 初始化 (Initialize), 准备 (Ready), 抓取 (Grab), 松开 (Release), 向上 (Move Up)
- **Color Sorting**: 黄色 (Yellow), 红色 (Red), 绿色 (Green), 蓝色 (Blue)
- **Combined Actions**: 完整抓取 (Full Grab Sequence), 分拣黄色 (Sort Yellow), etc.

## 🎯 Predefined Actions

The system includes the following predefined positions and actions:

- **Initial Position**: [90, 130, 0, 0, 90]
- **Ready Position**: [90, 80, 50, 50, 270]
- **Grab Position**: [90, 53, 33, 36, 270]
- **Color Placement Positions**: Yellow, Red, Green, Blue

## 🔧 Project Structure

```
Audio_Control_Mechanical-Arm/
├── auto.py              # Main application file
└── test/                # Test files
    ├── AIAPI-test.py    # AI API test
    ├── function_test1.py
    ├── function_test2.py
    └── sst-test.py      # Speech recognition test
```

## 📝 How It Works

1. **Voice Input**: The system captures audio from the microphone
2. **Speech Recognition**: Audio is sent to Xunfei API for speech-to-text conversion
3. **Command Understanding**: The transcribed text is sent to DeepSeek AI to extract the action keyword
4. **Action Execution**: The system executes the corresponding predefined arm movement

> 💡 **Tip**: If audio input is not available, you can type commands directly in the console. The system will process them the same way as voice commands.

## 🐛 Troubleshooting

### Audio Device Issues

- Run `audio` command to detect available audio devices
- Check microphone permissions in your system settings
- Try using text input mode if audio is unavailable

### API Connection Issues

- Verify your API keys are correct
- Check your internet connection
- Ensure you have sufficient API credits

## 📄 License

This project is open source. Please refer to the license file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<a name="中文"></a>
# 语音控制机械臂系统

一个使用语音识别和人工智能来理解和执行命令的语音控制机械臂系统。系统支持多种预定义动作，如抓取、放置和按颜色分拣物体。

## ✨ 主要特性

- 🎤 **语音识别**: 使用讯飞（iFlytek）API进行实时语音转文字
- 🤖 **AI命令理解**: 使用DeepSeek AI来理解自然语言命令
- 🦾 **预定义动作**: 支持多种预定义的机械臂运动和序列
- 🎨 **颜色分拣**: 按颜色自动分拣物体（黄色、红色、绿色、蓝色）
- ⌨️ **文本输入模式**: 当音频不可用时，可回退到文本命令模式
- 🔧 **音频设备检测**: 自动检测和测试音频输入设备

## 📋 系统要求

- Python 3.7+
- 机械臂硬件（兼容Arm_Lib）
- 用于语音输入的麦克风
- 用于语音识别的讯飞（iFlytek）API凭证
- 用于AI命令理解的DeepSeek API密钥

## 📦 安装

### 1. 安装依赖

```bash
pip install websocket-client pyaudio openai
```

### 2. 配置API密钥

编辑 `auto.py` 并更新以下内容：

- **讯飞API**: 在 `start_voice_recognition()` 函数中更新 `APPID`、`APIKey` 和 `APISecret`
- **DeepSeek API**: 在 `VoiceControlledArm.__init__()` 方法中更新 `api_key`

> ⚠️ **警告**: 请确保妥善保管您的API密钥。考虑使用环境变量或配置文件，而不是硬编码在代码中。

## 🚀 使用方法

### 基本使用

```bash
python auto.py
```

### 可用命令

| 命令 | 描述 |
|------|------|
| `start` | 开始语音识别 |
| `test` | 测试机械臂动作 |
| `reset` | 重置机械臂到初始位置 |
| `audio` | 检测和测试音频设备 |
| `actions` | 显示所有可用动作 |
| `quit` | 退出系统 |

### 语音命令

您也可以直接说出命令或在控制台中输入。支持的命令包括：

- **基础动作**: 初始化、准备、抓取、松开、向上
- **颜色分拣**: 黄色、红色、绿色、蓝色
- **组合动作**: 完整抓取、分拣黄色等

## 🎯 预定义动作

系统包含以下预定义位置和动作：

- **初始位置**: [90, 130, 0, 0, 90]
- **准备位置**: [90, 80, 50, 50, 270]
- **抓取位置**: [90, 53, 33, 36, 270]
- **颜色放置位置**: 黄色、红色、绿色、蓝色

## 🔧 项目结构

```
Audio_Control_Mechanical-Arm/
├── auto.py              # 主应用程序文件
└── test/                # 测试文件
    ├── AIAPI-test.py    # AI API测试
    ├── function_test1.py
    ├── function_test2.py
    └── sst-test.py      # 语音识别测试
```

## 📝 工作原理

1. **语音输入**: 系统从麦克风捕获音频
2. **语音识别**: 音频被发送到讯飞API进行语音转文字转换
3. **命令理解**: 转录的文本被发送到DeepSeek AI以提取动作关键词
4. **动作执行**: 系统执行相应的预定义机械臂运动

> 💡 **提示**: 如果音频输入不可用，您可以直接在控制台中输入命令。系统将以与语音命令相同的方式处理它们。

## 🐛 故障排除

### 音频设备问题

- 运行 `audio` 命令以检测可用的音频设备
- 检查系统设置中的麦克风权限
- 如果音频不可用，尝试使用文本输入模式

### API连接问题

- 验证您的API密钥是否正确
- 检查您的互联网连接
- 确保您有足够的API额度

## 📄 许可证

本项目是开源的。详细信息请参阅许可证文件。

## 🤝 贡献

欢迎贡献！请随时提交Pull Request。

---

<div align="center">
[返回顶部](#audio-control-mechanical-arm--语音控制机械臂系统)
</div>
