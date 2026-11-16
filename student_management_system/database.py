"""database.py - all reads/writes to Supabase tables (always as the logged-in student)."""
import os
import streamlit as st


def get_secret(name, default=None):
    """Read a value from Streamlit secrets, or from environment variables."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def client():
    return st.session_state["client"]


def user_id():
    return st.session_state["user_id"]


def get_student():
    rows = client().table("students").select("*").eq("id", user_id()).limit(1).execute().data
    return rows[0] if rows else None


def refresh_student():
    student = get_student()
    if student:
        st.session_state["student"] = student
    return student


def update_student(fields: dict):
    allowed = {"email", "phone", "date_of_birth", "address"}
    clean = {k: v for k, v in fields.items() if k in allowed}
    client().table("students").update(clean).eq("id", user_id()).execute()
    refresh_student()


def get_attendance():
    return (client().table("attendance").select("subject,total_classes,attended")
            .eq("student_id", user_id()).order("subject").execute().data)


def get_announcements(limit=50):
    return (client().table("announcements").select("*")
            .order("published_on", desc=True).limit(limit).execute().data)


def add_feedback(category: str, message: str):
    client().table("feedback").insert({
        "student_id": user_id(), "category": category,
        "message": message, "status": "Submitted",
    }).execute()


def get_feedback():
    return (client().table("feedback").select("category,message,status,created_at")
            .eq("student_id", user_id()).order("created_at", desc=True).execute().data)


# ======================================================================
# ADMIN-ONLY FUNCTIONS
# The check below is only a safety net. The REAL protection is Row Level
# Security in the database (migration_roles.sql): even if someone bypassed
# this check, Supabase would reject every admin operation for a student.
# ======================================================================
def require_admin():
    if st.session_state.get("role") != "admin":
        raise PermissionError("Administrator access required.")


def admin_count_students() -> int:
    require_admin()
    res = client().table("students").select("id", count="exact").limit(1).execute()
    return res.count or 0


def admin_list_students():
    require_admin()
    return (client().table("students")
            .select("id,enrollment_no,name,email,phone,date_of_birth,address,university,college,"
                    "branch,semester,academic_year,admission_year")
            .order("enrollment_no").execute().data)


def admin_get_attendance(student_id: str):
    require_admin()
    return (client().table("attendance").select("subject,total_classes,attended")
            .eq("student_id", student_id).order("subject").execute().data)


def admin_save_attendance(student_id: str, rows: list):
    """rows = [{'subject':..., 'total_classes':int, 'attended':int}, ...] (insert or update)."""
    require_admin()
    payload = [{"student_id": student_id, "subject": r["subject"],
                "total_classes": int(r["total_classes"]), "attended": int(r["attended"])} for r in rows]
    if payload:
        client().table("attendance").upsert(payload, on_conflict="student_id,subject").execute()


def admin_delete_attendance(student_id: str, subject: str):
    require_admin()
    client().table("attendance").delete().eq("student_id", student_id).eq("subject", subject).execute()


def admin_list_announcements():
    require_admin()
    return (client().table("announcements").select("*")
            .order("published_on", desc=True).execute().data)


def admin_add_announcement(title: str, description: str, category: str, published_on: str):
    require_admin()
    client().table("announcements").insert({
        "title": title, "description": description, "category": category,
        "published_on": published_on}).execute()


def admin_update_announcement(ann_id: str, title: str, description: str, category: str, published_on: str):
    require_admin()
    client().table("announcements").update({
        "title": title, "description": description, "category": category,
        "published_on": published_on}).eq("id", ann_id).execute()


def admin_delete_announcement(ann_id: str):
    require_admin()
    client().table("announcements").delete().eq("id", ann_id).execute()


def admin_list_feedback():
    require_admin()
    return (client().table("feedback")
            .select("id,category,message,status,created_at,students(name,enrollment_no)")
            .order("created_at", desc=True).execute().data)


def admin_update_feedback_status(feedback_id: str, status: str):
    require_admin()
    if status not in ("Submitted", "Under Review", "Resolved"):
        raise ValueError("Invalid status.")
    client().table("feedback").update({"status": status}).eq("id", feedback_id).execute()


def admin_delete_feedback(feedback_id: str):
    require_admin()
    client().table("feedback").delete().eq("id", feedback_id).execute()