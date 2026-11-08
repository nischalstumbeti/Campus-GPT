# University Information System — Architecture

## 1. Overall architecture

```text
┌──────────────────────────────────────────────────────────┐
│ UIS Frontend (Next.js) — :3000                           │
│ Student / Faculty / HOD / Admin portals                  │
└──────────────────────────┬───────────────────────────────┘
                           │ JWT
                           ▼
┌──────────────────────────────────────────────────────────┐
│ UIS Backend (FastAPI) — :8000                            │
│ Auth · RBAC · Academic · Hostel · Admin · Integration    │
└──────────────────────────┬───────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│ UIS Database (SQLite local / PostgreSQL+Supabase prod)   │
│ System of record — students, marks, attendance, hostel…  │
└──────────────────────────────────────────────────────────┘

Campus-GPT (separate process :3001/:8001)
        │
        │  Bearer service token + user identity claims
        ▼
  /api/v1/integration/campus-gpt/*  → consent → minimize → audit → JSON
```

## 2. Folder structure

```text
university-information-system/
├── frontend/          # Next.js ERP UI
├── backend/           # FastAPI
├── database/          # schema notes, migrations plan
├── docs/              # ER, RBAC, OpenAPI notes, roadmap
└── README.md
```

## 3. Database ER (logical)

```text
users ──┬── student_profiles ── enrollments ── course_offerings ── courses
        │         │                    │              │
        │         │                    ├── attendance_records
        │         │                    └── marks / grades
        │         ├── semester_results (CGPA, credits, backlogs)
        │         ├── hostel_allocations / hostel_leaves
        │         └── achievements
        ├── faculty_profiles ── teaching_assignments
        └── roles (RBAC)

departments ── programs ── courses
announcements, exam_schedules, academic_calendars
integration_consents, audit_logs, api_clients
```

## 4. Role–permission matrix

| Resource | Student | Faculty | HOD | Exam Admin | Hostel Admin | Uni Admin | Super Admin |
|----------|---------|---------|-----|------------|--------------|-----------|-------------|
| Own profile | R/U | R/U | R/U | R/U | R/U | CRUD | CRUD |
| Own academics | R | — | dept R | — | — | R | R |
| Class attendance (assigned) | — | CRUD | dept R | — | — | R | CRUD |
| Class marks (assigned) | — | CRUD | dept R | R | — | R | CRUD |
| Exam schedules | R | R | R | CRUD | — | CRUD | CRUD |
| Hostel (own) | R + leave req | — | — | — | CRUD | R | CRUD |
| Announcements | R | R + dept | CRUD dept | R | R | CRUD | CRUD |
| Users / depts | — | — | dept faculty | — | — | CRUD | CRUD |
| Integration APIs | via consent | — | — | — | — | manage clients | manage |

**ABAC:** student may only read rows where `student.user_id == auth.uid`. Faculty only assigned offerings.

## 5. API specification (summary)

### Portal APIs
- `POST /api/v1/auth/login`
- `GET  /api/v1/auth/me`
- `GET  /api/v1/student/dashboard`
- `GET  /api/v1/student/attendance|marks|grades|courses|timetable|exams|hostel|achievements`
- `GET  /api/v1/faculty/dashboard|classes|students`
- `GET  /api/v1/admin/...`

### Campus-GPT integration (data minimization)
- `GET /api/v1/integration/campus-gpt/student/{resource}`
- Auth: integration API key + end-user JWT subject (or delegated token)
- Checks: client auth → user identity → consent → ABAC → minimize → audit

Full interactive docs: `http://localhost:8000/docs`

## 6. UIS ↔ Campus-GPT integration

```text
Campus-GPT Backend
  → Authorization: Bearer <integration_key>
  → X-UIS-User-Id / delegated user token (identity from auth, never client-supplied student_id for "me")
  → UIS validates consent for resource
  → Returns minimal JSON only
  → Writes audit_logs (no sensitive payload dump)
```

## 7. Authentication flow

1. User logs into UIS → JWT (role, user_id, student_id/faculty_id).
2. Portal calls use that JWT.
3. Campus-GPT users authenticate to **Campus-GPT**; Campus-GPT backend calls UIS with integration credentials + mapped institutional user id.
4. UIS never trusts a student_id from the Campus-GPT frontend alone.

## 8. Consent flow

1. User grants/revokes categories in Campus-GPT (mirrored or stored on UIS `integration_consents`).
2. Integration endpoint checks consent key (e.g. `academic.attendance`).
3. If revoked → `403 CONSENT_DENIED` (no data).

## 9. Development roadmap

| Phase | Scope |
|-------|--------|
| **1** | Setup, DB, auth, RBAC, portals shell, synthetic seed |
| **2** | Attendance, marks, grades, CGPA, courses, timetable, exams |
| **3** | Hostel, achievements, announcements, requests, documents |
| **4** | Integration API, consent, audit, OpenAPI |
| **5** | Wire Campus-GPT (ports 3001/8001) — *no Campus-GPT code until then* |
| **6** | Security tests |
| **7** | End-to-end demo |

## 10. Demo accounts

| Login | Password | Role |
|-------|----------|------|
| `student.demo` | `campus123` | Student (Ananya Krishnan / KARE2024CSE045) |
| `faculty.demo` | `campus123` | Faculty (Dr. Priya Raman) |
| `hod.demo` | `campus123` | HOD CSE |
| `admin.demo` | `campus123` | University Admin |
