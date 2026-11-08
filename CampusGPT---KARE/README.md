# Campus Platform — Campus GPT + University Information System

Unified launcher for **Campus GPT** (AI intelligence layer) and the **University Information System** (institutional ERP). Both applications remain independent; `app.py` orchestrates startup, health checks, and shutdown.

![Campus-GPT](https://img.shields.io/badge/Campus--GPT-v1.0-purple)

## Quick Start (recommended)

### Prerequisites

- Python 3.10+
- Node.js 18+
- Dependencies installed for both projects (see below)

### Run the full platform

```bash
python app.py
```

This opens the **Campus Platform** launcher, which will:

1. Check Python, Node.js, and project folders
2. Start UIS (backend + frontend)
3. Start Campus GPT (backend + frontend)
4. Open both browser interfaces automatically
5. Show a dashboard with status, Open, Restart, and Stop controls

| Application | Frontend | Backend |
|-------------|----------|---------|
| University Information System | http://localhost:3000 | http://localhost:8000 |
| Campus GPT | http://localhost:3001 | http://localhost:8001 |

Ports are defined in `config/config.json`. Configure each app's `.env` files before first run.

### First-time setup

**Campus GPT backend**

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env
python run.py
```

**Campus GPT frontend**

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

**UIS** — see `campus-platform/university-information-system/README.md`

---

## Campus GPT Features

- **Conversational AI Chat** – ChatGPT-like interface with context-aware responses
- **RAG Pipeline** – Grounded answers from verified institutional data (no hallucinations)
- **Voice Input** – Record audio → Whisper (Hugging Face, Indian-accent) → text → chatbot
- **Voice Output** – Text-to-speech with Indian English voice (edge-tts)
- **Knowledge Base Ingestion** – Upload PDFs, CSVs, TXT files; chunk & embed
- **Recommendation Engine** – Personalized course/college suggestions based on profile
- **Admin Panel** – Analytics, document management, escalation logs
- **Multi-System Integration** – Simulated SIS, hostel, admission, placement, accreditation APIs

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python) |
| Database | PostgreSQL / SQLite |
| Vector DB | FAISS |
| AI | Google Gemini (chat, embeddings), Whisper (Hugging Face Indian-accent), edge-tts (TTS) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- **Gemini API key** – Get free key at https://aistudio.google.com/apikey
- **No key for demo** – Works with pre-loaded FAQ; add GEMINI_API_KEY for full AI.
- **ffmpeg** (for voice input) – Required for webm→wav conversion. Install: `apt install ffmpeg` (Linux) or download from ffmpeg.org

### 1. Backend Setup

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create `.env` (optional for demo):

```bash
cp .env.example .env
# Add your GEMINI_API_KEY from https://aistudio.google.com/apikey
# Leave empty for demo mode (pre-loaded FAQ only)
```

Run the backend:

```bash
python run.py
# Or: uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Optional: Seed sample knowledge** (requires OPENAI_API_KEY):

```bash
python -m app.utils.seed_knowledge
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

Create `.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

Run the frontend:

```bash
npm run dev
```

### 3. Open in Browser

- **Landing**: http://localhost:3001
- **Chat**: http://localhost:3001/chat
- **Admin**: http://localhost:3001/admin
- **Upload**: http://localhost:3001/admin/upload
- **Recommendations**: http://localhost:3001/recommend
- **API Docs**: http://localhost:8001/docs

> **Ports:** Campus-GPT uses **3001 / 8001**. The University Information System (UIS) uses **3000 / 8000**.

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_API_KEY` | Gemini API key (get at aistudio.google.com) | - |
| `DATABASE_URL` | PostgreSQL or SQLite URL | SQLite for dev |
| `FAISS_INDEX_PATH` | Path for FAISS index | `./data/faiss_index` |
| `RAG_TOP_K` | Number of chunks to retrieve | 5 |
| `RAG_CHUNK_SIZE` | Tokens per chunk | 750 |
| `CONFIDENCE_THRESHOLD` | Below this = escalation | 0.7 |
| `SECRET_KEY` | JWT secret (change in prod!) | - |

### Frontend (`frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL |

---

## How RAG Works

1. **Query** – User asks a question
2. **Embed** – Query is converted to a vector via OpenAI Embeddings API
3. **Retrieve** – FAISS finds top-k most similar chunks from the vector store
4. **Generate** – Context + query sent to GPT; response grounded in retrieved data
5. **Policy** – If context is insufficient, response: *"I don't have enough verified information"*
6. **Confidence** – Low confidence → escalation flag for admin review

### No Hallucinations

The system is configured to **only answer from retrieved context**. If the knowledge base doesn't contain relevant information, the AI refuses to guess.

---

## API Documentation

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Run RAG pipeline, return answer |
| POST | `/api/upload` | Ingest document (admin) |
| POST | `/api/upload/public` | Ingest document (MVP, no auth) |
| POST | `/api/voice` | Speech-to-text (Whisper, Hugging Face Indian-accent) |
| POST | `/api/tts` | Text-to-speech (Indian English voice, edge-tts) |
| POST | `/api/recommend` | Course/college recommendations |
| GET | `/api/analytics` | Usage insights (admin) |
| GET | `/api/analytics/public` | Basic analytics (MVP) |

### Chat Request

```json
{
  "message": "What is the hostel availability?",
  "session_id": "optional-uuid",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
}
```

### Chat Response

```json
{
  "answer": "...",
  "session_id": "uuid",
  "sources": [{"source": "...", "relevance": 0.9}],
  "confidence": 0.85,
  "escalated": false
}
```

---

## Project Structure

```
Capston Project - CampusGPT/
├── app.py                 # Unified launcher (run this)
├── config/
│   └── config.json        # Ports and service paths
├── logs/                  # Launcher & service logs (auto-created)
├── backend/               # Campus GPT API (FastAPI, port 8001)
├── frontend/              # Campus GPT UI (Next.js, port 3001)
├── campus-platform/
│   └── university-information-system/
│       ├── backend/       # UIS API (FastAPI, port 8000)
│       └── frontend/      # UIS UI (Next.js, port 3000)
└── README.md
```

---

## Security & Access Control

- **Roles**: Student, Admin, Super Admin
- **Auth**: JWT-based (see `/api/auth/login`, `/api/auth/register`)
- **MVP**: `/api/upload/public` and `/api/chat` work without auth for demos
- **Production**: Use `/api/upload` with admin token

---

## Demo Mode (No API Key)

Without `GEMINI_API_KEY`, Campus-GPT runs in **demo mode**:
- **Chat**: Keyword-based FAQ (hostel, placements, NAAC, NIRF, admission, programs, scholarships)
- **Recommendations**: Pre-written sample suggestions
- **Voice**: Returns message to type (Gemini-only; no speech-to-text)
- **Upload**: Accepts files but doesn't ingest (add API key for full ingestion)

## Sample Queries to Try

**Demo mode** (no API key):

- *What is the hostel availability?*
- *What are the placement statistics?*
- *What is the NAAC grade?*
- *What programs are offered?*
- *What is the application fee?*

**With GEMINI_API_KEY**: Full RAG + seed script for richer answers.

## Prompt safety

Unethical or abusive prompts (e.g. "you are bad", "stupid", insults) are rejected. The bot only answers admission, hostel, placement, and campus-related queries.

---

## License

MIT
