"""Entry point for running the goose duck backend server."""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# 加载 .env 文件（优先从 backend 目录，其次从项目根目录）
backend_dir = Path(__file__).parent
project_root = backend_dir.parent

# 尝试加载 backend/.env
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[ENV] 已加载: {env_file}")
else:
    # 尝试项目根目录
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"[ENV] 已加载: {env_file}")
    else:
        print("[ENV] 警告: 未找到 .env 文件")

if __name__ == "__main__":
    app_module = "goose_duck.backend.goose_duck_app:app"
    print("[APP] 启动鹅鸭杀游戏")
    
    uvicorn.run(
        app_module,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
