"""UNP Grading System - class list PDF parser.

Parses the portal's "Class List" report: student rows plus the class
metadata block (class code, section, subject, term, school year,
instructor, schedule).
"""
import re
import pdfplumber

STUDENT_RE = re.compile(
    r"^(\d+)\s+(\d{2}-\d{4,6})\s+(.+?)\s+([MF])\s+([A-Z]{2,6})\s+(\d)"
    r"(?:\s+(\d{9,12}))?(?:\s+(\S+@\S+))?\s*$")
CLASS_RE = re.compile(
    r"Class:\s*(\S+)\s*::\s*(.+?)\s*::\s*(.+?)\s*::\s*(.+)$")
TERM_RE = re.compile(r"Class List\s*\(([^)]+?)\s+(\d{4}-\d{4})\)")
SCHED_RE = re.compile(r"Sched:\s*(.+)$")


def parse_class_list(path_or_file):
    """Return {'students': [...], 'meta': {...}}."""
    students = []
    meta = {"class_code": "", "section": "", "subject_code": "",
            "subject_title": "", "term": "", "school_year": "",
            "instructor": "", "schedule": ""}
    lines = []
    with pdfplumber.open(path_or_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())

    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        m = STUDENT_RE.match(line)
        if m:
            students.append({
                "no": int(m.group(1)),
                "id": m.group(2),
                "name": re.sub(r"\s+", " ", m.group(3)).strip(),
                "sex": m.group(4),
                "course": m.group(5),
                "year": m.group(6),
                "cp": m.group(7) or "",
                "email": m.group(8) or "",
            })
            continue
        m = CLASS_RE.search(line)
        if m:
            meta["class_code"] = m.group(1)
            meta["section"] = m.group(2)
            meta["subject_code"] = m.group(3)
            # subject title may be followed by "Sched: ..." on the same line
            rest = m.group(4)
            sm = SCHED_RE.search(rest)
            if sm:
                meta["subject_title"] = rest[:sm.start()].strip()
                meta["schedule"] = sm.group(1).strip()
            else:
                meta["subject_title"] = rest.strip()
            # instructor is usually the non-empty line just above
            for back in range(i - 1, max(-1, i - 4), -1):
                prev = lines[back].strip()
                if prev and "Class List" not in prev and \
                        "University" not in prev and "Vigan" not in prev:
                    meta["instructor"] = prev
                    break
            continue
        m = TERM_RE.search(line)
        if m:
            meta["term"], meta["school_year"] = m.group(1), m.group(2)
            continue
        m = SCHED_RE.search(line)
        if m and not meta["schedule"]:
            meta["schedule"] = m.group(1).strip()

    students.sort(key=lambda s: s["no"])
    return {"students": students, "meta": meta}
