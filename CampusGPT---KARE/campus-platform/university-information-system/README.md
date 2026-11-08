# University Information System (UIS)

Independent institutional ERP — **system of record** for Campus-GPT.

> **DEMO ENVIRONMENT — SYNTHETIC DATA ONLY**

## Ports

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend / Swagger | http://localhost:8000 / http://localhost:8000/docs |

## Quick start

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env
python -m app.seed.run_seed
python run.py
```

### Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

## Demo accounts (password: `campus123`)

Same people exist in Campus-GPT (login by **email**) and UIS (login by **username**). Timetable, attendance, and marks come from UIS.

| UIS username | Campus-GPT email | Role | Notes |
|--------------|------------------|------|-------|
| `student.demo` | `student.demo@klu.ac.in` | Student | **Ananya Krishnan / KARE2024CSE045** — CSE 5th sem A |
| `rohan.mehta` | `rohan.mehta@klu.ac.in` | Student | Rohan Mehta |
| `priya.sharma` | `priya.sharma@klu.ac.in` | Student | Priya Sharma |
| `karthik.raj` | `karthik.raj@klu.ac.in` | Student | Karthik Raj |
| `divya.nair` | `divya.nair@klu.ac.in` | Student | Divya Nair |
| `arjun.patel` | `arjun.patel@klu.ac.in` | Student | Arjun Patel |
| `sneha.reddy` | `sneha.reddy@klu.ac.in` | Student | Sneha Reddy |
| `vishal.kumar` | `vishal.kumar@klu.ac.in` | Student | Vishal Kumar |
| `meera.iyer` | `meera.iyer@klu.ac.in` | Student | Meera Iyer |
| `aditya.singh` | `aditya.singh@klu.ac.in` | Student | Aditya Singh |
| `faculty.demo` | `faculty.demo@klu.ac.in` | Faculty | Dr. Priya Raman — DBMS |
| `hod.demo` | `hod.demo@klu.ac.in` | HOD | Dr. Ramesh Venkat |
| `admin.demo` | `admin.demo@klu.ac.in` | University Admin | Stats + user management |

## Campus-GPT integration

Namespace: `/api/v1/integration/campus-gpt/`

Headers:

```text
X-API-Key: <INTEGRATION_API_KEY>
X-UIS-Username: student.demo
# or Authorization: Bearer <UIS user JWT>
```

Example:

```bash
curl -H "X-API-Key: uis-campus-gpt-dev-integration-key" ^
     -H "X-UIS-Username: student.demo" ^
     http://localhost:8000/api/v1/integration/campus-gpt/student/attendance
```

Consent: Student portal → **Campus-GPT Consent**. Revoking `academic.attendance` yields `403 CONSENT_DENIED`.

ABAC: `target_student_id` for another student on marks is rejected (`DENIED_ABAC`).

## Architecture

See [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Separation rules

- Do not place Campus-GPT code in this folder.
- Campus-GPT must not connect to `uis.db` / UIS PostgreSQL.
- Integration is API-only.
