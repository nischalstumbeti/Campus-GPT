"""Demo responses - works without any API key. Comprehensive KARE (Kalasalingam University) dummy data."""

# Agent-specific intro prefixes
AGENT_INTROS = {
    "admission": "[Admission Agent] ",
    "reception": "[Reception] ",
    "hostel": "[Hostel Manager] ",
    "warden": "[Warden] ",
    "academic": "[Academic Operations] ",
    "faculty": "[Faculty Desk] ",
    "general": "",
}

# Department contacts for escalation / complex queries
DEPARTMENT_CONTACTS = """
**Department Contacts (Kalasalingam Academy of Research and Education):**
- **Admission Office:** admission@kluniversity.ac.in | +91-4562-235000
- **Hostel Office:** hostel@kluniversity.ac.in | +91-4562-235001
- **Placement Cell:** placement@kluniversity.ac.in | +91-4562-235002
- **Finance/Scholarship:** fees@kluniversity.ac.in | +91-4562-235003
- **Academic/Examinations:** academics@kluniversity.ac.in | +91-4562-235004
- **Main Reception:** reception@kluniversity.ac.in | 1800-XXX-XXXX
*Srivilliputtur, Virudhunagar, Tamil Nadu*
"""

# Keyword -> response (case-insensitive partial match). KARE-specific dummy data.
DEMO_FAQ = [
    (["timetable", "time table", "class schedule", "today's class", "lab slot"],
     "I do not invent personal class schedules in demo mode.\n\n"
     "Open **Timetable** in Campus-GPT (same KARE UIS records as chat), or sign in with a linked UIS student "
     "and ask again with Gemini enabled for a live answer.\n"
     "*Source: KARE UIS timetable API*"),
    (["attendance", "shortage", "75%"],
     "**Attendance (Ananya Krishnan, KARE2024CSE045):**\n"
     "- CSE501 DBMS: 90.6% (Good)\n"
     "- CSE502 Computer Networks: **75.0% (Watch)** — do not miss further periods\n"
     "- CSE503 TOC: 92.9% · CSE504 SE: 92.9% · CSE505 AI: 84.6%\n"
     "- Labs: DBMS Lab 100% · Networks Lab 83.3%\n"
     "KARE requires **≥75%** to sit end-semester exams.\n"
     "*Source: Academic database*"),
    (["marks", "internal mark", "cat-1", "cat 2", "grades"],
     "**Internal marks (demo SIS record):**\n"
     "- **DBMS:** CAT-1 42/50, CAT-2 38/50, Assignment 18/20\n"
     "- **Networks:** CAT-1 35/50, CAT-2 31/50 — needs revision\n"
     "- **TOC:** CAT-1 44/50, CAT-2 40/50\n"
     "- **SE:** CAT-1 39/50, CAT-2 41/50\n"
     "- **AI:** CAT-1 36/50, CAT-2 33/50\n"
     "Open **Marks** for the full assessment table.\n"
     "*Source: Academic database*"),
    (["office hours", "faculty available", "availability", "cabin"],
     "**Faculty availability (CSE):**\n"
     "- **Dr. Priya Raman** (DBMS, CSE-214): Mon 3–4 PM, Wed 4–5 PM\n"
     "- **Prof. Arun Kumar** (Networks, CSE-118): Tue & Fri 3–4 PM\n"
     "- **Dr. Meena Iyer** (TOC, CSE-301): Mon 4–5 PM, Thu 3–4 PM\n"
     "- **Prof. Suresh Babu** (SE, CSE-122): Wed 3–4 PM\n"
     "- **Dr. Kavitha N** (AI, CSE-220): Thu 4–5 PM\n"
     "Department meeting: Friday 4–5 PM, HoD Conference Room.\n"
     "*Source: Academic database*"),
    (["study plan", "plan my week", "academic schedule", "planner"],
     "**Plan from academic schedule:**\n"
     "- Protect Networks attendance (75%) — no more skips.\n"
     "- Use Mon–Fri 3–5 PM free blocks for CAT revision (Networks & AI internals are weaker).\n"
     "- Book Dr. Priya (Wed 4 PM) or Prof. Arun (Tue 3 PM) during office hours.\n"
     "- CAT-2 window: 10–14 Nov 2026; end-semester 8–20 Dec 2026.\n"
     "Open **Planner** for auto-generated slots.\n"
     "*Source: Academic database + calendar*"),
    (["circular", "draft", "recurring", "notice", "meeting invite"],
     "**Recurring drafts Campus-GPT can generate:**\n"
     "- Weekly timetable reminder for the section\n"
     "- Faculty meeting invite (every Friday 4 PM)\n"
     "- Attendance shortage follow-up\n"
     "- CAT / end-semester reminder\n"
     "- Office-hours circular\n"
     "Open **Drafts**, pick a type, and copy the circular. Faculty can save it for reuse.\n"
     "*Source: Academic calendar + timetable*"),
    # Eligibility criteria
    (["eligibility", "qualify", "criteria", "cutoff", "marks required", "minimum"],
     "**Eligibility Criteria (KARE):**\n"
     "- **B.Tech:** 10+2 with PCM, minimum 60% aggregate. JEE Main / TNEA score considered.\n"
     "- **M.Tech:** B.Tech/B.E. in relevant branch, minimum 60%. GATE score preferred.\n"
     "- **MBA:** Any UG degree, 50% aggregate. CAT/MAT/CMAT score considered.\n"
     "- **BBA/B.Com:** 10+2 from recognized board, 50% aggregate.\n"
     "- **M.Sc/M.A:** Relevant UG degree, 55% aggregate.\n"
     "- **Ph.D:** PG degree with 55%. UGC-NET/CSIR-NET exempts entrance.\n"
     "*Source: KARE Admission Brochure 2024-25*"),

    (["fee", "fees", "tuition", "cost", "charges"],
     "**Fee Structure (KARE 2024-25):**\n"
     "- **B.Tech:** ₹3.77 L - ₹9.2 L (total 4 years, varies by branch)\n"
     "- **M.Tech:** ₹1.36 L - ₹5.3 L (2 years, 22 specializations)\n"
     "- **MBA:** ₹1.38 L - ₹5.3 L (2 years)\n"
     "- **BBA/B.Sc/B.A:** ₹1.1 L - ₹1.18 L (3 years)\n"
     "- **Hostel (optional):** ₹45,000 - ₹65,000 per year\n"
     "- **One-time:** Caution deposit ₹10,000 (refundable)\n"
     "*Contact Finance Office for exact branch-wise fees. Source: KARE Fee Circular*"),

    (["scholarship", "financial aid", "fee waiver", "merit", "sc st"],
     "**Scholarships at KARE:**\n"
     "- **KEEE Merit:** 25%-100% tuition waiver (top rankers)\n"
     "- **Arts & Science Merit:** 50% waiver for 90%+ in 12th\n"
     "- **CLAT Scholarship:** ₹75,000/year for law aspirants\n"
     "- **KLSAT Scholarship:** ₹50,000/year (entrance merit)\n"
     "- **Lateral Entry (Diploma):** 25% tuition waiver\n"
     "- **Need-based:** Apply through financial aid office\n"
     "- **SC/ST/OBC:** Government schemes; institution top-up available\n"
     "*Source: KARE Scholarship Cell*"),

    (["courses", "programs", "branches", "btech", "mtech", "mba", "bc a"],
     "**Programs Offered (KARE):**\n"
     "- **UG:** B.Tech (CSE, ECE, EEE, Mech, Civil, IT, AI/ML), BBA, BCA, B.Sc, B.Com, B.A, B.Ed\n"
     "- **PG:** M.Tech (22 specializations), MBA, MCA, M.Sc, M.Com, M.A, M.Phil\n"
     "- **Research:** Ph.D in Engineering, Science, Management, Humanities\n"
     "- **Total seats:** B.Tech ~2,616, M.Tech ~372, MBA ~360\n"
     "*Source: KARE Academic Calendar*"),

    (["compare", "which branch", "better", "cse vs ece", "best course"],
     "**Comparing Branches at KARE:**\n"
     "- **CSE/IT:** Highest placement avg (~9 LPA), most companies, AI/ML specializations\n"
     "- **ECE/EEE:** Strong hardware/embedded, ~7.5 LPA avg\n"
     "- **Mech/Civil:** Core industries, ~6.5 LPA avg\n"
     "- **MBA:** Corporate roles, avg ~8 LPA; good for management aspirants\n"
     "- **BCA:** IT-focused, shorter duration; MCA pathway available\n"
     "Choose based on interest, JEE rank, and career goals.\n"
     "*Source: Placement Cell & Academic Office*"),

    # Hostel & accommodation
    (["hostel", "accommodation", "stay", "room", "boarding"],
     "**Hostel at KARE:**\n"
     "- **Boys hostel:** 500 beds (45 currently available)\n"
     "- **Girls hostel:** 400 beds (38 currently available)\n"
     "- **Fee:** ₹45,000 - ₹65,000/year (AC/Non-AC, single/shared)\n"
     "- **Facilities:** WiFi, mess, recreation room, 24/7 security\n"
     "- **Location:** On-campus, Srivilliputtur\n"
     "- **Booking:** Apply via admission portal or contact hostel@kluniversity.ac.in\n"
     "*Source: Hostel Office*"),

    # Placement
    (["placement", "job", "salary", "package", "recruitment", "companies"],
     "**Placement Statistics (KARE 2023-24):**\n"
     "- Highest package: 44 LPA\n"
     "- Average package: 8.5 LPA\n"
     "- Placement rate: 92%\n"
     "- 150+ companies, 850+ offers\n"
     "- Top recruiters: Microsoft, Google, Amazon, TCS, Infosys, Wipro, Cognizant\n"
     "- Training: Pre-placement training, mock interviews, resume workshops\n"
     "*Source: Placement Cell*"),

    # Accreditation & ranking
    (["naac", "accreditation", "grade", "accredited", "nba"],
     "**Accreditation (KARE):**\n"
     "- NAAC Grade: A++ (CGPA 3.65)\n"
     "- Valid until 2028 (4th cycle)\n"
     "- NBA accredited engineering programs\n"
     "- ISO 9001:2015 certified\n"
     "- UGC Deemed University status\n"
     "*Source: NAAC/Institutional records*"),

    (["nirf", "ranking", "rank"],
     "**NIRF Rankings (KARE 2023-24):**\n"
     "- Overall: 48\n"
     "- Engineering: 36\n"
     "- University: 29\n"
     "*Source: NIRF/MHRD*"),

    # Application & admission process
    (["application", "apply", "admission process", "how to apply"],
     "**Admission Process (KARE):**\n"
     "1. **Apply online:** Visit kluniversity.ac.in admission portal\n"
     "2. **Application fee:** Rs 1,500 (general), Rs 750 (reserved)\n"
     "3. **Documents:** 10th/12th marksheets, Aadhaar, photos, category certificate\n"
     "4. **Last dates:** UG ~June 30, PG ~July 15 (check website for current year)\n"
     "5. **Merit list & counselling:** Based on JEE/TNEA/CAT/MAT etc.\n"
     "6. **Fee payment & enrollment:** Within 7 days of seat allotment\n"
     "*Source: Admission Office*"),

    (["documents", "documents required", "certificates"],
     "**Documents Required for Admission:**\n"
     "- 10th & 12th marksheets and certificates\n"
     "- Aadhaar card (original + copy)\n"
     "- Passport size photos (4)\n"
     "- Category certificate (SC/ST/OBC) if applicable\n"
     "- JEE Main / TNEA / GATE / CAT score card (as applicable)\n"
     "- Transfer certificate from previous institution\n"
     "- Migration certificate (if from other university)\n"
     "*Source: Admission Office*"),

    # Campus facilities
    (["facilities", "campus", "library", "lab", "infrastructure"],
     "**Campus Facilities (KARE):**\n"
     "- **Library:** 50,000+ books, e-journals, digital resources, 24/7 reading hall\n"
     "- **Labs:** Computer labs (24/7), engineering labs, language lab\n"
     "- **Sports:** Indoor & outdoor stadium, gym, NCC/NSS\n"
     "- **Hostel:** On-campus accommodation, mess, WiFi\n"
     "- **Medical:** Health center, ambulance, tie-up with nearby hospital\n"
     "- **Transport:** Bus facility from Srivilliputtur and nearby towns\n"
     "- **Cafeteria & canteen:** Multiple food outlets\n"
     "- **WiFi:** Campus-wide connectivity\n"
     "*Source: Campus directory*"),

    # Reception & general
    (["reception", "contact", "office", "direction", "visit", "address"],
     "**Reception & Contact (KARE):**\n"
     "- **Address:** Kalasalingam Academy of Research and Education, Krishnankoil, Srivilliputtur, Virudhunagar, Tamil Nadu 626126\n"
     "- **Main reception:** Building A, Ground floor\n"
     "- **Office hours:** Mon–Sat 9 AM–5 PM\n"
     "- **Helpline:** 1800-XXX-XXXX\n"
     "- **For visits:** Carry ID proof; prior appointment recommended during admission season\n"
     "*Source: Reception*"),

    # Warden & hostel rules
    (["warden", "complaint", "discipline", "leave", "rules", "curfew"],
     "**Hostel Rules & Warden (KARE):**\n"
     "- **Warden office:** Inside hostel block, accessible 8 AM-8 PM\n"
     "- **Leave:** Submit 48 hours in advance; parent consent required for outstation\n"
     "- **Curfew:** 10 PM (varies by block); late entry with prior permission\n"
     "- **Complaints:** warden@kluniversity.ac.in or in-person\n"
     "- **Discipline:** Ragging prohibited; strict adherence to hostel norms\n"
     "*Source: Warden office*"),

    # Last date & deadlines
    (["last date", "deadline", "closing date", "when to apply"],
     "**Admission Deadlines (Typical - check website):**\n"
     "- **UG (B.Tech, BBA, B.Sc, etc.):** June 30\n"
     "- **PG (M.Tech, MBA, M.Sc, etc.):** July 15\n"
     "- **Ph.D:** Rolling admissions; check department\n"
     "- *Verify current year dates at kluniversity.ac.in*\n"
     "*Source: Admission Office*"),
]

