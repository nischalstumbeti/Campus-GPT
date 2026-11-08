# Campus-GPT: Technical Overview for External Reviewers

**Document Version:** 1.0  
**Last Updated:** March 2025  
**Project:** AI-Powered Institutional Intelligence & Admission Concierge for Kalasalingam Academy of Research and Education (KARE)

---

## 1. Executive Summary

Campus-GPT is a production-grade AI assistant for educational institutions that automates admission queries, hostel FAQs, placement information, and campus-related inquiries. It uses **Retrieval-Augmented Generation (RAG)** to ground answers in verified institutional documents, avoiding hallucinations. The system supports conversational chat, document ingestion, personalized course recommendations, analytics, and gamification (student points/leaderboard).

---

## 2. Technology Stack

| Layer | Technology | Version / Notes |
|-------|------------|-----------------|
| **Frontend** | Next.js | 14.2.3 |
| | React | 18.2.0 |
| | TypeScript | ^5 |
| | Tailwind CSS | 3.4.1 |
| | Framer Motion | ^11.0.3 |
| | Lucide React | Icons |
| | Mermaid | ^11.13.0 (diagram rendering) |
| **Backend** | FastAPI | 0.109.2 |
| | Uvicorn | 0.27.1 (ASGI server) |
| **Database** | SQLAlchemy (async) | 2.0.25 |
| | SQLite (dev) / PostgreSQL (prod) | aiosqlite / asyncpg |
| | Alembic | 1.13.1 (migrations) |
| **Vector Store** | FAISS (CPU) | ≥1.8.0 |
| **AI/ML** | Google Gemini | Chat: `gemini-1.5-flash`, Embeddings: `text-embedding-004` |
| **Document Processing** | PyPDF2, python-docx, python-pptx | PDF, DOCX, PPTX, TXT, MD, CSV |
| **Auth** | JWT (python-jose), bcrypt (passlib) | HS256, 24h expiry |
| **OAuth** | Google SSO | httpx for token exchange |

---

## 3. System Architecture

