"""Seed initial knowledge base with KARE (Kalasalingam University) institutional data."""
import asyncio
from app.config import get_settings
from app.services.embeddings import get_embedding
from app.services.vector_store import get_vector_store
import numpy as np

# Comprehensive KARE dummy data for RAG - covers eligibility, fees, scholarships, courses, facilities
SAMPLE_KNOWLEDGE = [
    "Kalasalingam Academy of Research and Education (KARE) is a deemed university in Srivilliputtur, Virudhunagar, Tamil Nadu. Established 1984. Campus-GPT is the AI-powered campus assistant for KARE.",
    "NAAC A++ accreditation with CGPA 3.65, valid until 2028. NBA accredited engineering programs. ISO 9001:2015. UGC Deemed University.",
    "NIRF 2023-24: Overall rank 48, Engineering 36, University 29.",
    "Placement 2023-24: Highest 44 LPA, average 8.5 LPA, 92% placement rate. 150+ companies, 850+ offers. Top recruiters: Microsoft, Google, Amazon, TCS, Infosys, Wipro, Cognizant.",
    "B.Tech eligibility: 10+2 PCM, 60% aggregate. JEE Main or TNEA score. Seats ~2616. Fee ₹3.77L to ₹9.2L for 4 years.",
    "M.Tech eligibility: B.Tech/B.E. relevant branch, 60%. GATE preferred. 22 specializations, 372 seats. Fee ₹1.36L to ₹5.3L for 2 years.",
    "MBA eligibility: Any UG degree, 50% aggregate. CAT/MAT/CMAT. 360 seats. Fee ₹1.38L to ₹5.3L for 2 years.",
    "Scholarships: KEEE Merit 25%-100% tuition waiver. Arts & Science Merit 50% for 90%+ in 12th. CLAT ₹75,000/year. KLSAT ₹50,000/year. Lateral entry 25% waiver. Need-based and SC/ST schemes available.",
    "Hostel: Boys 500 beds, Girls 400 beds. Fee ₹45,000-65,000/year. WiFi, mess, 24/7 security. Contact hostel@kluniversity.ac.in.",
    "Application fee: Rs 1500 general, Rs 750 reserved. Last date UG June 30, PG July 15. Apply at kluniversity.ac.in.",
    "Documents: 10th/12th marksheets, Aadhaar, photos, category certificate, entrance score card, transfer certificate.",
    "Admission process: Online application, document verification, merit list, counselling, fee payment within 7 days.",
    "Programs: B.Tech (CSE, ECE, EEE, Mech, Civil, IT, AI/ML), BBA, BCA, B.Sc, B.Com, B.A, B.Ed. PG: M.Tech, MBA, MCA, M.Sc, M.Com, M.A, M.Phil. Ph.D in multiple disciplines.",
    "Campus facilities: Library 50,000+ books, 24/7 labs, sports stadium, gym, hostel, medical center, WiFi, transport, cafeteria.",
    "Address: KARE, Krishnankoil, Srivilliputtur, Virudhunagar, Tamil Nadu 626126. Reception Building A. Office Mon-Sat 9AM-5PM.",
    "Department contacts: Admission admission@kluniversity.ac.in. Hostel hostel@kluniversity.ac.in. Placement placement@kluniversity.ac.in. Finance fees@kluniversity.ac.in. Academics academics@kluniversity.ac.in. Reception reception@kluniversity.ac.in.",
    "Hostel rules: Leave 48hrs advance. Curfew 10PM. Ragging prohibited. Warden warden@kluniversity.ac.in.",
    "CSE/IT highest placement avg. ECE/EEE for hardware. Mech/Civil core industries. MBA for management. BBA moderate fee foundation.",
    "BBA B.Sc B.A fee around ₹1.1L per year. BCA ₹9.2L. MCA ₹1.4L. Ph.D ₹2.1L-70k.",
    "Reception desk (Building A) helps with all campus information: office locations, visiting hours, department contacts, admissions overview, fee offices, hostel guidance, placement cell, transport, and medical center.",
    "Campus map directions from Reception Building A: Library is Academic Quad north wing; Examination Branch is Academic Block ground floor; Accounts/Finance is Admin Block; Placement Cell is Career Services building; Hostels are past the sports ground residential zone.",
    "Academic regulations: minimum 75% attendance required to appear for end-semester examinations. Internal assessments include CAT tests and assignments. Contact academics@kluniversity.ac.in for exam schedules.",
    "Transport: college bus services for day scholars; bus pass and route details from Transport desk near Accounts. Medical center provides first aid and referral support during office hours.",
    "Visitor policy: carry government photo ID; prior appointment recommended during peak admission season. Main gate security can guide visitors to Reception Building A.",
    "Student services available via Campus-GPT: Chat desks (Guide, Academics, Faculty, Admission, Reception, Hostel, Warden), Timetable, Attendance/Marks, Fees, Messages, Hostel Leave, Career, Consent/Privacy.",
]

async def seed():
    """Seed vector store with sample chunks."""
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        return
    store = get_vector_store()
    if store.count() > 0:
        return
    print("Seeding KARE knowledge base...")
    embeddings = []
    for text in SAMPLE_KNOWLEDGE:
        emb = await get_embedding(text)
        embeddings.append(emb)
    metadatas = [{"text": t, "content": t, "source": "KARE_seed", "chunk_id": i} for i, t in enumerate(SAMPLE_KNOWLEDGE)]
    store.add(np.array(embeddings).astype(np.float32), metadatas)
    print(f"Seeded {len(SAMPLE_KNOWLEDGE)} chunks.")

if __name__ == "__main__":
    asyncio.run(seed())
