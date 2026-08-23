# Havenkeep Setup & Development Guide 🛠️

This document provides step-by-step instructions for installing, configuring, running, and testing **Havenkeep** across different environments (Docker / Podman Compose or Local Native Development).

---

## 1. Prerequisites

Before installing Havenkeep, ensure your system has:

- **Python:** Python 3.11 or higher
- **Container Runtime (Optional but Recommended):** Docker & Docker Compose **or** Podman & Podman Compose
- **Node.js (For Frontend Dev):** Node.js v18.0+ or v20.0+
- **Local LLMs (Optional for Free Testing):** [Ollama](https://ollama.com) with models like `gemma3:latest` or `qwen2.5-coder:3b`

---

## 2. Environment Configuration

Havenkeep supports a **Multi-Supplier Architecture** (Anthropic, OpenAI, Ollama, Google Gemini, Groq, OpenRouter) with support for custom base URLs.

1. **Copy the template configuration file:**
   ```bash
   cp backend/.env.example backend/.env
   ```

2. **Configure your provider keys and settings in `backend/.env`:**

   ```env
   # System Settings
   ENVIRONMENT=development
   PORT=8000
   DATABASE_URL=sqlite+aiosqlite:///./havenkeep.db
   REDIS_URL=redis://localhost:6379/0

   # SUPPLIER API KEYS & CUSTOM BASE URLS
   ANTHROPIC_API_KEY=your_anthropic_key_here
   # ANTHROPIC_BASE_URL=https://api.anthropic.com/v1

   OPENAI_API_KEY=your_openai_key_here
   # OPENAI_BASE_URL=http://localhost:8000/v1  # Points to custom vLLM / LM Studio / LocalAI

   GOOGLE_API_KEY=your_google_key_here
   GROQ_API_KEY=your_groq_key_here
   OPENROUTER_API_KEY=your_openrouter_key_here

   # Local Ollama Provider (100% Free)
   OLLAMA_BASE_URL=http://localhost:11434

   # ROLE MODEL BINDINGS (Assign any provider to any agent role)
   # Model names are optional — if omitted, the provider's standard default model is used.
   SUPERVISOR_PROVIDER=ollama
   SUPERVISOR_MODEL=gemma3:latest

   PLANNER_PROVIDER=anthropic
   PLANNER_MODEL=claude-3-5-sonnet-20240620

   WORKER_PROVIDER=openai
   WORKER_MODEL=gpt-4o-mini

   CRITIC_PROVIDER=ollama
   CRITIC_MODEL=gemma3:latest
   ```

---

## 3. Running Option A: Docker / Podman Compose (Recommended)

Docker/Podman Compose spins up PostgreSQL (with `pgvector`), Redis, FastAPI backend (Port 8000), and Next.js frontend (Port 3000) automatically.

1. **Build and start all services:**
   ```bash
   docker-compose up --build -d
   ```
   *(If using Podman: `podman compose up --build -d`)*

2. **Verify running containers:**
   ```bash
   docker-compose ps
   ```

3. **Access Services:**
   - **Frontend Interactive UI:** `http://localhost:3000`
   - **FastAPI API & Swagger UI:** `http://localhost:8000/docs`
   - **Health Check Endpoint:** `http://localhost:8000/health`

---

## 4. Running Option B: Native Local Development (No Docker)

### 4.1 Backend Setup (FastAPI + LangGraph)

1. **Create and activate a Python virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Run the FastAPI development server:**
   ```bash
   PYTHONPATH=backend uvicorn app.main:app --reload --port 8000
   ```

### 4.2 Frontend Setup (Next.js @ Port 3000)

1. **Navigate to the frontend folder:**
   ```bash
   cd frontend
   ```

2. **Install dependencies and start dev server:**
   ```bash
   npm install
   npm run dev
   ```
   The frontend will run at `http://localhost:3000`.

---

## 5. Testing & Verification

### 5.1 Interactive CLI Harness (Free Local Test)
Run the interactive CLI test harness to manually execute tasks through the full LangGraph state machine (Supervisor $\rightarrow$ Fast-Lane Worker $\rightarrow$ Guardrail Pass $\rightarrow$ Audit Log):

```bash
PYTHONPATH=backend ./venv/bin/python3 scripts/interactive_test.py
```

### 5.2 Automated Pytest Benchmark Suite
Execute all 12 automated unit and integration tests (30 supervisor routing benchmark tasks, Fast-Lane execution, guardrail checks, 3-tier policy allowlists, budget caps):

```bash
TESTING=1 PYTHONPATH=backend ./venv/bin/python3 -m pytest tests/ -v
```

### 5.3 Manual REST API Testing (Swagger / cURL)

1. **Test Supervisor Classification Endpoint:**
   ```bash
   curl -X POST "http://localhost:8000/api/supervisor/classify" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Delete all outdated user records from production database."}'
   ```

2. **Test End-to-End Workflow Execution Endpoint (Phase 2):**
   ```bash
   curl -X POST "http://localhost:8000/api/workflow/execute" \
        -H "Content-Type: application/json" \
        -d '{"prompt": "Explain the difference between REST and GraphQL in 3 bullet points."}'
   ```

---

## 6. Troubleshooting & Gotchas

- **Podman / Docker Permission Errors:** If testing local Ollama from inside container sandbox, ensure local port 11434 is accessible or set host networking mode.
- **Missing API Keys:** If a cloud provider API key is absent, `ModelProviderAdapter` automatically falls back to local Ollama (`gemma3:latest`) or internal mock models so testing is never blocked.
