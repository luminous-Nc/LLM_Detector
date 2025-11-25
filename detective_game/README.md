# LLM 侦探原型

一个基于回合制、地点抽象的轻量 LLM 侦探游戏原型，前端为简易网页，后端使用 FastAPI 管理游戏状态并调用（或模拟）大语言模型驱动 NPC 行为。

## 目录结构

```
detective_game/
├── backend/          # FastAPI 应用、状态管理、Persona 逻辑
├── frontend/         # 极简网页原型
├── requirements.txt  # 后端依赖
└── README.md
```

## 快速开始

1. 创建并激活虚拟环境（可选）。
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 运行开发服务器（自动监听 8000 端口）：
   ```bash
   python -m detective_game.backend
   ```
4. 另开终端启动前端静态服务（5173 端口）：
   ```bash
   python -m http.server 5173 --directory detective_game/frontend
   ```
5. 在浏览器访问 `http://127.0.0.1:5173/index.html`，即可与后端交互。

> 如果需要真实的 LLM 输出，请在环境中设置 `OPENAI_API_KEY`。未设置时将使用 `EchoLLMClient` 返回占位回复。

## 核心模块

- `backend/game_state.py`  
  管理游戏全局状态（地点、线索、Persona 所在位置等），提供玩家动作接口与快照。
- `backend/persona.py`  
  参考原项目的 Persona 结构，封装 NPC 的观测、提示生成与 LLM 调用流程。
- `backend/story_manager.py`  
  简化的剧情触发器，可根据当前状态追加叙事事件。
- `backend/app.py`  
  FastAPI 入口，提供 `/api/state` 与 `/api/action`，协调玩家动作、NPC 回合与剧情评估。

## 下一步建议

- 丰富 `StoryManager` 的规则（基于 YAML/JSON 编排案件流程）。
- 为 Persona 增加记忆存取与自省逻辑（直接复用原仓库的 `AssociativeMemory` 等模块）。
- 将当前 Mock 的 Echo LLM 替换为真实模型，并完善 prompt 模板表达。
- 为前端加入更好的状态展示、对话历史与线索图谱。
