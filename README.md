# Local AI Office

A local multi-agent AI workspace. A **Boss** agent plans your request, hands tasks to
**Researcher**, **Coder** and **Analyst** workers, and you watch the whole team work in a
live, animated office. Everything runs on your machine with a local LLM.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# start your local OpenAI-compatible model server (oMLX by default, port 8000)
uvicorn backend.main:app --reload --port 8080
```

Open <http://localhost:8080/office/office.html>.

The model server URL and model name live in `backend/llm/llama_cpp_client.py`
(default `http://127.0.0.1:8000`, `qwen3-1.7b`).

## Layout

| Path | What it is |
|------|-----------|
| `backend/agents` | Boss, Coder, Researcher, Analyst and generic agents |
| `backend/core` | Task manager, dispatcher, event/message buses, artifacts |
| `backend/api` | REST routes and the WebSocket bridge |
| `frontend/office` | The office UI (`office.html`, `office.css`, `office.js`) |
| `tests` | pytest suite |

## The UI

- **Office** – live scene; agents walk to the Boss to get tasks and return to their desks.
- **Agents / Tasks / Settings** – roster, task history with filters, display options.
- Add or remove agents from the sidebar; generated projects appear in the workspace panel.