### 3.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Next.js)                              │
│  Landing │ Chat │ Login │ Admin │ Analytics │ Recommendations │ Upload      │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │ HTTP/REST
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Auth (JWT)   │  │ Chat (RAG)   │  │ Upload       │  │ Analytics    │     │
│  │ OAuth        │  │ Voice        │  │ Recommend    │  │ Admin        │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        ▼                        ▼                        ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ SQLite/       │      │ FAISS Vector      │      │ Gemini API        │
│ PostgreSQL    │      │ Store (embeddings)│      │ (Chat + Embed)    │
└───────────────┘      └──────────────────┘      └──────────────────┘
```

### 3.2 Directory Structure

```
Campus GPT/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry, CORS, route registration
│   │   ├── config.py            # Pydantic settings (env vars)
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── user.py          # User, Role (student/admin/super_admin)
│   │   │   ├── analytics.py     # QueryLog
│   │   │   ├── escalation.py    # EscalationLog
│   │   │   └── document.py      # Document (upload metadata)
│   │   ├── routes/
│   │   │   ├── auth.py          # Login, register, forgot-password, Google OAuth
│   │   │   ├── chat.py          # POST /api/chat
│   │   │   ├── upload.py        # POST /api/upload, /api/upload/public
│   │   │   ├── voice.py         # POST /api/voice
│   │   │   ├── analytics.py     # GET /api/analytics, /api/analytics/public
│   │   │   ├── recommend.py     # POST /api/recommend
│   │   │   ├── student.py       # GET /api/student/points
│   │   │   └── admin.py         # GET /api/admin/documents, /api/admin/vector-stats
│   │   ├── services/
│   │   │   ├── rag_service.py   # RAG pipeline (retrieve → generate)
│   │   │   ├── ingestion.py     # Document parsing, chunking, embedding
│   │   │   ├── embeddings.py    # Gemini embeddings
│   │   │   ├── vector_store.py  # FAISS wrapper
│   │   │   ├── recommendation.py
│   │   │   └── demo_responses.py
│   │   └── utils/
│   │       ├── database.py      # SQLAlchemy engine, init_db, migrations
│   │       ├── auth.py          # JWT, bcrypt, get_current_user, require_admin
│   │       ├── prompt_validator.py
│   │       └── diagram_service.py
│   ├── scripts/
│   │   └── bulk_ingest.py       # Bulk ingest from data/documents/
│   ├── data/
│   │   ├── faiss_index/         # FAISS index + metadata.jsonl
│   │   └── documents/          # Source docs for bulk ingest
│   ├── requirements.txt
│   └── .env / .env.example
├── frontend/
│   ├── app/                     # Next.js App Router
│   │   ├── page.tsx             # Landing
│   │   ├── chat/page.tsx       # Chat interface
│   │   ├── login/, register/, forgot-password/
│   │   ├── admin/page.tsx, admin/analytics/, admin/upload/
│   │   └── recommend/page.tsx
│   ├── components/
│   │   ├── ChatInterface.tsx
│   │   ├── CloudBackground.tsx
│   │   └── MermaidDiagram.tsx
│   ├── hooks/
│   │   └── useChat.ts
│   └── package.json
├── data/
│   └── documents/               # Place PDF, DOCX, etc. for bulk ingest
├── README.md
└── TECHNICAL_OVERVIEW.md
```

---

## 4. Core Flows

### 4.1 Chat Flow (RAG Pipeline)

1. **User sends message** → Frontend `useChat` → `POST /api/chat`
2. **Prompt validation** → `prompt_validator.py` checks for abusive/off-topic content
3. **Retrieval** (if `GEMINI_API_KEY` is set):
   - Query embedded via Gemini `text-embedding-004`
   - FAISS returns top-k similar chunks (default k=5)
   - Chunks + metadata (source, page) passed to generator
4. **Generation**:
   - Context + query sent to Gemini `gemini-1.5-flash`
   - System prompt enforces: *only answer from context; no hallucination*
   - Low context → response: *"I don't have enough verified information..."*
5. **Diagram detection** (optional): For workflow/architecture queries, Gemini may generate Mermaid diagram
6. **Points** (logged-in students only):
   - High confidence (≥0.8): 8 pts
   - Medium (0.5–0.8): 5 pts
   - Low (<0.5): 2 pts
   - Concise query (≤80 chars): +3 bonus
   - Escalated: 0 pts
7. **Logging** → QueryLog (user_id, session_id, query, confidence, failed, points_earned)
8. **Escalation** → If confidence < threshold (0.7), EscalationLog created
9. **Response** → `{ answer, session_id, sources, confidence, escalated, diagram, points_earned }`

### 4.2 Authentication Flow

| Flow | Steps |
|------|-------|
| **Login** | `POST /api/auth/login` (email, password) → JWT |
| **Register** | `POST /api/auth/register` (email, password, full_name) → JWT |
| **Google SSO** | `GET /api/auth/google` → Redirect to Google → `GET /api/auth/google/callback` → Create/link user → Redirect to frontend with `?token=...` |
| **Forgot Password** | `POST /api/auth/forgot-password` → Returns generic success (TODO: real email) |
| **Demo Login** | `POST /api/auth/demo-login` → JWT for testing |

- JWT stored in `localStorage` as `campus_gpt_token`
- Protected endpoints use `Authorization: Bearer <token>`
- Roles: `student`, `admin`, `super_admin`

### 4.3 Document Ingestion Flow

1. **Upload** (admin): `POST /api/upload` (requires admin JWT) → File saved → `ingest_document()`
2. **Upload (public)** : `POST /api/upload/public` (no auth) → Same ingestion
3. **Bulk ingest**: Place files in `data/documents/` → Run `python -m scripts.bulk_ingest`
4. **Ingestion steps**:
   - Extract text (PDF per-page chunks, DOCX/PPTX/TXT/MD/CSV)
   - Chunk text (750 tokens ≈ 3000 chars, 100 overlap)
   - Embed via Gemini (batch of 50)
   - Add to FAISS + metadata (source, page, text)

### 4.4 Recommendation Flow

- `POST /api/recommend` with: `program_level`, `course`, `subject`, `budget`, `marks`, `board`, `state`
- If no API key: returns `DEMO_RECOMMENDATIONS`
- If API key: Gemini generates 3–5 personalized course/college recommendations based on KARE offerings

### 4.5 Analytics Flow

- **Admin** (`GET /api/analytics`): Requires admin JWT. Returns top queries, failed queries, escalations, summary stats
- **Public** (`GET /api/analytics/public`): No auth. Returns total/failed queries, top queries, student leaderboard (points)

---

## 5. API Reference

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/chat` | Optional | RAG chat; returns answer, sources, confidence, escalated, diagram, points_earned |
| POST | `/api/upload` | Admin | Upload & ingest document |
| POST | `/api/upload/public` | No | Upload (MVP/demo) |
| POST | `/api/voice` | No | Placeholder (Gemini-only; no speech-to-text) |
| POST | `/api/recommend` | No | Course/college recommendations |
| GET | `/api/analytics` | Admin | Full analytics |
| GET | `/api/analytics/public` | No | Basic analytics + leaderboard |
| GET | `/api/student/points` | Student | Current user points |
| GET | `/api/admin/documents` | Admin | List uploaded documents |
| GET | `/api/admin/vector-stats` | Admin | FAISS chunk count |
| POST | `/api/auth/login` | No | Email/password login |
| POST | `/api/auth/register` | No | Sign up |
| POST | `/api/auth/forgot-password` | No | Password reset request |
| GET | `/api/auth/google` | No | Redirect to Google OAuth |
| GET | `/api/auth/google/callback` | No | OAuth callback |

