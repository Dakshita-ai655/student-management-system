"""admin.py - Admin pages. Only reachable when the logged-in profile role is 'admin'.
Every database call goes through database.admin_* (which re-checks the role) AND is
enforced again by Row Level Security in Supabase."""
from datetime import date, datetime
import pandas as pd
import streamlit as st
import database as db

FEEDBACK_STATUSES = ["Submitted", "Under Review", "Resolved"]
ANN_CATEGORIES = ["General", "Examination", "Academics", "Events", "Administration"]


def _banner(title, subtitle=""):
    st.markdown(f'<div class="sms-banner"><h2>{title}</h2><span>{subtitle}</span></div>', unsafe_allow_html=True)


def _fmt(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d %b %Y")
    except Exception:
        return str(value)


def _go(page):
    st.session_state["page"] = page


def _flash():
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))


def _student_label(s):
    return f"{s['enrollment_no']} - {s['name']}"


# ------------------------------------------------------------ DASHBOARD
def page_admin_dashboard():
    _banner(f"Welcome, {st.session_state.get('display_name', 'Administrator')}", "Admin Dashboard")
    try:
        total = db.admin_count_students()
        feedback = db.admin_list_feedback()
        announcements = db.admin_list_announcements()
    except Exception as exc:
        st.error(f"Could not load dashboard data: {exc}")
        return
    pending = sum(1 for f in feedback if f["status"] != "Resolved")
    c1, c2, c3 = st.columns(3)
    c1.metric("Registered students", total)
    c2.metric("Open feedback", pending)
    c3.metric("Announcements", len(announcements))

    st.subheader("Latest feedback")
    if not feedback:
        st.info("No feedback has been submitted yet.")
    for f in feedback[:3]:
        who = f.get("students") or {}
        st.markdown(f'<div class="sms-card"><b>{f["category"]}</b> · {f["status"]}<br>{f["message"][:160]}<br>'
                    f'<small>{who.get("name", "?")} ({who.get("enrollment_no", "?")}) · {_fmt(f["created_at"])}</small></div>',
                    unsafe_allow_html=True)

    st.subheader("Quick Access")
    cols = st.columns(4)
    for col, name in zip(cols, ["Student Records", "Manage Attendance", "Manage Announcements", "Student Feedback"]):
        col.button(name, key=f"aquick_{name}", on_click=_go, args=(name,))


# ------------------------------------------------------- STUDENT RECORDS
def page_student_records():
    _banner("Student Records", "View registered students (read-only)")
    try:
        students = db.admin_list_students()
    except Exception as exc:
        st.error(f"Could not load students: {exc}")
        return
    if not students:
        st.info("No students registered yet.")
        return
    search = st.text_input("Search by name or enrollment number").strip().lower()
    shown = [s for s in students if search in s["name"].lower() or search in s["enrollment_no"].lower()]
    df = pd.DataFrame(shown)
    if df.empty:
        st.info("No matching students.")
        return
    cols = ["enrollment_no", "name", "branch", "semester", "academic_year", "email", "phone"]
    st.dataframe(df[cols].rename(columns=lambda c: c.replace("_", " ").title()), hide_index=True)

    st.subheader("Student details")
    pick = st.selectbox("Select a student", shown, format_func=_student_label)
    d1, d2 = st.columns(2)
    d1.write(f"**Name:** {pick['name']}  \n**Enrollment:** {pick['enrollment_no']}  \n**Email:** {pick['email'] or '-'}  \n"
             f"**Phone:** {pick['phone'] or '-'}  \n**Date of birth:** {pick['date_of_birth'] or '-'}  \n**Address:** {pick['address'] or '-'}")
    d2.write(f"**University:** {pick['university']}  \n**College:** {pick['college']}  \n**Branch:** {pick['branch']}  \n"
             f"**Semester:** {pick['semester']}  \n**Academic year:** {pick['academic_year']}  \n**Admission year:** {pick['admission_year']}")
    rows = db.admin_get_attendance(pick["id"])
    if rows:
        att = pd.DataFrame(rows)
        att["Attendance %"] = (att["attended"] / att["total_classes"].where(att["total_classes"] > 0) * 100).round(1)
        st.table(att.rename(columns={"subject": "Subject", "total_classes": "Total", "attended": "Attended"}).set_index("Subject"))
    else:
        st.caption("No attendance records for this student.")


