"""Entry point for running the goose duck backend server."""

from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Load .env file (prefer backend directory, then project root)
backend_dir = Path(__file__).parent
project_root = backend_dir.parent

# Try loading backend/.env
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"[ENV] Loaded: {env_file}")
else:
    # Try project root
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"[ENV] Loaded: {env_file}")
    else:
        print("[ENV] Warning: .env file not found")

if __name__ == "__main__":
    app_module = "goose_duck.backend.goose_duck_app:app"
    print("[APP] Starting Goose Duck Game")
    
    uvicorn.run(
        app_module,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
