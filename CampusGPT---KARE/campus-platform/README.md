# Campus Platform

Two products that share **one academic source of truth** (UIS). They stay separate processes and databases; Campus-GPT reads student records only through UIS APIs.

```text
campus-platform/
├── university-information-system/   # Institutional system of record (UIS)
└── campus-gpt/                      # AI intelligence layer (separate app)
```

| Application | Frontend | Backend |
|-------------|----------|---------|
| **UIS** | http://localhost:3000 | http://localhost:8000 |
| **Campus-GPT** | http://localhost:3001 | http://localhost:8001 |

## Rule

- UIS owns students, attendance, marks, hostel, exams, etc.
- Campus-GPT owns chat, RAG, consent UI, AI orchestration.
- Campus-GPT **never** connects to the UIS database.
- Integration path: `Campus-GPT Backend → UIS /api/v1/integration/campus-gpt/*`

## Current status

| Product | Status |
|---------|--------|
| University Information System | **In development** (this folder) |
| Campus-GPT | Existing app at repo root (`frontend/`, `backend/`). Will migrate into `campus-gpt/` and shift to ports 3001/8001 in Phase 5. Do not mix UIS code into the root Campus-GPT tree. |

## Quick start (UIS only)

See [university-information-system/README.md](./university-information-system/README.md).
