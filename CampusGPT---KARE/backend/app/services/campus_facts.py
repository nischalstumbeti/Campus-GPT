"""Campus fact sheets — loaded from the database (campus_fact_sheets table)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Bootstrap body used only to seed the DB once — runtime reads always go through the table.
_SEED_RECEPTION_BRIEF = """
KARE (Kalasalingam Academy of Research and Education) — Reception desk fact sheet

IDENTITY
- Full name: Kalasalingam Academy of Research and Education (KARE), Deemed-to-be University (UGC).
- Location: Krishnankoil, Srivilliputtur, Virudhunagar District, Tamil Nadu 626126, India.
- Established: 1984. Main reception: Building A, campus entrance lobby.
- Office hours: Monday–Saturday 9:00 AM – 5:00 PM (closed university holidays). Visitor help desk same hours.
- Helpline / reception: reception@kluniversity.ac.in | 1800-XXX-XXXX (campus board) | +91-4562-235000.

ACCREDITATION & RANKING
- NAAC A++ (CGPA 3.65, valid through 2028).
- NBA accreditation for major engineering programs. ISO 9001:2015.
- NIRF (indicative): Engineering ~36, University ~29, Overall ~48.

PROGRAMS (overview)
- UG Engineering: B.Tech CSE, IT, AI/ML, ECE, EEE, Mechanical, Civil (+ related specializations).
- Other UG: BBA, BCA, B.Sc, B.Com, B.A, B.Ed.
- PG: M.Tech (multiple specializations), MBA, MCA, M.Sc, M.Com, M.A, M.Phil.
- Research: Ph.D. across engineering, science, management, and humanities.
- Typical seats: B.Tech ~2616; M.Tech ~372; MBA ~360 (confirm with Admission Office for current year).

ADMISSIONS (how to guide students)
- Apply online: kluniversity.ac.in admission portal.
- Application fee (indicative): Rs 1500 general / Rs 750 reserved category.
- Typical UG deadline June 30; PG July 15 (year-specific — verify on portal).
- Process: online form → document verification → merit/counselling → fee payment (usually within 7 days).
- Documents commonly needed: 10th & 12th marksheets, Aadhaar, photos, category certificate (if any), entrance score card, TC/migration.
- B.Tech eligibility (indicative): 10+2 PCM with ~60% aggregate; JEE Main / TNEA considered.
- M.Tech: relevant B.Tech/B.E. ~60%; GATE preferred.
- MBA: any UG ~50%; CAT/MAT/CMAT accepted.
- Admission Office: admission@kluniversity.ac.in | +91-4562-235000.

FEES & SCHOLARSHIPS (high-level guidance)
- B.Tech program fee band (indicative full program): about ₹3.77L–₹9.2L depending on branch.
- Hostel residential fee (indicative): ₹45,000–₹65,000 per year (mess may be separate).
- Scholarships: KEEE merit waivers 25%–100%; Arts & Science merit for high 12th scores; need-based and SC/ST schemes; lateral-entry waiver schemes.
- Finance / fee queries: fees@kluniversity.ac.in | +91-4562-235003.
- For a signed-in student’s exact dues, use fee records / Pay fees (do not invent personal amounts).

ACADEMICS & EXAMINATIONS
- Academic Office / Examinations: academics@kluniversity.ac.in | +91-4562-235004.
- Attendance rule (indicative): minimum 75% to sit end-semester exams.
- For personal timetable, attendance, marks: use authorized UIS-linked Campus-GPT Academic tools when consent allows.
- Examination branch: typically near Academic Block; ask Reception Building A for walking directions on campus maps.

HOSTEL & RESIDENTIAL
- Boys hostel capacity ~500; Girls ~400. WiFi, mess, 24/7 security.
- Hostel Office: hostel@kluniversity.ac.in | +91-4562-235001.
- Warden: warden@kluniversity.ac.in. Leave usually needs ~48 hours advance; campus curfew typically 10:00 PM; ragging strictly prohibited.
- Deep leave/room issues: guide student to Hostel Manager / Warden desk in Campus-GPT or UIS Hostel Leave page.

PLACEMENTS & CAREER
- Placement Cell: placement@kluniversity.ac.in | +91-4562-235002.
- Recent indicative outcomes: ~92% placement rate, average ~8.5 LPA, highest ~44 LPA, 150+ recruiters (IT/core/consulting mix).
- Career guidance also available via Campus-GPT Career page for consented profiles.

CAMPUS FACILITIES & DIRECTIONS
- Central Library (50,000+ volumes), 24/7 lab access policies by department, stadium, gym, medical center, WiFi, transport/buses, cafeterias.
- Common directions: Library — Academic Quad north wing; Examination Branch — Academic Block ground floor; Accounts — Admin Block; Placement Cell — Career Services building; Hostels — residential zone past sports ground.
- Transport: college buses for day scholars; enquire Accounts/Transport desk for routes and bus pass.

