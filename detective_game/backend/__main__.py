"""Run the FastAPI app with uvicorn."""

import argparse
import os
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load .env file from the same directory as this script
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    parser = argparse.ArgumentParser(description="Detective Game Backend")
    parser.add_argument("--llm-provider", choices=["echo", "gemini", "deepseek", "openrouter"], help="LLM Provider to use (default: echo)")
    parser.add_argument("--api-key", help="API Key for the LLM provider")
    parser.add_argument("--model", help="Specific model name (optional)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", default=True, help="Enable auto-reload (default: True)")
    
    args = parser.parse_args()

    # Command line args override environment variables
    if args.llm_provider:
        os.environ["LLM_PROVIDER"] = args.llm_provider
    if args.api_key:
        os.environ["LLM_API_KEY"] = args.api_key
    if args.model:
        os.environ["LLM_MODEL"] = args.model
        
    provider = os.getenv("LLM_PROVIDER", "echo")
    print(f"Starting server with LLM_PROVIDER={provider}")
    uvicorn.run("detective_game.backend.app:app", host=args.host, port=args.port, reload=args.reload)
