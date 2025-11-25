# 🔍 尸人庄谜案 - LLM 侦探游戏

一个基于《尸人庄谜案》设定的回合制 LLM 侦探游戏原型。玩家扮演被困在别墅中的大学生，在丧尸包围和连环杀人案的双重威胁下，通过调查、对话、收集线索来找出隐藏的凶手。

## 🎮 游戏特色

- **动态时间系统**：游戏分为6个时间段（黎明、早上、中午、下午、傍晚、深夜）
- **动态案件**：凶手按预设时间行凶，案件随时间推进发生
- **场景可达性**：某些时段某些场景不可访问（如夜间、丧尸占领等）
- **NPC 自主行动**：NPC 由 LLM 驱动，自主决定移动和行为
- **深度对话**：可与 NPC 对话，出示证据质问
- **线索系统**：调查场景收集证据，逐步揭开真相

## 📁 项目结构

```
detective_game/
├── settings/               # 📁 游戏配置（YAML）
│   ├── actors/             # NPC 角色定义
│   ├── scenes/             # 场景与调查点
│   ├── clues/              # 线索定义
│   ├── timeline/           # 世界事件时间线
│   └── config.yaml         # 全局配置
│
├── backend/                # 📁 FastAPI 后端
│   ├── models/             # 数据模型
│   ├── systems/            # 游戏子系统
│   ├── ai/                 # LLM 客户端与 NPC AI
│   ├── loaders/            # 配置加载器
│   ├── game_manager.py     # 游戏主控制器
│   └── app.py              # FastAPI 入口
│
├── frontend/               # 📁 前端
│   └── index.html          # 单页应用
│
├── requirements.txt
└── README.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd detective_game
pip install -r requirements.txt
```

### 2. 启动后端

```bash
python -m detective_game.backend
```

后端将在 `http://127.0.0.1:8000` 启动。

### 3. 启动前端

```bash
python -m http.server 5173 --directory detective_game/frontend
```

### 4. 访问游戏

打开浏览器访问 `http://127.0.0.1:5173/index.html`

## 🤖 配置 LLM

默认使用 Echo 模式（模拟回复）。要使用真实 LLM：

### Gemini

```bash
export LLM_PROVIDER=gemini
export GEMINI_API_KEY=your_api_key
```

### DeepSeek (via OpenRouter)

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=your_openrouter_key
```

## 🎭 角色设定

游戏包含以下角色：

| 角色 | 身份 | 特点 |
|------|------|------|
| 明智恭介 | 侦探 | 冷静理性的推理高手 |
| 比留子 | 侦探 | 聪明果断的生物学专业学生 |
| 上杉武雄 | 凶手 | 表面稳重的社团社长 |
| 进藤真吾 | 嫌疑人 | 欠债的活跃分子 |
| 白石雪子 | 目击者 | 知道秘密但胆小的小提琴手 |
| 长川诚一 | 受害者 | 发现真相的正义青年 |

## 🗺️ 场景地图

```
                    ┌─────────────┐
                    │  主卧室     │
                    │(需要钥匙)   │
                    └──────┬──────┘
                           │
    ┌─────────┐     ┌──────┴──────┐     ┌─────────┐
    │ 音乐室  │─────│   楼梯      │─────│ 图书室  │
    │(案发点2)│     └──────┬──────┘     └────┬────┘
    └────┬────┘            │                  │
         │           ┌─────┴─────┐      ┌─────┴─────┐
    ┌────┴────┐     │ 入口大厅  │      │  书房    │
    │二楼客房 │     └─────┬─────┘      └──────────┘
    └─────────┘           │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │  客厅     │ │ 餐厅  │ │  庭院     │
        └─────┬─────┘ └───┬───┘ │(危险区域) │
              │           │     └───────────┘
        ┌─────┴─────┐ ┌───┴───┐
        │  厨房     │─│       │
        └─────┬─────┘ └───────┘
              │
        ┌─────┴─────┐
        │  储藏室   │
        │(案发点1)  │
        └───────────┘
```

## 🔧 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/state` | GET | 获取游戏状态 |
| `/api/action` | POST | 执行玩家动作 |
| `/api/conversation/message` | POST | 发送对话消息 |
| `/api/conversation/end` | POST | 结束对话 |
| `/api/clues` | GET | 获取线索列表 |
| `/api/reset` | POST | 重置游戏 |

## 📝 扩展游戏

### 添加新角色

在 `settings/actors/` 中创建新的 YAML 文件：

```yaml
id: new_character
name: 新角色名
role: suspect  # detective/suspect/witness/victim/murderer

public:
  occupation: 职业
  description: 外在描述

private:
  secret: 角色的秘密
  goal: 角色的目标

personality:
  traits: [特点1, 特点2]
  speaking_style: 说话风格

backstory: |
  角色的背景故事...

schedule:
  dawn: location_id
  morning: location_id
  ...
```

### 添加新场景

在 `settings/scenes/` 中创建新的 YAML 文件。

### 添加新线索

在 `settings/clues/` 中添加线索定义。

### 修改时间线事件

编辑 `settings/timeline/main_events.yaml`。

## 📜 License

MIT
