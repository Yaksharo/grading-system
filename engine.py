"""UNP Grading System - grading engine.

Implements the E-Class Record formulation exactly as used in the CCIT
gradesheets: base-50 percentage scores, weighted components, the
transmutation table, and the 50/50 semestral combination.
"""

COMPONENTS = ["quizzes", "participation", "project", "exam"]

DEFAULT_LABELS = {
    "quizzes": "Quizzes / Activity",
    "participation": "Class Participation / Seatwork / Recitation",
    "project": "Project / Assignment / Exercises / Reports",
    "exam": "Exam",
}

# weights per subject type, component order as in COMPONENTS
PRESETS = {
    "Lecture with Laboratory": [20, 25, 25, 30],
    "Lecture": [30, 15, 15, 40],
    "NSTP": [30, 10, 20, 40],
}

# lower bound -> (grade, descriptor); PASSED at initial >= 75
DEFAULT_TRANSMUTATION = [
    (50, 5.00, "Failed"),
    (63, 4.00, "Conditional"),
    (66, 3.75, "Conditional"),
    (69, 3.50, "Conditional"),
    (72, 3.25, "Conditional"),
    (75, 3.00, "Fair"),
    (78, 2.75, "Fair"),
    (80, 2.50, "Average"),
    (82, 2.25, "Average"),
    (85, 2.00, "Good"),
    (88, 1.75, "Good"),
    (91, 1.50, "Very Good"),
    (94, 1.25, "Very Good"),
    (97, 1.00, "Excellent"),
]

DEFAULT_COLUMNS = {"quizzes": 5, "participation": 4, "project": 1, "exam": 1}


def transmute(initial, table=None):
    """Range lookup like VLOOKUP(..., TRUE): last row whose bound <= initial."""
    if initial is None:
        return None, ""
    table = table or DEFAULT_TRANSMUTATION
    result = (None, "")
    for bound, grade, desc in table:
        if initial >= bound:
            result = (grade, desc)
    return result


def component_result(scores, hps_list, weight_pct):
    """scores/hps_list: parallel lists (None = blank score cell).
    Returns dict(total, ps, ws) with None when no scores are entered."""
    entered = [s for s in scores if s is not None]
    hps_total = sum(h for h in hps_list if h is not None) or 0
    if not entered or hps_total <= 0:
        return {"total": None, "ps": None, "ws": None}
    total = sum(entered)
    ps = round(total / hps_total * 50 + 50, 2)
    ws = round(ps * (weight_pct / 100.0), 2)
    return {"total": total, "ps": ps, "ws": ws}


def term_result(scores_by_comp, hps_by_comp, weights_pct, table=None):
    """Compute one term for one student.
    scores_by_comp / hps_by_comp: {component: [values]}
    weights_pct: {component: percent}
    Returns dict with per-component results + initial, grade, descriptor,
    remark. initial is None until every component has at least one score."""
    comps = {}
    for comp in COMPONENTS:
        comps[comp] = component_result(scores_by_comp.get(comp, []),
                                       hps_by_comp.get(comp, []),
                                       weights_pct.get(comp, 0))
    if any(comps[c]["ws"] is None for c in COMPONENTS):
        initial = None
    else:
        initial = round(sum(comps[c]["ws"] for c in COMPONENTS), 2)
    grade, desc = transmute(initial, table)
    remark = "" if initial is None else ("PASSED" if initial >= 75
                                         else "FAILED")
    return {"components": comps, "initial": initial, "grade": grade,
            "descriptor": desc, "remark": remark}


def semestral_result(mid_initial, fin_initial, mid_w=0.5, fin_w=0.5,
                     table=None):
    if mid_initial is None or fin_initial is None:
        return {"initial": None, "grade": None, "descriptor": "",
                "remark": ""}
    initial = round(mid_initial * mid_w + fin_initial * fin_w, 2)
    grade, desc = transmute(initial, table)
    remark = "PASSED" if initial >= 75 else "FAILED"
    return {"initial": initial, "grade": grade, "descriptor": desc,
            "remark": remark}


def validate_weights(weights_pct):
    return abs(sum(weights_pct.get(c, 0) for c in COMPONENTS) - 100) < 0.001
