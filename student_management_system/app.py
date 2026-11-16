"""app.py - main Streamlit app: login page + ERP layout. Run with:  streamlit run app.py"""
import re
from datetime import date, datetime
import pandas as pd
import streamlit as st

import admin
import auth
import attendance as att
import database as db
import storage

st.set_page_config(page_title="Student Management System", page_icon="🎓",
                   layout="wide", initial_sidebar_state="expanded")

PAGES = ["Dashboard", "Student Profile", "Attendance Management",
         "Cloud Document Storage", "Feedback & Updates"]
UNIVERSITY = db.get_secret("UNIVERSITY_NAME", "Indira Gandhi Delhi Technical University for Women")

BASE_CSS = """
<style>
.stApp {background:#f4f5f7;}
h1,h2,h3 {color:#0b2a5b;}
#MainMenu, footer {visibility:hidden;}
[data-testid="stMetric"] {background:#fff;border:1px solid #d9dde3;padding:12px 16px;border-radius:4px;}
div[data-testid="stForm"] {background:#fff;border:1px solid #d9dde3;border-radius:4px;}
.sms-banner {background:#0b2a5b;color:#fff;padding:14px 20px;border-radius:4px;margin-bottom:18px;}
.sms-banner h2 {color:#fff;margin:0;font-size:1.3rem;}
.sms-banner span {font-size:.9rem;opacity:.85;}
.sms-card {background:#fff;border:1px solid #d9dde3;border-left:4px solid #0b2a5b;padding:10px 14px;margin-bottom:8px;border-radius:3px;}
.sms-card small {color:#5f6b7a;}
</style>
"""
SIDEBAR_CSS = """
<style>
[data-testid="stSidebar"] {background:#0b2a5b;}
[data-testid="stSidebar"] * {color:#ffffff !important;}
[data-testid="stSidebar"] .stButton>button {width:100%;justify-content:flex-start;text-align:left;
  background:transparent;border:none;border-radius:0;padding:.65rem 1rem;box-shadow:none;}
[data-testid="stSidebar"] .stButton>button:hover {background:#1d4380;}
[data-testid="stSidebar"] .stButton>button[kind="primary"],
[data-testid="stSidebar"] .stButton>button[data-testid="stBaseButton-primary"] {background:#2a5aa8;}
[data-testid="stSidebarCollapseButton"], [data-testid="collapsedControl"] {display:none;}
</style>
"""
HIDE_SIDEBAR_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"] {display:none;}
</style>
"""


def go(page: str):
    st.session_state["page"] = page


def fmt_date(value) -> str:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d %b %Y")
    except Exception:
        return str(value)


def banner(title: str, subtitle: str = ""):
    st.markdown(f'<div class="sms-banner"><h2>{title}</h2><span>{subtitle}</span></div>',
                unsafe_allow_html=True)


# ----------------------------------------------------------------- LOGIN
def login_page():
    st.markdown(HIDE_SIDEBAR_CSS, unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        st.markdown(f"<h2 style='text-align:center;margin-bottom:0'>🎓 {UNIVERSITY}</h2>"
                    "<h4 style='text-align:center;color:#5f6b7a;margin-top:4px'>Student Management System</h4>",
                    unsafe_allow_html=True)
        tab_student, tab_admin = st.tabs(["Student Login", "Admin Login"])
        with tab_student:
            with st.form("login_form"):
                enrollment = st.text_input("Enrollment Number", max_chars=20)
                password = st.text_input("Password", type="password", max_chars=100)
                submitted = st.form_submit_button("Login")
            if submitted:
                ok, msg = auth.login(enrollment, password, "student")
                if ok:
                    st.rerun()
                else:
                    st.error(msg)
        with tab_admin:
            with st.form("admin_login_form"):
                email = st.text_input("Admin Email", max_chars=100)
                apass = st.text_input("Password", type="password", max_chars=100, key="admin_pw")
                asubmitted = st.form_submit_button("Admin Login")
            if asubmitted:
                ok, msg = auth.login(email, apass, "admin")
                if ok:
                    st.rerun()
                else:
                    st.error(msg)


# ------------------------------------------------------------- DASHBOARD
def overall_attendance(rows) -> float:
    total = sum(r["total_classes"] for r in rows)
    attended = sum(r["attended"] for r in rows)
    return att.percentage(attended, total)


def page_dashboard(student):
    banner(f"Welcome, {student['name']}", "Student Dashboard")
    rows = db.get_attendance()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Enrollment No.", student["enrollment_no"])
    c2.metric("Branch", student["branch"])
    c3.metric("Semester", student["semester"])
    c4.metric("Overall Attendance", f"{overall_attendance(rows)}%" if rows else "N/A")

    st.subheader("Recent Announcements")
    try:
        for a in db.get_announcements(limit=3):
            st.markdown(f'<div class="sms-card"><b>{a["title"]}</b><br>{a["description"]}<br>'
                        f'<small>{fmt_date(a["published_on"])} · {a["category"]}</small></div>',
                        unsafe_allow_html=True)
    except Exception:
        st.warning("Could not load announcements right now.")

    st.subheader("Quick Access")
    cols = st.columns(4)
    for col, name in zip(cols, PAGES[1:]):
        col.button(name, key=f"quick_{name}", on_click=go, args=(name,))


# --------------------------------------------------------------- PROFILE
def page_profile(student):
    banner("Student Profile", "View and update your details")
    st.subheader("Academic Information")
    a1, a2 = st.columns(2)
    a1.text_input("University", student["university"], disabled=True)
    a2.text_input("College", student["college"], disabled=True)
    b1, b2, b3, b4 = st.columns(4)
    b1.text_input("Branch", student["branch"], disabled=True)
    b2.text_input("Semester", str(student["semester"]), disabled=True)
    b3.text_input("Academic Year", student["academic_year"], disabled=True)
    b4.text_input("Admission Year", str(student["admission_year"]), disabled=True)

    st.subheader("Personal Information")
    p1, p2 = st.columns(2)
    p1.text_input("Name", student["name"], disabled=True)
    p2.text_input("Enrollment Number", student["enrollment_no"], disabled=True)
    st.caption("Name, enrollment number and academic details can only be changed by the administration.")

    dob_val = date.fromisoformat(student["date_of_birth"]) if student.get("date_of_birth") else date(2005, 1, 1)
    with st.form("profile_form"):
        email = st.text_input("Email", student.get("email") or "", max_chars=100)
        phone = st.text_input("Phone Number", student.get("phone") or "", max_chars=15)
        dob = st.date_input("Date of Birth", dob_val, min_value=date(1970, 1, 1), max_value=date.today())
        address = st.text_area("Address", student.get("address") or "", max_chars=300)
        saved = st.form_submit_button("Save Changes")
    if saved:
        email, phone, address = email.strip(), phone.strip(), address.strip()
        if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            st.error("Enter a valid email address.")
        elif phone and not re.match(r"^[0-9+\-\s]{7,15}$", phone):
            st.error("Enter a valid phone number (7-15 digits, + and - allowed).")
        else:
            try:
                db.update_student({"email": email or None, "phone": phone or None,
                                   "date_of_birth": dob.isoformat(), "address": address or None})
                st.success("Profile updated.")
            except Exception as exc:
                st.error(f"Could not update profile: {exc}")


# ------------------------------------------------------------ ATTENDANCE
def show_result(res: dict):
    if not res["ok"]:
        st.error(res["error"])
        return
    if res["status"] == "no_data":
        st.info(res["message"])
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("Current Attendance", f"{res['percentage']}%")
    if res["status"] == "safe":
        m2.metric("Can Still Miss", res["can_miss"])
        m3.metric("Must Attend in a Row", 0)
        st.success(res["message"])
    else:
        m2.metric("Can Still Miss", 0)
        m3.metric("Must Attend in a Row", res["need_attend"] if res["need_attend"] is not None else "Not possible")
        st.warning(res["message"])


def page_attendance(student):
    banner("Attendance Management", "Subject-wise attendance and calculator")
    try:
        rows = db.get_attendance()
    except Exception as exc:
        st.error(f"Could not load attendance: {exc}")
        rows = []

    if rows:
        table = []
        for r in rows:
            pct = att.percentage(r["attended"], r["total_classes"])
            table.append({
                "Subject": r["subject"], "Total Classes": r["total_classes"],
                "Attended": r["attended"], "Missed": r["total_classes"] - r["attended"],
                "Attendance %": f"{pct}%",
                "Status": "Below 75%" if r["total_classes"] and pct < 75 else "OK",
            })
        st.table(pd.DataFrame(table).set_index("Subject"))
        st.metric("Overall Attendance", f"{overall_attendance(rows)}%")
    else:
        st.info("No attendance records have been added for you yet.")

    st.subheader("ATTENDANCE CALCULATOR")
    options = ["Enter manually"] + [r["subject"] for r in rows]
    choice = st.selectbox("Calculate for", options)
    default_t, default_a = 0, 0
    if choice != "Enter manually":
        sel = next(r for r in rows if r["subject"] == choice)
        default_t, default_a = sel["total_classes"], sel["attended"]
    c1, c2, c3 = st.columns(3)
    total = c1.number_input("Total classes conducted", min_value=0, max_value=5000, value=default_t,
                            step=1, key=f"calc_t_{choice}")
    attended = c2.number_input("Classes attended", min_value=0, max_value=5000, value=default_a,
                               step=1, key=f"calc_a_{choice}")
    required = c3.number_input("Minimum required attendance %", min_value=1.0, max_value=100.0,
                               value=75.0, step=1.0, key="calc_req")
    show_result(att.calculate(total, attended, required))


# ------------------------------------------------------------- DOCUMENTS
def page_documents(student):
    banner("Cloud Document Storage", "Your private documents, stored securely in the cloud")
    counter = st.session_state.setdefault("upload_counter", 0)

    st.subheader("Upload Document")
    u1, u2 = st.columns([1, 2])
    category = u1.selectbox("Category", storage.CATEGORIES, key="upload_cat")
    file = u2.file_uploader("Choose a file (max 10 MB)", key=f"uploader_{counter}",
                            type=sorted(storage.ALLOWED.keys()))
    if st.button("Upload"):
        ok, msg = storage.upload_document(file, category)
        if ok:
            st.session_state["upload_counter"] = counter + 1
            st.session_state["flash"] = msg
            st.rerun()
        else:
            st.error(msg)
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

    st.subheader("My Documents")
    f1, f2 = st.columns([2, 1])
    search = f1.text_input("Search by file name")
    cat_filter = f2.selectbox("Filter by category", ["All"] + storage.CATEGORIES)
    try:
        docs = storage.list_documents(search, cat_filter)
    except Exception as exc:
        st.error(f"Could not load documents: {exc}")
        return
    if not docs:
        st.info("No documents found.")
        return

    head = st.columns([3, 2, 1, 1, 2, 2, 1])
    for col, title in zip(head, ["Name", "Category", "Type", "Size", "Uploaded", "Download", "Delete"]):
        col.markdown(f"**{title}**")
    for d in docs:
        c = st.columns([3, 2, 1, 1, 2, 2, 1])
        c[0].write(d["file_name"])
        c[1].write(d["category"])
        c[2].write(d["file_type"])
        c[3].write(storage.human_size(d["file_size"]))
        c[4].write(fmt_date(d["uploaded_at"]))
        url_key = f"url_{d['id']}"
        if url_key in st.session_state:
            c[5].link_button("Open file", st.session_state[url_key])
        elif c[5].button("Get link", key=f"get_{d['id']}"):
            url = storage.get_download_url(d["storage_path"])
            if url:
                st.session_state[url_key] = url
                st.rerun()
            else:
                st.error("Could not create a download link.")
        if c[6].button("🗑", key=f"del_{d['id']}", help="Delete this document"):
            ok, msg = storage.delete_document(d)
            st.session_state.pop(url_key, None)
            if ok:
                st.session_state["flash"] = msg
                st.rerun()
            else:
                st.error(msg)
    st.caption("Download links are private and expire after 5 minutes. Click 'Get link' again for a new one.")


# ---------------------------------------------------- FEEDBACK & UPDATES
FEEDBACK_CATEGORIES = ["Faculty", "Academics", "Infrastructure", "Administration", "Other"]


def page_feedback(student):
    banner("Feedback & Updates", "Share feedback and read college announcements")
    tab1, tab2 = st.tabs(["Feedback", "College Updates"])

    with tab1:
        if "fb_flash" in st.session_state:
            st.success(st.session_state.pop("fb_flash"))
        fb_ver = st.session_state.setdefault("fb_ver", 0)
        with st.form(f"feedback_form_{fb_ver}"):
            category = st.selectbox("Category", FEEDBACK_CATEGORIES)
            message = st.text_area("Your feedback (10 to 1000 characters)", max_chars=1000)
            sent = st.form_submit_button("Submit Feedback")
        if sent:
            message = message.strip()
            if len(message) < 10:
                st.error("Please write at least 10 characters.")
            else:
                try:
                    db.add_feedback(category, message)
                    st.session_state["fb_ver"] = fb_ver + 1   # fresh empty form
                    st.session_state["fb_flash"] = "Feedback submitted. Status: Submitted"
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not submit feedback: {exc}")
        st.subheader("My Submissions")
        try:
            items = db.get_feedback()
        except Exception as exc:
            st.error(f"Could not load feedback: {exc}")
            items = []
        if items:
            st.table(pd.DataFrame([{"Date": fmt_date(i["created_at"]), "Category": i["category"],
                                    "Feedback": i["message"], "Status": i["status"]}
                                   for i in items]).set_index("Date"))
        else:
            st.info("You have not submitted any feedback yet.")

    with tab2:
        st.caption("These are sample announcements for demonstration only.")
        try:
            news = db.get_announcements()
        except Exception as exc:
            st.error(f"Could not load announcements: {exc}")
            news = []
        cats = ["All"] + sorted({n["category"] for n in news})
        pick = st.selectbox("Category", cats, key="news_cat")
        for n in news:
            if pick == "All" or n["category"] == pick:
                st.markdown(f'<div class="sms-card"><b>{n["title"]}</b><br>{n["description"]}<br>'
                            f'<small>{fmt_date(n["published_on"])} · {n["category"]}</small></div>',
                            unsafe_allow_html=True)


# ------------------------------------------------------------------ MAIN
PAGE_FUNCS = {
    "Dashboard": page_dashboard, "Student Profile": page_profile,
    "Attendance Management": page_attendance,
    "Cloud Document Storage": page_documents, "Feedback & Updates": page_feedback,
}


def main():
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    if not auth.is_logged_in():
        login_page()
        return

    st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    role = st.session_state["role"]
    if role == "admin":
        pages, funcs, default = list(admin.ADMIN_PAGES), admin.ADMIN_PAGES, "Admin Dashboard"
        who = f"### 🎓 SMS Admin\n**{st.session_state.get('display_name', 'Administrator')}**  \nAdministrator"
    else:
        student = st.session_state["student"]
        pages, funcs, default = PAGES, PAGE_FUNCS, "Dashboard"
        who = f"### 🎓 SMS\n**{student['name']}**  \n{student['enrollment_no']}"

    current = st.session_state.get("page", default)
    if current not in funcs:          # e.g. a student can never land on an admin page
        current = default
        st.session_state["page"] = default
    with st.sidebar:
        st.markdown(who)
        st.markdown("---")
        for name in pages:
            st.button(name, key=f"nav_{name}", on_click=go, args=(name,),
                      type="primary" if name == current else "secondary")
        st.markdown("---")
        st.button("Logout", key="nav_logout", on_click=auth.logout)

    try:
        if role == "admin":
            funcs[current]()
        else:
            funcs[current](student)
    except Exception as exc:
        st.error(f"Something went wrong: {exc}")


main()