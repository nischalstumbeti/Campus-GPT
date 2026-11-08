"""A small text PDF so the hall ticket can be opened, printed, and downloaded."""
from __future__ import annotations


def _escape(value: str) -> str:
    cleaned = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return cleaned.encode("latin-1", "replace").decode("latin-1")


def _wrap(text: str, width: int = 92) -> list[str]:
    words = (text or "").replace("\r", "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        piece = word if not current else f"{current} {word}"
        if len(piece) > width:
            if current:
                lines.append(current)
            current = word[:width]
        else:
            current = piece
    if current:
        lines.append(current)
    return lines


def build_hall_ticket_pdf(lines: list[str]) -> bytes:
    pages: list[list[str]] = []
    page: list[str] = []
    for line in lines:
        page.append(line)
        if len(page) >= 46:
            pages.append(page)
            page = []
    if page or not pages:
        pages.append(page or [""])

    objects: list[bytes] = []

    def add(body: str | bytes) -> int:
        raw = body.encode("latin-1") if isinstance(body, str) else body
        objects.append(raw)
        return len(objects)

    font_id = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids: list[int] = []
    content_ids: list[int] = []
    for chunk in pages:
        commands = ["BT", "/F1 11 Tf", "48 790 Td", "15 TL"]
        for index, line in enumerate(chunk):
            if index:
                commands.append("T*")
            commands.append(f"({_escape(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", "replace")
        content_ids.append(add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream"))
        page_ids.append(0)

    kids = " ".join(f"{index} 0 R" for index in range(len(objects) + 1, len(objects) + 1 + len(pages)))
    # pages object is created after we know ids; assign page objects now
    pages_index_placeholder = len(objects) + len(pages) + 1
    for offset, content_id in enumerate(content_ids):
        page_ids[offset] = add(
            f"<< /Type /Page /Parent {pages_index_placeholder} 0 R /MediaBox [0 0 595 842] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
    pages_id = add("<< /Type /Pages /Count %d /Kids [%s] >>" % (len(page_ids), " ".join(f"{pid} 0 R" for pid in page_ids)))
    catalog_id = add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(out)


def ticket_lines(ticket: dict) -> list[str]:
    lines = [
        ticket.get("institution") or "Campus Information System",
        ticket.get("title") or "Hall Ticket",
        ticket.get("session_name") or "",
        "",
        f"Name: {ticket.get('name', '')}",
        f"Register number: {ticket.get('student_id', '')}",
        f"Programme: {ticket.get('program', '')}",
        f"Batch: {ticket.get('batch', '')}    Semester: {ticket.get('semester', '')}    Section: {ticket.get('section', '')}",
        "",
        "Course        Exam                 Date         Time    Venue",
        "-" * 78,
    ]
    for exam in ticket.get("exams") or []:
        lines.append(
            f"{exam.get('code', ''):<12} {str(exam.get('type', ''))[:18]:<20} {exam.get('date', ''):<12} {exam.get('start', ''):<7} {exam.get('venue', '')}"
        )
        if exam.get("attendance") is not None:
            lines.append(f"             Attendance {exam.get('attendance')}%")
        name = exam.get("course") or ""
        if name:
            lines.append(f"             {name}")
    if not ticket.get("exams"):
        lines.append("No examinations are scheduled.")
    lines.append("")
    lines.append("Instructions")
    for paragraph in (ticket.get("instructions") or "").splitlines() or ["Carry this hall ticket and your identity card."]:
        lines.extend(_wrap(paragraph))
    lines.append("")
    if ticket.get("footer"):
        lines.append(ticket["footer"])
    lines.append("")
    lines.append("Student signature                    Controller of Examinations")
    return lines