# ------------------------------------------------------------ ATTENDANCE
def page_manage_attendance():
    _banner("Manage Attendance", "Official attendance records - only admins can change these")
    _flash()
    try:
        students = db.admin_list_students()
    except Exception as exc:
        st.error(f"Could not load students: {exc}")
        return
    if not students:
        st.info("No students registered yet.")
        return
    pick = st.selectbox("Student", students, format_func=_student_label)
    sid = pick["id"]
    ver = st.session_state.setdefault("att_ver", 0)
    try:
        rows = db.admin_get_attendance(sid)
    except Exception as exc:
        st.error(f"Could not load attendance: {exc}")
        return

    st.subheader(f"Attendance for {pick['name']}")
    if rows:
        df = pd.DataFrame(rows)
        edited = st.data_editor(
            df, hide_index=True, disabled=["subject"], num_rows="fixed", key=f"att_{sid}_{ver}",
            column_config={
                "subject": "Subject",
                "total_classes": st.column_config.NumberColumn("Total classes", min_value=0, max_value=5000, step=1),
                "attended": st.column_config.NumberColumn("Attended", min_value=0, max_value=5000, step=1),
            })
        if st.button("Save attendance changes"):
            problems = [r["subject"] for _, r in edited.iterrows()
                        if pd.isna(r["total_classes"]) or pd.isna(r["attended"]) or int(r["attended"]) > int(r["total_classes"])]
            if problems:
                st.error("Attended classes cannot be more than total classes: " + ", ".join(problems))
            else:
                changed = [r for (_, r), (_, o) in zip(edited.iterrows(), df.iterrows())
                           if int(r["total_classes"]) != int(o["total_classes"]) or int(r["attended"]) != int(o["attended"])]
                if not changed:
                    st.info("No changes to save.")
                else:
                    try:
                        db.admin_save_attendance(sid, [{"subject": r["subject"], "total_classes": r["total_classes"],
                                                        "attended": r["attended"]} for r in changed])
                        st.session_state["att_ver"] = ver + 1
                        st.session_state["flash"] = f"Updated {len(changed)} subject(s)."
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not save: {exc}")
    else:
        st.info("This student has no subjects yet. Add one below.")

    st.subheader("Add a subject")
    with st.form(f"add_subject_{sid}_{ver}"):
        name = st.text_input("Subject name", max_chars=60)
        a1, a2 = st.columns(2)
        total = a1.number_input("Total classes", min_value=0, max_value=5000, value=0, step=1)
        attended = a2.number_input("Classes attended", min_value=0, max_value=5000, value=0, step=1)
        add = st.form_submit_button("Add subject")
    if add:
        name = name.strip()
        if len(name) < 2:
            st.error("Enter a subject name.")
        elif attended > total:
            st.error("Attended classes cannot be more than total classes.")
        elif any(r["subject"].lower() == name.lower() for r in rows):
            st.error("That subject already exists. Edit it in the table above.")
        else:
            try:
                db.admin_save_attendance(sid, [{"subject": name, "total_classes": total, "attended": attended}])
                st.session_state["att_ver"] = ver + 1
                st.session_state["flash"] = f"Subject '{name}' added."
                st.rerun()
            except Exception as exc:
                st.error(f"Could not add subject: {exc}")

    if rows:
        st.subheader("Remove a subject")
        r1, r2 = st.columns([2, 1])
        subject = r1.selectbox("Subject", [r["subject"] for r in rows], key=f"del_sub_{sid}_{ver}")
        sure = r2.checkbox("I am sure", key=f"del_ok_{sid}_{ver}")
        if st.button("Delete subject"):
            if not sure:
                st.error("Tick 'I am sure' first.")
            else:
                try:
                    db.admin_delete_attendance(sid, subject)
                    st.session_state["att_ver"] = ver + 1
                    st.session_state["flash"] = f"Subject '{subject}' removed."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not delete: {exc}")


# --------------------------------------------------------- ANNOUNCEMENTS
def _validate_ann(title, description):
    if not (3 <= len(title.strip()) <= 150):
        return "Title must be 3 to 150 characters."
    if not (5 <= len(description.strip()) <= 1500):
        return "Description must be 5 to 1500 characters."
    return None


