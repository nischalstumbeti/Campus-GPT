"""Fill empty cabin details for officials. Does not overwrite a value already saved."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import User

OFFICIAL_ROLES = {
    "faculty",
    "hod",
    "hostel_admin",
    "warden",
    "hostel_warden",
    "admin",
    "university_admin",
    "super_admin",
    "department_admin",
    "exam_admin",
    "school_dean",
    "director",
    "operator",
    "coe",
    "developer",
}

# username -> designation, department/office, school, cabin block
DEFAULTS = {
    "faculty.demo": ("Associate Professor", "Computer Science & Engineering", "School of Computing", "CSE Block, Cabin C-201"),
    "arun.kumar": ("Assistant Professor", "Computer Science & Engineering", "School of Computing", "CSE Block, Cabin C-202"),
    "meena.iyer": ("Professor", "Computer Science & Engineering", "School of Computing", "CSE Block, Cabin C-203"),
    "suresh.babu": ("Assistant Professor", "Computer Science & Engineering", "School of Computing", "CSE Block, Cabin C-204"),
    "kavitha.n": ("Associate Professor", "Computer Science & Engineering", "School of Computing", "CSE Block, Cabin C-205"),
    "hod.demo": ("Professor & Head", "Computer Science & Engineering", "School of Computing", "CSE Block, Cabin C-101"),
    "warden.demo": ("Hostel Warden", "Hostel Office", "Student Welfare", "B-Block, Warden Office"),
    "admin.demo": ("University Administrator", "Administration", "University Office", "Admin Block, A-001"),
}


async def ensure_directory() -> dict:
    updated = 0
    async with SessionLocal() as db:
        users = (
            await db.execute(
                select(User)
                .where(User.role.in_(OFFICIAL_ROLES))
                .options(selectinload(User.faculty))
            )
        ).scalars().all()
        for user in users:
            preset = DEFAULTS.get(user.username)
            if preset:
                designation, office, school, block = preset
            else:
                designation = "Faculty" if user.role in ("faculty", "hod") else user.role.replace("_", " ").title()
                office = "Computer Science & Engineering" if user.role in ("faculty", "hod") else "Administration"
                school = "School of Computing" if user.role in ("faculty", "hod") else "University Office"
                block = "CSE Block" if user.role in ("faculty", "hod") else "Admin Block"
            changed = False
            if not (user.designation or "").strip():
                user.designation = designation
                changed = True
            if not (user.office or "").strip():
                user.office = office
                changed = True
            if not (user.school or "").strip():
                user.school = school
                changed = True
            if not (user.cabin_block or "").strip():
                user.cabin_block = block
                changed = True
            if changed:
                updated += 1
        await db.commit()
    return {"ok": True, "updated": updated}
