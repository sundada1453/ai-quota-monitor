# AI Quota Monitor (AI 配额实时监控桌面悬浮窗)

一款轻量、极简且精准的桌面端 AI 配额监控悬浮窗工具。专为高频使用 **xAI Grok** 与 **Google Antigravity (AGY)** 的开发者打造，支持全桌面置顶、多模式切换、鼠标任意拖拽与官方数据源实时直连。

---

## 📸 界面预览

![AI Quota Monitor 预览](preview.png)

* **卡片完整视图**：展示各模型额度百分比、彩色渐变进度条、详细重置倒计时及连接状态。
* **极简胶囊视图**：双击卡片即可折叠为极窄单行胶囊，不遮挡代码与工作区，随时掌握额度动态。

---

## ✨ 核心特性

- ⚡ **Grok 官方周额度 100% 精确对齐**：
  - 逆向直连 xAI 官方账单管理接口（与 Orca / Codex 桌面端底层数据源完全同源）。
  - 精确获取真实周已用比例（涵盖 `GrokPlugins`、`GrokBuild`、`GrokChat` 等细分用量）与准确的重置倒计时。
- 🤖 **Antigravity (AGY) 双维度实时监控**：
  - 同时展示 **5 小时短期平滑额度** 与 **每周总额度**。
  - **三级自适应探测架构**：
    1. **第一级（本地直连）**：自动探测本机运行中的 Antigravity 桌面端 `LanguageServer` 进程，通过内部 ConnectRPC 协议通信，携带 `forceRefresh: true` 穿透客户端静态快照，获取真实实时的消耗数据；
    2. **第二级（云端接口）**：本地桌面端未运行时，自动回退到 Google 官方 `daily-cloudcode-pa` 端点获取；
    3. **第三级（CLI 兜底）**：无缝降级到本地 `agy -p /usage` 命令行解析。
- 🎨 **优雅精致的桌面交互**：
  - **无边框毛玻璃暗黑风**：契合现代 IDE 与终端设计风格，高对比度色彩提示。
  - **智能警示进度条**：常规蓝色/绿色/紫色展示，用量超过 75% 自动转为橙色警示，超过 90% 转为红色预警。
  - **双击折叠 / 展开**：在完整卡片视图与极简单行胶囊视图间毫秒级切换。
  - **任意拖拽与记忆**：按住悬浮窗任意区域均可随心拖动放置在屏幕合适位置。
  - **右键便捷菜单**：提供“立即刷新”、“切换模式”、“退出程序”等实用操作。
- 🛡️ **轻量低耗与防抖保护**：
  - 纯原生 Python + Tkinter 实现，零繁重 GUI 框架依赖，内存占用极低（~20MB）。
  - 采集任务在后台守护线程异步执行，主界面永不卡顿；内置内存防抖缓存，避免高频请求触发官方频控限制。

---

## 🚀 快速开始

### 1. 环境准备

系统要求：
- Linux / macOS / Windows（推荐 Linux X11 桌面环境，如 XFCE、GNOME 等）
- Python 3.8 及以上版本
- Tkinter 图形支持库

在 Debian / Ubuntu 系 Linux 上安装 Tkinter：
```bash
sudo apt-get update && sudo apt-get install -y python3-tk
```

### 2. 获取代码与启动

克隆或下载本项目至本地目录：
```bash
git clone https://github.com/sundada1453/ai-quota-monitor.git
cd ai-quota-monitor
```

使用内置的管理脚本 `start.sh` 进行控制：
```bash
# 启动悬浮窗 (默认在后台常驻运行)
bash start.sh start

# 检查当前运行状态
bash start.sh status

# 重启悬浮窗 (修改配置或代码后热重载)
bash start.sh restart

# 停止悬浮窗
bash start.sh stop
```

如果需要在特定的显示端口启动（如远程 VNC 环境）：
```bash
DISPLAY=:1 bash start.sh start
```

---

## 🖱️ 交互快捷指南

| 操作 | 动作响应 |
| :--- | :--- |
| **鼠标左键按住拖动** | 在屏幕任意位置移动悬浮窗 |
| **双击窗口任意位置** | 在 **卡片完整视图** ↔ **极简胶囊视图** 之间快速切换 |
| **鼠标右键单击** | 唤出上下文菜单：手动立即刷新、视图模式切换、退出监控 |

---

## ⚙️ 配置说明 (`config.json`)

项目根目录的 `config.json` 提供了简单灵活的自定义项：

```json
{
  "grok": {
    "weekly_quota_requests": 150,
    "weekly_quota_usd": 15.0,
    "quota_mode": "requests"
  },
  "antigravity": {
    "five_hour_quota_requests": 50,
    "quota_window_hours": 5
  },
  "ui": {
    "refresh_seconds": 10,
    "theme": "dark",
    "always_on_top": true,
    "initial_x": 1050,
    "initial_y": 45
  }
}
```

* `ui.refresh_seconds`：后台自动刷新周期（秒），默认为 10 秒。
* `ui.always_on_top`：是否保持全桌面窗口置顶（`true` / `false`）。
* `ui.initial_x` / `ui.initial_y`：首次启动时悬浮窗在屏幕上的初始 X/Y 像素坐标。

---

## 🔍 技术原理与架构

```text
[ AI Quota Monitor UI (widget.py) ]
                 │ (异步后台线程轮询)
                 ▼
      [ 采集引擎 (collector.py) ]
       ┌─────────┴─────────┐
       ▼                   ▼
 [ Grok 官方账单通道 ]   [ Antigravity 自适应探测通道 ]
       │                   ├─ 优先: 本地 LanguageServer ConnectRPC (127.0.0.1)
       │                   ├─ 其次: Google 官方 CloudCode API
       │                   └─ 兜底: 本地 agy CLI 命令
       ▼
 ~/.grok/auth.json
  (获取 CLI Session Token)
       ▼
 https://cli-chat-proxy.grok.com/v1/billing?format=credits
```

1. **Grok 官方额度获取原理**：
   - 读取本机的 `~/.grok/auth.json` 提取用户的 CLI 认证 Token；
   - 携带 `X-XAI-Token-Auth: xai-grok-cli` 与 `x-userid` 访问 xAI 账单统计端点；
   - 解析返回的 `creditUsagePercent`、各产品细分消耗及周期截止重置时间戳。
2. **Antigravity 桌面端本地直连原理**：
   - 通过系统进程表探测正在运行的 `language_server` 进程与 `--csrf_token` 启动参数；
   - 定位其本地 HTTPS 监听端口，构造带 `x-codeium-csrf-token` 的 ConnectRPC 请求；
   - 调用 `exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary`，传参 `{"forceRefresh": true}`，绕过客户端组件的静态 DOM 缓存，直接拿到最新用量。

---

## 📄 License

本项目基于 [MIT License](LICENSE) 开源。欢迎提交 Issue 与 Pull Request 共同完善！
