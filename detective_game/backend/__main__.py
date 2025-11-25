"""Entry point for running the backend server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "detective_game.backend.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
