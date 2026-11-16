"""attendance.py - attendance maths (exact, using fractions - no rounding errors)."""
import math
from decimal import Decimal
from fractions import Fraction


def percentage(attended: int, total: int) -> float:
    return 0.0 if total <= 0 else round(attended / total * 100, 2)


def calculate(total: int, attended: int, required_pct: float = 75.0) -> dict:
    """
    A = attended, T = total, r = required fraction (e.g. 0.75)
      A/T >= r :  max extra absences      = floor(A/r - T)
      A/T <  r :  consecutive classes need = ceil((r*T - A)/(1 - r))
    """
    out = {"ok": False, "error": None, "percentage": 0.0, "status": "", "can_miss": None,
           "need_attend": None, "message": ""}
    try:
        T, A = int(total), int(attended)
        r = Fraction(Decimal(str(required_pct))) / 100
    except Exception:
        out["error"] = "Please enter valid numbers."
        return out

    if T < 0 or A < 0:
        out["error"] = "Numbers cannot be negative."
        return out
    if A > T:
        out["error"] = "Classes attended cannot be more than total classes."
        return out
    if not (0 < r <= 1):
        out["error"] = "Minimum required attendance must be between 1 and 100."
        return out

    out["ok"] = True
    if T == 0:
        out["status"] = "no_data"
        out["message"] = "No classes have been conducted yet, so attendance cannot be calculated."
        return out

    out["percentage"] = round(float(Fraction(A, T) * 100), 2)

    if Fraction(A, T) >= r:
        can_miss = max(0, math.floor(Fraction(A) / r - T))
        out["status"] = "safe"
        out["can_miss"] = can_miss
        out["message"] = (f"You are above the required {required_pct:g}%. You can miss at most "
                          f"{can_miss} more class(es) and stay at or above {required_pct:g}%.")
    else:
        out["status"] = "below"
        if r == 1:
            out["message"] = ("WARNING: Attendance is below 100% and can never return to 100%, "
                              "because missed classes cannot be undone.")
        else:
            need = math.ceil((r * T - A) / (1 - r))
            out["need_attend"] = need
            out["message"] = (f"WARNING: Attendance is below {required_pct:g}%. You must attend the next "
                              f"{need} class(es) in a row (without missing any) to reach {required_pct:g}%.")
    return out
