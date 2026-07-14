# EPC Intelligence Platform
### Data Centre Construction — AI-Powered Project Intelligence

> **ET AI Hackathon 2026** | Built with Mistral 7B · Qdrant · FastAPI · React · Docker

---

## What It Does

Managing a hyperscale data centre EPC (Engineering, Procurement & Construction) project means dealing with hundreds of specification documents, shifting schedules, and a constant stream of RFIs (Requests for Information). This platform puts an AI assistant at the fingertips of every project stakeholder — so they can query documents, check compliance, assess schedule risk, and resolve RFIs in seconds instead of hours.

**Three specialist AI agents, one unified interface:**

| Agent | What it does | Example query |
|---|---|---|
| **Spec Compliance** | Checks if a design or component meets spec requirements | *"Is a UPS with 94% efficiency compliant?"* |
| **Schedule Risk** | Analyses the project schedule for delays and critical path impacts | *"What are the current delays to the project timeline?"* |
| **RFI Copilot** | Searches past RFI resolutions before you raise a new one | *"Has there been an RFI about cable tray fill factor?"* |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React + Vite)                   │
│   Upload │ RAG Query │ Spec Compliance │ Schedule Risk │ RFI    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / Streaming (SSE)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI  (api:8000)                           │
│                                                                 │
│  /documents/upload   →  PDF parse → chunk → embed → store      │
│  /query/stream       →  embed → search → LLM stream            │
│  /agents/*/stream    →  embed → search → agent prompt stream   │
└──────┬──────────────────────────┬────────────────────────────┬──┘
       │                          │                            │
       ▼                          ▼                            ▼
┌─────────────┐        ┌──────────────────┐        ┌──────────────────┐
│  PostgreSQL │        │  Qdrant           │        │  Ollama           │
│  (metadata) │        │  (vector store)   │        │  Mistral 7B      │
│  postgres:  │        │  qdrant:6333      │        │  ollama:11434    │
│  5432       │        │  384-dim cosine   │        │  local LLM       │
└─────────────┘        └──────────────────┘        └──────────────────┘

Embeddings: sentence-transformers/all-MiniLM-L6-v2 (384 dims, runs in API container)
```

**Data flow for a query:**
1. User question → API embeds with `all-MiniLM-L6-v2`
2. Qdrant vector search → top-K relevant document chunks
3. Chunks + question → agent prompt → Mistral 7B via Ollama
4. Tokens stream back to browser word-by-word via `StreamingResponse`
5. `__META__` + `__SOURCES__` appended at stream end for structured data

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac/Linux)
- Git
- 8 GB RAM minimum (Mistral 7B model is ~4.1 GB)

### Run in 3 commands

```bash
git clone https://github.com/YOUR_USERNAME/epc-intelligence.git
cd epc-intelligence
docker compose up -d
```

Then open **http://localhost:5173** in your browser.

> **First run takes 5–10 minutes** — Docker pulls images and Ollama downloads the Mistral 7B model automatically. Subsequent starts are instant.

### Check everything is running

```bash
docker compose ps
```

All 6 services should show `Up`:

```
epc_ollama     Up   11434/tcp
epc_qdrant     Up   6333/tcp, 6334/tcp
epc_postgres   Up   5432/tcp
epc_api        Up   0.0.0.0:8000->8000/tcp
epc_frontend   Up   0.0.0.0:5173->5173/tcp
```

Health check: http://localhost:8000/health should return `{"status":"ok",...}`

---

## Load Sample Data

The repo includes 4 representative EPC documents as seed PDFs:

```bash
cd seed_data
pip install requests PyMuPDF --break-system-packages
python upload_seeds.py
```

This uploads:
- `spec_electrical.pdf` — Electrical specification (UPS, HV distribution, cable trays)
- `spec_cooling.pdf` — Cooling system specification (CRAH units, chillers, refrigerants)
- `project_schedule.pdf` — Project schedule with milestones and current delays
- `rfi_log.pdf` — RFI log with past queries and resolutions

After upload, the **Documents** tab should show 4 documents (16 chunks total).

---

## Features

### RAG Query
Natural language search across all uploaded project documents. Answers stream word-by-word with source citations.

### Spec Compliance Agent
Analyses queries against specification documents. Returns:
- **Compliance status badge** — COMPLIANT / NON-COMPLIANT / REQUIRES VERIFICATION
- Structured analysis: requirement, risk, source reference
- Relevant spec chunks with similarity scores

### Schedule Risk Agent
Analyses project schedule documents. Returns:
- **Risk level badge** — HIGH / MEDIUM / LOW
- Identified risks and critical path impacts
- Recommendations with schedule references

### RFI Copilot
Searches the RFI log for similar past queries. Returns:
- Similar RFIs found with resolution details
- Open items and recommendations
- Source chunks from the RFI log

### Document Upload
Upload any EPC PDF (specifications, schedules, RFI logs, drawings). The platform automatically:
- Extracts text with PyMuPDF
- Chunks into 500-token segments with overlap
- Generates embeddings with `all-MiniLM-L6-v2`
- Stores vectors in Qdrant + metadata in PostgreSQL

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Mistral 7B via Ollama | No API key needed, runs fully local |
| Vector DB | Qdrant | Fast cosine similarity search, Docker-native |
| Embeddings | all-MiniLM-L6-v2 | Lightweight, 384-dim, runs in CPU |
| Backend | FastAPI (Python) | Async streaming, clean REST API |
| Frontend | React + Vite + Tailwind CSS | Fast HMR, responsive 3-column layout |
| Database | PostgreSQL | Document metadata and chunk tracking |
| Containers | Docker Compose | Single-command setup, no local installs |

**No paid APIs. No internet required after setup. Fully self-contained.**

---

## GPU Acceleration (Optional)

If your machine has an NVIDIA GPU, you can run inference significantly faster:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

This passes the GPU through to the Ollama container. Standard `docker compose up -d` (no GPU override) works on any machine — it falls back to CPU automatically.

> **Judges:** Run the standard command. No GPU required. Response times are ~30–60s per query on CPU; streaming means you see text immediately while inference runs.

---

## Project Structure

```
epc-intelligence/
├── api/
│   ├── main.py              # FastAPI app — RAG + 3 streaming agents
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Sidebar nav, health check
│   │   ├── components/
│   │   │   ├── Query.jsx            # RAG Query tab
│   │   │   ├── SpecCompliance.jsx   # Spec Compliance agent
│   │   │   ├── ScheduleRisk.jsx     # Schedule Risk agent
│   │   │   ├── RFICopilot.jsx       # RFI Copilot agent
│   │   │   ├── Documents.jsx        # Document list
│   │   │   └── Upload.jsx           # PDF upload
│   │   └── utils/
│   │       └── streamAgent.js       # Shared streaming utility
│   ├── vite.config.js
│   └── Dockerfile
├── seed_data/
│   ├── upload_seeds.py      # Seed document uploader
│   ├── reset_collection.py  # Qdrant reset utility
│   └── *.pdf                # 4 sample EPC documents
├── tests/
│   └── test_api.py          # pytest — 6 endpoint tests
├── docker-compose.yml        # 6-service stack
├── docker-compose.gpu.yml    # Optional GPU override
└── README.md
```

---

## Running Tests

With Docker running:

```bash
pip install pytest httpx --break-system-packages
pytest tests/test_api.py -v
```

Expected output:
```
tests/test_api.py::test_health                      PASSED
tests/test_api.py::test_list_documents              PASSED
tests/test_api.py::test_query                       PASSED
tests/test_api.py::test_spec_compliance_non_compliant PASSED
tests/test_api.py::test_schedule_risk_high          PASSED
tests/test_api.py::test_rfi_copilot                 PASSED
6 passed
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | System health + service status |
| GET | `/documents` | List all uploaded documents |
| POST | `/documents/upload` | Upload a PDF (`multipart/form-data`) |
| POST | `/query` | RAG query (blocking) |
| POST | `/query/stream` | RAG query (streaming) |
| POST | `/agents/spec-compliance` | Spec compliance check (blocking) |
| POST | `/agents/spec-compliance/stream` | Spec compliance check (streaming) |
| POST | `/agents/schedule-risk` | Schedule risk analysis (blocking) |
| POST | `/agents/schedule-risk/stream` | Schedule risk analysis (streaming) |
| POST | `/agents/rfi-copilot` | RFI search (blocking) |
| POST | `/agents/rfi-copilot/stream` | RFI search (streaming) |

Full interactive docs: http://localhost:8000/docs

---

## Demo

> 📹 **[Demo Video — coming Day 20]**

<!-- Add YouTube/Google Drive link here before submission -->

---

## About

Built for the **ET AI Hackathon 2026** — a 20-day challenge to build production-ready AI applications.

**Domain:** Data Centre EPC (Engineering, Procurement & Construction)  
**Problem:** Project teams waste hours manually searching specs, schedules, and RFI logs  
**Solution:** RAG-powered AI agents that surface answers in seconds, with source citations

---

*Powered by Mistral 7B · No API keys · Runs fully local*
