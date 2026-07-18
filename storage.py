"""UNP Grading System - local JSON storage, one file per class."""
import json
import os
import re
import time

import engine


def data_dir():
    d = os.path.join(os.path.expanduser("~"), "UNPGradingSystem", "classes")
    os.makedirs(d, exist_ok=True)
    return d


def _slug(text):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_") or "class"


def new_class(meta, students):
    """Build a fresh class record from parsed class list data."""
    counts = dict(engine.DEFAULT_COLUMNS)
    hps = {term: {c: [None] * counts[c] for c in engine.COMPONENTS}
           for term in ("midterm", "finals")}
    return {
        "version": 1,
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "meta": dict(meta),
        "config": {
            "preset": "Lecture",
            "weights": {c: w for c, w in zip(
                engine.COMPONENTS, engine.PRESETS["Lecture"])},
            "labels": dict(engine.DEFAULT_LABELS),
            "columns": counts,
            "hps": hps,
            "semestral_weights": {"midterm": 0.5, "finals": 0.5},
            "transmutation": [list(r) for r in
                              engine.DEFAULT_TRANSMUTATION],
        },
        "students": list(students),
        "scores": {"midterm": {}, "finals": {}},
    }


def class_path(cls):
    m = cls["meta"]
    name = f"{_slug(m.get('subject_code',''))}_{_slug(m.get('section',''))}"
    return os.path.join(data_dir(), name + ".json")


def save_class(cls, path=None):
    path = path or class_path(cls)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cls, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return path


def load_class(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def list_classes():
    out = []
    for fn in sorted(os.listdir(data_dir())):
        if fn.endswith(".json"):
            path = os.path.join(data_dir(), fn)
            try:
                cls = load_class(path)
                m = cls.get("meta", {})
                out.append({
                    "path": path,
                    "label": f"{m.get('subject_code','?')} - "
                             f"{m.get('section','?')} - "
                             f"{m.get('term','?')} {m.get('school_year','')}",
                    "students": len(cls.get("students", [])),
                })
            except (json.JSONDecodeError, OSError):
                continue
    return out


def get_scores(cls, term, student_id, comp):
    n = cls["config"]["columns"][comp]
    row = cls["scores"].setdefault(term, {}).setdefault(student_id, {})
    vals = row.setdefault(comp, [None] * n)
    while len(vals) < n:
        vals.append(None)
    return vals[:n]


def set_score(cls, term, student_id, comp, idx, value):
    vals = cls["scores"].setdefault(term, {}).setdefault(
        student_id, {}).setdefault(
        comp, [None] * cls["config"]["columns"][comp])
    while len(vals) <= idx:
        vals.append(None)
    vals[idx] = value
