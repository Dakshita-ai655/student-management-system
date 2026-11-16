"""auth.py - login / logout using Supabase Authentication, with Student and Admin roles.

The role is stored in the `profiles` table and can NOT be changed from the app
(see migration_roles.sql). Nobody can register as admin: admin accounts are
created only with create_admin.py (service-role key, run on your own computer).
"""
import re
import time
import streamlit as st
from supabase import create_client
import database as db

EMAIL_DOMAIN = "students.sms-demo.edu"   # must match create_demo_students.py
ENROLLMENT_RE = re.compile(r"^[A-Za-z0-9]{4,20}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_ATTEMPTS = 5
LOCK_SECONDS = 60
BAD_LOGIN = "Invalid credentials."


def enrollment_to_email(enrollment: str) -> str:
    return f"{enrollment.strip().lower()}@{EMAIL_DOMAIN}"


def _new_client():
    url = db.get_secret("SUPABASE_URL")
    key = db.get_secret("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("The app is not configured yet: SUPABASE_URL / SUPABASE_ANON_KEY are missing.")
    return create_client(url, key)


def _fail():
    fails = st.session_state.get("fail_count", 0) + 1
    st.session_state["fail_count"] = fails
    if fails >= MAX_ATTEMPTS:
        st.session_state["locked_until"] = time.time() + LOCK_SECONDS
        st.session_state["fail_count"] = 0


def _sign_out_quietly(sb):
    try:
        sb.auth.sign_out()
    except Exception:
        pass


def login(identifier: str, password: str, mode: str = "student"):
    """mode = 'student' (enrollment number) or 'admin' (email). Returns (ok, error_message)."""
    locked_until = st.session_state.get("locked_until", 0)
    if time.time() < locked_until:
        return False, f"Too many failed attempts. Try again in {int(locked_until - time.time())} seconds."

    identifier = (identifier or "").strip()
    if mode == "admin":
        if not EMAIL_RE.match(identifier):
            return False, "Enter a valid admin email address."
        email = identifier.lower()
    else:
        if not ENROLLMENT_RE.match(identifier):
            return False, "Enter a valid enrollment number (letters and digits only)."
        email = enrollment_to_email(identifier)
    if not password:
        return False, "Enter your password."

    try:
        sb = _new_client()
    except RuntimeError as exc:
        return False, str(exc)

    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        user = res.user
        prof = sb.table("profiles").select("role,display_name").eq("id", user.id).limit(1).execute().data
    except Exception:
        _fail()
        return False, BAD_LOGIN

    role = prof[0]["role"] if prof else None
    # The login form must match the account's role (a student cannot use the Admin form, and vice versa)
    if role != mode:
        _sign_out_quietly(sb)
        _fail()
        return False, BAD_LOGIN

    student = None
    if role == "student":
        rows = sb.table("students").select("*").eq("id", user.id).limit(1).execute().data
        if not rows:
            _sign_out_quietly(sb)
            return False, "Your login exists but no student record was found. Contact the administrator."
        student = rows[0]

    st.session_state["fail_count"] = 0
    st.session_state["client"] = sb
    st.session_state["user_id"] = user.id
    st.session_state["role"] = role
    st.session_state["display_name"] = (student["name"] if student else (prof[0].get("display_name") or "Administrator"))
    if student:
        st.session_state["student"] = student
    st.session_state["page"] = "Dashboard" if role == "student" else "Admin Dashboard"
    return True, ""


def is_logged_in() -> bool:
    sb = st.session_state.get("client")
    role = st.session_state.get("role")
    if sb is None or role not in ("student", "admin"):
        return False
    if role == "student" and "student" not in st.session_state:
        return False
    try:
        if sb.auth.get_session() is None:   # also refreshes an expiring token
            logout()
            return False
    except Exception:
        logout()
        return False
    return True


def logout():
    sb = st.session_state.get("client")
    if sb is not None:
        _sign_out_quietly(sb)
    st.session_state.clear()