# Fallback when no match - includes department redirection
DEMO_FALLBACK = (
    "I'm running in **demo mode** without an AI API. I have pre-loaded responses for KARE (Kalasalingam Academy of Research and Education). "
    "Try asking about: timetable, attendance, marks, faculty office hours, study planning, recurring circulars, eligibility, fees, hostel, or placements. "
    "For complex queries, contact the appropriate department:\n"
    "- **Admission:** admission@kluniversity.ac.in\n"
    "- **Hostel:** hostel@kluniversity.ac.in\n"
    "- **Placement:** placement@kluniversity.ac.in\n"
    "- **Finance/Scholarship:** fees@kluniversity.ac.in\n"
    "Connect Gemini API for full intelligent responses."
)


def get_demo_response(query: str, agent_type: str = "general") -> tuple[str, float, list[dict]]:
    """Match query to demo FAQ. Returns (answer, confidence, sources)."""
    q = query.lower().strip()
    intro = AGENT_INTROS.get(agent_type, "")
    # Avoid accidental substring matches on tiny greetings (e.g. hi ⊂ which)
    try:
        from app.ai.intent import greeting_reply, is_greeting

        if is_greeting(query):
            return greeting_reply(), 1.0, []
    except Exception:
        pass
    try:
        from app.services.agent_scope import (
            hostel_off_topic_reply,
            is_clearly_off_hostel,
            is_hostel_scoped_query,
            should_enforce_hostel_only,
        )

        if should_enforce_hostel_only(agent_type) and (
            is_clearly_off_hostel(query) or not is_hostel_scoped_query(query)
        ):
            if is_clearly_off_hostel(query) or len(q.split()) >= 3:
                return hostel_off_topic_reply(), 1.0, []
    except Exception:
        pass
    for keywords, answer in DEMO_FAQ:
        # Require keyword length >= 3 or whole-word-ish match for short tokens
        matched = False
        for k in keywords:
            if len(k) <= 2:
                continue
            if k in q:
                matched = True
                break
        if matched:
            return intro + answer, 0.85, [{"source": "KARE Demo FAQ", "excerpt": answer[:150] + "...", "relevance": 0.9}]
    return intro + DEMO_FALLBACK, 0.5, [{"source": "Demo mode", "relevance": 0.5}]


# KARE-specific recommendations for demo mode
DEMO_RECOMMENDATIONS = """
**Course & Branch Recommendations (KARE - Demo Mode)**

Based on your profile, here are suggested pathways at Kalasalingam Academy of Research and Education:

1. **B.Tech Computer Science / IT** – Strong placement record (~9 LPA avg). Ideal if you have tech interest and good JEE Main scores. Most companies recruit from CSE/IT.

2. **B.Tech ECE / EEE** – For hardware/embedded interests. NAAC A++ institution supports quality education. ~7.5 LPA avg placement.

3. **MBA** – If you have work experience or strong CAT/MAT scores. Placement cell has corporate ties. Avg ~8 LPA.

4. **BBA** – For business/management with moderate investment (~₹1.1L/year). Good foundation for MBA later.

5. **M.Tech** – 22 specializations; GATE score preferred. Fee range ₹1.36L-5.3L. Good for specialization.

**Why KARE?** NAAC A++, NIRF ranked (Engg 36, Uni 29), 92% placement rate, scholarships up to 100% for merit. Connect Gemini API for personalized AI recommendations.
"""