HOW RECEPTION SHOULD ANSWER
- Give complete, practical campus information for ANY college-related question (directions, contacts, admissions overview, fees overview, hostel overview, placements, facilities, office hours).
- Prefer facts from this brief and knowledge excerpts; never invent personal marks, attendance, or fee balances.
- If a specialist action is needed (apply hostel leave, pay fee, view marks), answer briefly then point to the right Campus-GPT page or office email/phone.
""".strip()

_SEED_RECEPTION_FULL = (
    "Kalasalingam Academy of Research and Education (KARE) — complete campus information\n\n"
    "Identity: Deemed-to-be University (UGC) at Krishnankoil, Srivilliputtur, Virudhunagar, "
    "Tamil Nadu 626126. Established 1984. Main Reception: Building A. Office hours Mon–Sat 9 AM–5 PM. "
    "Reception: reception@kluniversity.ac.in | board +91-4562-235000.\n\n"
    "Accreditation: NAAC A++ (CGPA 3.65), NBA for major engineering programs, ISO 9001:2015. "
    "NIRF (indicative): Engineering ~36, University ~29, Overall ~48.\n\n"
    "Programs: B.Tech (CSE, IT, AI/ML, ECE, EEE, Mechanical, Civil), BBA, BCA, B.Sc, B.Com, B.A, B.Ed; "
    "PG M.Tech, MBA, MCA, M.Sc, M.Com, M.A, M.Phil; Ph.D. across disciplines.\n\n"
    "Admissions: Apply at kluniversity.ac.in. Application fee about Rs 1500 (general) / Rs 750 (reserved). "
    "Typical process: online form, document verification, merit/counselling, fee payment. "
    "Documents: 10th/12th marksheets, Aadhaar, photos, category certificate if any, entrance score, TC. "
    "Admission Office: admission@kluniversity.ac.in | +91-4562-235000.\n\n"
    "Fees and scholarships: B.Tech program fee band roughly Rs 3.77L–9.2L; hostel about Rs 45,000–65,000/year. "
    "Merit and need-based scholarships (KEEE and others). Finance: fees@kluniversity.ac.in | +91-4562-235003.\n\n"
    "Academics: Academics/Exams academics@kluniversity.ac.in | +91-4562-235004. "
    "About 75% attendance is required for end-semester exams. Library, labs, and exam branch are on Academic Quad/Block.\n\n"
    "Hostel: Boys ~500 and Girls ~400 beds, mess, WiFi, 24/7 security. "
    "Hostel Office hostel@kluniversity.ac.in | +91-4562-235001. Warden warden@kluniversity.ac.in. "
    "Leave usually needs advance notice; curfew typically 10 PM; ragging prohibited.\n\n"
    "Placements: Placement Cell placement@kluniversity.ac.in | +91-4562-235002. "
    "Recent indicative outcomes ~92% placement, average ~8.5 LPA, highest ~44 LPA, 150+ recruiters.\n\n"
    "Facilities: Central library (50,000+ books), labs, stadium, gym, medical center, WiFi, buses, cafeterias.\n\n"
    "Directions from Reception Building A: Library — Academic Quad north wing; Examination Branch — Academic Block "
    "ground floor; Accounts — Admin Block; Placement — Career Services; Hostels — past sports ground.\n\n"
    "Ask me any follow-up (contacts, directions, admissions, fees overview, hostel overview, placements), "
    "or use Academics / Hostel / Fees pages in Campus-GPT for personal records."
)

# In-process cache filled from DB (never used unless DB load succeeded)
_cache: dict[str, str] = {}


async def ensure_fact_sheets(db: AsyncSession) -> None:
    """Insert default fact sheets into the database if missing."""
    from app.models.platform import CampusFactSheet

    defaults = {
        "reception_brief": ("Reception campus brief", _SEED_RECEPTION_BRIEF),
        "reception_full": ("Reception full reply", _SEED_RECEPTION_FULL),
    }
    for key, (title, body) in defaults.items():
        row = (
            await db.execute(select(CampusFactSheet).where(CampusFactSheet.key == key))
        ).scalar_one_or_none()
        if row is None:
            db.add(CampusFactSheet(key=key, title=title, body=body))
            _cache[key] = body
        else:
            _cache[key] = row.body or body
    await db.flush()


async def get_fact(db: AsyncSession | None, key: str) -> str:
    """Load a fact sheet from the database (preferred) or warm cache."""
    if key in _cache and _cache[key]:
        # Still refresh from DB when a session is available
        pass
    if db is not None:
        try:
            from app.models.platform import CampusFactSheet

            row = (
                await db.execute(select(CampusFactSheet).where(CampusFactSheet.key == key))
            ).scalar_one_or_none()
            if row and row.body:
                _cache[key] = row.body
                return row.body
        except Exception:
            pass
    return _cache.get(key, "")


async def reception_context_block_async(db: AsyncSession | None = None) -> str:
    text = await get_fact(db, "reception_brief")
    return text


async def reception_full_reply_async(db: AsyncSession | None = None) -> str:
    text = await get_fact(db, "reception_full")
    return text


def reception_context_block() -> str:
    """Sync helper — returns DB-backed cache only (empty if DB not loaded yet)."""
    return _cache.get("reception_brief", "")


def reception_full_reply() -> str:
    """Sync helper — returns DB-backed cache only (empty if DB not loaded yet)."""
    return _cache.get("reception_full", "")


def wants_full_campus_brief(query: str) -> bool:
    q = (query or "").lower()
    triggers = (
        "complete information",
        "full information",
        "about kare",
        "about college",
        "about the college",
        "about university",
        "about the university",
        "tell me about kare",
        "everything about",
        "overview of kare",
        "overview of the college",
        "campus information",
    )
    return any(t in q for t in triggers)