---

## 6. Data Models

### 6.1 User
- `id`, `email`, `hashed_password`, `full_name`, `role` (student/admin/super_admin), `points`, `created_at`, `updated_at`

### 6.2 QueryLog
- `id`, `user_id` (nullable for guests), `session_id`, `query`, `response_length`, `confidence_score`, `sources_used`, `failed`, `points_earned`, `created_at`

### 6.3 EscalationLog
- `id`, `session_id`, `query`, `confidence_score`, `response_preview`, `status` (pending/resolved), `resolved_by`, `resolution_notes`, `created_at`, `resolved_at`

### 6.4 Document
- `id`, `filename`, `file_type`, `file_size`, `chunk_count`, `status`, `uploaded_by`, `created_at`, `metadata_json`

---

## 7. RAG Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `RAG_TOP_K` | 5 | Number of chunks retrieved |
| `RAG_CHUNK_SIZE` | 750 | Tokens per chunk (~3000 chars) |
| `RAG_CHUNK_OVERLAP` | 100 | Overlap tokens |
| `CONFIDENCE_THRESHOLD` | 0.7 | Below = escalation |
| `ESCALATION_ENABLED` | true | Create EscalationLog on low confidence |
| `EMBEDDING_DIM` | 768 | Gemini embedding dimension |

---

## 8. Security

- **Prompt validation**: Rejects abusive, jailbreak, and inappropriate content
- **JWT**: 24h expiry; `SECRET_KEY` must be changed in production
- **bcrypt**: Password hashing
- **Role-based access**: Admin routes require `admin` or `super_admin`
- **CORS**: Configured for `localhost:3000`, `localhost:3001`
- **Demo mode**: Without `GEMINI_API_KEY`, uses keyword-based FAQ; no embeddings

---

## 9. Environment Variables

### Backend (`.env`)
| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes (for full RAG) | From aistudio.google.com |
| `DATABASE_URL` | No | Defaults to SQLite |
| `FAISS_INDEX_PATH` | No | `./data/faiss_index` |
| `SECRET_KEY` | Yes (prod) | JWT signing |
| `GOOGLE_CLIENT_ID` | For OAuth | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | For OAuth | Google OAuth |
| `API_BASE_URL` | OAuth | Backend URL |
| `FRONTEND_URL` | OAuth | Frontend URL |

### Frontend (`.env.local`)
| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL (e.g. `http://localhost:8000`) |

---

## 10. Deployment Notes

- **Backend**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Frontend**: `npm run build` → `npm run start`
- **Database**: Use PostgreSQL in production; set `DATABASE_URL`
- **FAISS**: Index persisted in `./data/faiss_index`; survives restarts
- **Bulk ingest**: Run `python -m scripts.bulk_ingest` to populate knowledge base

---

## 11. Known Limitations & Future Work

- **Voice**: No speech-to-text (Gemini-only; would need Whisper or similar)
- **Password reset**: API returns success but no email is sent (TODO)
- **Google OAuth**: Requires correct `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, redirect URIs
- **Mermaid**: Diagram rendering uses Mermaid library; raw Mermaid + “Open in Mermaid Live” link also provided

---

## 12. Testing & Demo

- **Without API key**: Demo mode with pre-loaded FAQ responses
- **Sample queries**: "What is the hostel availability?", "Placement statistics?", "NAAC grade?"
- **API docs**: `http://localhost:8000/docs`
- **Health**: `GET /` or `GET /health`

---

*This document is intended for external technical reviewers. For user-facing documentation, see README.md.*
