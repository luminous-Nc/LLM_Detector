# Repository Guidelines

## Project Structure & Module Organization
- `detective_game/backend/`: FastAPI app, game state manager, persona actors, story hooks, and LLM clients. Entry point: `detective_game/backend/app.py`.
- `detective_game/frontend/`: Minimal HTML prototype that calls backend REST endpoints.
- `detective_game/requirements.txt`: Python dependencies for the backend runtime.
- `README.md`: Quick-start instructions; sync any run-command updates here.

## Build, Test, and Development Commands
- `pip install -r detective_game/requirements.txt` – set up backend environment.
- `python -m detective_game.backend` – run FastAPI dev server with live reload via uvicorn.
- `python -m http.server --directory detective_game/frontend 5173` – simple static server for the web UI (adjust port as needed).
- `pytest` – placeholder for backend tests once added (create under `tests/`).

## Coding Style & Naming Conventions
- Python code follows PEP 8 with 4-space indentation; keep line length ≤ 100 chars.
- Use descriptive module names (`story_manager.py`, `persona.py`) aligning with functionality.
- Prefer dataclasses for state containers (`detective_game/backend/models.py`) and type hints throughout.
- When introducing formatting/linting, configure tools (e.g., `black`, `ruff`) in project root and document usage here.

## Testing Guidelines
- Place automated tests in `tests/` mirroring package layout, e.g., `tests/backend/test_game_state.py`.
- Use `pytest` for unit and integration tests; target baseline coverage of core turn logic and persona behaviors.
- Name test functions descriptively (`test_apply_player_action_moves_player`).
- For LLM interactions, provide mock clients (see `EchoLLMClient`) to keep tests deterministic.

## Commit & Pull Request Guidelines
- Write commits in imperative mood (`Add story manager rule handling`); keep scope focused.
- Reference issues in commit body when applicable (`Refs #12`).
- Pull requests should include: summary of changes, testing evidence (commands + results), and screenshots or logs if UI/behavior changes.
- Request review when CI (once configured) is green; respond promptly to feedback and squash before merge if history is noisy.