def page_manage_announcements():
    _banner("Manage Announcements", "Create, edit and delete college updates")
    _flash()
    ann_ver = st.session_state.setdefault("ann_ver", 0)
    with st.form(f"new_ann_{ann_ver}"):
        st.subheader("New announcement")
        title = st.text_input("Title", max_chars=150)
        desc = st.text_area("Description", max_chars=1500)
        c1, c2 = st.columns(2)
        cat = c1.selectbox("Category", ANN_CATEGORIES)
        when = c2.date_input("Date", date.today())
        create = st.form_submit_button("Publish announcement")
    if create:
        err = _validate_ann(title, desc)
        if err:
            st.error(err)
        else:
            try:
                db.admin_add_announcement(title.strip(), desc.strip(), cat, when.isoformat())
                st.session_state["ann_ver"] = ann_ver + 1
                st.session_state["flash"] = "Announcement published."
                st.rerun()
            except Exception as exc:
                st.error(f"Could not publish: {exc}")

    st.subheader("Existing announcements")
    try:
        items = db.admin_list_announcements()
    except Exception as exc:
        st.error(f"Could not load announcements: {exc}")
        return
    if not items:
        st.info("No announcements yet.")
    for a in items:
        with st.expander(f"{a['title']}  ·  {_fmt(a['published_on'])}  ·  {a['category']}"):
            with st.form(f"edit_{a['id']}"):
                t = st.text_input("Title", a["title"], max_chars=150)
                d = st.text_area("Description", a["description"], max_chars=1500)
                e1, e2 = st.columns(2)
                cats = ANN_CATEGORIES if a["category"] in ANN_CATEGORIES else ANN_CATEGORIES + [a["category"]]
                c = e1.selectbox("Category", cats, index=cats.index(a["category"]))
                w = e2.date_input("Date", date.fromisoformat(str(a["published_on"])))
                save = st.form_submit_button("Save changes")
            if save:
                err = _validate_ann(t, d)
                if err:
                    st.error(err)
                else:
                    try:
                        db.admin_update_announcement(a["id"], t.strip(), d.strip(), c, w.isoformat())
                        st.session_state["flash"] = "Announcement updated."
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not update: {exc}")
            k1, k2 = st.columns([1, 3])
            sure = k2.checkbox("I am sure I want to delete this", key=f"sure_{a['id']}")
            if k1.button("Delete", key=f"del_{a['id']}"):
                if not sure:
                    st.error("Tick the confirmation box first.")
                else:
                    try:
                        db.admin_delete_announcement(a["id"])
                        st.session_state["flash"] = "Announcement deleted."
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not delete: {exc}")


# -------------------------------------------------------------- FEEDBACK
def page_admin_feedback():
    _banner("Student Feedback", "Review feedback and update its status")
    _flash()
    try:
        items = db.admin_list_feedback()
    except Exception as exc:
        st.error(f"Could not load feedback: {exc}")
        return
    pick = st.selectbox("Show", ["All"] + FEEDBACK_STATUSES)
    shown = [f for f in items if pick == "All" or f["status"] == pick]
    if not shown:
        st.info("No feedback to show.")
    for f in shown:
        who = f.get("students") or {}
        with st.container(border=True):
            st.markdown(f"**{f['category']}** · {who.get('name', '?')} ({who.get('enrollment_no', '?')}) · {_fmt(f['created_at'])}")
            st.write(f["message"])
            c1, c2 = st.columns([2, 1])
            new = c1.selectbox("Status", FEEDBACK_STATUSES, index=FEEDBACK_STATUSES.index(f["status"]),
                               key=f"st_{f['id']}")
            d1, d2 = st.columns([2, 1])
            sure = d1.checkbox("I am sure I want to delete this feedback", key=f"sure_fb_{f['id']}")
            if d2.button("Delete feedback", key=f"delfb_{f['id']}"):
                if not sure:
                    st.error("Tick the confirmation box first.")
                else:
                    try:
                        db.admin_delete_feedback(f["id"])
                        st.session_state["flash"] = "Feedback deleted."
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not delete: {exc}")
            if c2.button("Update status", key=f"upd_{f['id']}"):
                if new == f["status"]:
                    st.info("Status is already " + new + ".")
                else:
                    try:
                        db.admin_update_feedback_status(f["id"], new)
                        st.session_state["flash"] = f"Feedback marked '{new}'."
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not update: {exc}")


ADMIN_PAGES = {
    "Admin Dashboard": page_admin_dashboard,
    "Student Records": page_student_records,
    "Manage Attendance": page_manage_attendance,
    "Manage Announcements": page_manage_announcements,
    "Student Feedback": page_admin_feedback,
}