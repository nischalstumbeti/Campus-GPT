# Campus-GPT Architecture

Privacy-aware, role-based, context-aware **AI University Copilot**.

Positioning: not a chatbot and not an ERP.  
Loop: **ASK → UNDERSTAND → DECIDE → CREATE → ACT**

Security always outranks feature count. The LLM never decides access.

---

## 1. Existing system (preserved)

Working today (do not rewrite):

- Next.js 14 + FastAPI + SQLite (Postgres-ready)
- JWT auth: student / faculty / admin
- Academic SIS tables: timetable, attendance, marks, hostel leave, calendar
- RAG: chunk → Gemini embed → FAISS → grounded answer
- Chat sessions + long-term memory
- Demo SIS for `student.demo@klu.ac.in` / `faculty.demo@klu.ac.in`

This increment adds the copilot **control plane** around that core: consent, gateway, query router, citations/explainability, and a chat-first IA.

---

## 2. Authorization flow (non-negotiable)

```
User
 → Authentication (JWT)
 → Role verification (RBAC)
 → Attribute checks (ABAC: own student_id / assigned class)
 → Consent / permission
 → Secure Data Gateway  (SQL only, never full DB)
 → Retrieval (structured + RAG)
 → LLM
 → Grounded response + citations + “why this data”
```

Forbidden: `User → LLM → entire university database`.

If permission is missing, the gateway returns **no rows**. The model is told only that access was denied — never whether a hidden record exists.

---

## 3. Permission model

Categories (granular; not one master toggle):

| Group | Keys | Purpose |
|---|---|---|
| Academic | `academic.attendance`, `academic.marks`, `academic.grades`, `academic.cgpa`, `academic.credits`, `academic.history` | Personalized academics |
| Hostel | `hostel.room`, `hostel.leave`, `hostel.records` | Hostel assistance |
| Achievements | `achievements.certs`, `achievements.awards`, `achievements.activities` | Career / resume |
| Financial | `financial.fees`, `financial.scholarship` | Fees / scholarships |

States: **allow / deny / revoke**. Demo accounts seed **allow** so the product is usable; users can revoke.

ABAC rules:

- Student: `student.user_id == auth.uid`
- Faculty: own profile + **assigned** courses/sections only
- Admin: explicit role, still logged

---

## 4. Query router

Intent classes:

- `knowledge` — regulations, notices → RAG only
- `structured` — attendance, marks, CGPA, timetable → SQL via gateway
- `calculation` — classes needed for 75%, what-if CGPA → SQL + math (not embeddings)
- `document` — letters, emails → profile (if consented) + templates
- `workflow` — leave / complaint → confirmation required
- `mixed` — rules + personal facts

---

## 5. RAG vs structured data

| Unstructured (RAG) | Structured (SQL gateway) |
|---|---|
| Regulations, handbook, circulars, FAQs | Marks, grades, attendance, CGPA, credits, timetable, hostel leave |

Hybrid retrieval (knowledge): metadata filter → keyword overlap + vector search → simple rerank → citations. Prefer current `effective_date`. On conflict: show both sources; do not silently pick one.

---

## 6. ERP adapters

```
AcademicDataProvider
AttendanceProvider
HostelProvider
NotificationProvider
```

Current implementation: `SqliteAcademicProvider` (local SIS).  
Later: `UniversityERPProvider` with the same methods. Copilot logic does not import ERP SDKs.

---

## 7. API map

Existing `/api/auth`, `/api/chat`, `/api/academic/*`, `/api/me/*` stay.

Added:

- `/api/privacy/consents` — get / patch granular consent
- `/api/privacy/access-log` — access history
- `/api/privacy/explain` — last data-use explanation
- `/api/copilot/graduation` — credit progress
- `/api/copilot/announcements` — official updates
- `/api/copilot/letters` — draft only (no auto-submit)
- `/api/copilot/achievements`
- `/api/copilot/career`
- `/api/copilot/week-plan`
- `/api/audit` — admin audit log

Chat `/api/chat` now returns `data_used`, `intent`, `kind` (`fact` / `calculation` / `recommendation` / `knowledge`).

---

## 8. UI information architecture

**Student**

- Chat
- My Academic Life (attendance, marks, forecast, timetable, graduation)
- University (rules / notices)
- Planner (calendar + week plan)
- Documents (letters)
- Hostel
- Career
- Achievements
- Privacy
- Settings

**Faculty:** Chat, My Classes, Analytics, Documents, Notifications, Privacy, Settings  
**Admin:** Overview, Users, Knowledge, Announcements, Permissions, Audit, Settings

Homepage (logged-out): product, not records. Chat-first after login.

---

## 9. Phases

| Phase | Status in this increment |
|---|---|
| 1 Foundation (auth, roles, demo, chat) | Done (existing) + copilot shell |
| 2 RAG + citations | Existing RAG; stricter grounding + conflict note |
| 3 Personal intelligence | Gateway-filtered attendance/marks/CGPA/graduation |
| 4 Privacy | Consent center, access history, why-this-data, audit |
| 5 University assistant | Announcements, planner, hostel, achievements |
| 6 Productivity | Letter drafts (formal / email / short) + career summary |
| 7 Actions | Leave already exists; confirmation preserved; no silent submit |
| 8 Research eval | Metric hooks in architecture; dataset scaffold later |

---

## 10. Demo environment

Banner: **DEMO ENVIRONMENT**

| Account | Password | Role |
|---|---|---|
| `student@example.com` | `campus123` | Student (isolated fake SIS) |
| `faculty@example.com` | `campus123` | Faculty |
| `admin@example.com` | `campus123` | Admin |
| `student.demo@klu.ac.in` | `campus123` | Legacy demo student |
| `faculty.demo@klu.ac.in` | `campus123` | Legacy demo faculty |

No real student records in seed data.
