"""
test_rls.py - checks that security is enforced by the DATABASE, not just hidden buttons.
It logs in as a real student, a real admin, and an anonymous visitor, and tries forbidden actions.

Run on your computer after setup:   python test_rls.py
Needs: SUPABASE_URL, the ANON key (not service-role), one demo student login, one admin login.
All temporary changes it makes are undone.
"""
import getpass
import os
from supabase import create_client

EMAIL_DOMAIN = "students.sms-demo.edu"
results = []


def check(label, passed):
    results.append(passed)
    print(("  PASS  " if passed else "  FAIL  ") + label)


def blocked(fn):
    """True if the action raised an error OR affected no rows (both mean 'not allowed')."""
    try:
        res = fn()
        return not getattr(res, "data", None)
    except Exception:
        return True


def allowed(fn):
    try:
        return bool(fn().data)
    except Exception:
        return False


def main():
    url = os.environ.get("SUPABASE_URL") or input("Supabase URL: ").strip()
    anon = os.environ.get("SUPABASE_ANON_KEY") or input("Supabase ANON key: ").strip()
    enrollment = input("Demo student enrollment number [00101012024]: ").strip() or "00101012024"
    spw = getpass.getpass("Demo student password: ")
    aemail = input("Admin email: ").strip()
    apw = getpass.getpass("Admin password: ")

    stu, adm, anon_c = create_client(url, anon), create_client(url, anon), create_client(url, anon)
    sid = stu.auth.sign_in_with_password({"email": f"{enrollment.lower()}@{EMAIL_DOMAIN}", "password": spw}).user.id
    adm.auth.sign_in_with_password({"email": aemail, "password": apw})
    print("\nLogged in as student and admin.\n")

    att = adm.table("attendance").select("*").eq("student_id", sid).limit(1).execute().data
    fb = adm.table("feedback").select("*").limit(1).execute().data

    print("ANONYMOUS visitor")
    check("cannot read students", blocked(lambda: anon_c.table("students").select("*").execute()))
    check("cannot read announcements", blocked(lambda: anon_c.table("announcements").select("*").execute()))

    print("STUDENT")
    check("sees only own student row", len(stu.table("students").select("id").execute().data) == 1)
    check("sees only own profile", len(stu.table("profiles").select("id").execute().data) == 1)
    check("cannot promote self to admin",
          blocked(lambda: stu.table("profiles").update({"role": "admin"}).eq("id", sid).execute())
          and stu.table("profiles").select("role").eq("id", sid).execute().data[0]["role"] == "student")
    check("cannot create an admin profile",
          blocked(lambda: stu.table("profiles").insert({"id": sid, "role": "admin"}).execute()))
    check("cannot change locked student fields (name)",
          blocked(lambda: stu.table("students").update({"name": "Hacked"}).eq("id", sid).execute()))
    check("cannot insert attendance",
          blocked(lambda: stu.table("attendance").insert(
              {"student_id": sid, "subject": "HACK", "total_classes": 1, "attended": 1}).execute()))
    if att:
        a = att[0]
        check("cannot update attendance",
              blocked(lambda: stu.table("attendance").update({"attended": a["total_classes"]})
                      .eq("id", a["id"]).execute())
              and adm.table("attendance").select("attended").eq("id", a["id"]).execute().data[0]["attended"] == a["attended"])
        check("cannot delete attendance",
              blocked(lambda: stu.table("attendance").delete().eq("id", a["id"]).execute())
              and len(adm.table("attendance").select("id").eq("id", a["id"]).execute().data) == 1)
    check("cannot create announcements",
          blocked(lambda: stu.table("announcements").insert(
              {"title": "hack", "description": "hack hack", "category": "General"}).execute()))
    if fb:
        f = fb[0]
        check("cannot change feedback status",
              blocked(lambda: stu.table("feedback").update({"status": "Resolved"}).eq("id", f["id"]).execute())
              and adm.table("feedback").select("status").eq("id", f["id"]).execute().data[0]["status"] == f["status"])

    print("ADMIN")
    check("can see all students", len(adm.table("students").select("id").execute().data) >= 1)
    check("cannot see students' documents", len(adm.table("documents").select("id").execute().data) == 0)
    check("cannot edit own profile role",
          blocked(lambda: adm.table("profiles").update({"role": "student"}).neq("id", "0").execute()))
    if att:
        a = att[0]
        ok = allowed(lambda: adm.table("attendance").update({"attended": a["attended"]}).eq("id", a["id"]).execute())
        check("can update attendance", ok)
    new = adm.table("announcements").insert(
        {"title": "RLS test", "description": "temporary test row", "category": "General"}).execute().data
    check("can create announcement", bool(new))
    if new:
        nid = new[0]["id"]
        check("can edit announcement",
              allowed(lambda: adm.table("announcements").update({"title": "RLS test 2"}).eq("id", nid).execute()))
        check("can delete announcement", allowed(lambda: adm.table("announcements").delete().eq("id", nid).execute()))
    if fb:
        f = fb[0]
        other = "Under Review" if f["status"] != "Under Review" else "Resolved"
        check("can change feedback status",
              allowed(lambda: adm.table("feedback").update({"status": other}).eq("id", f["id"]).execute()))
        adm.table("feedback").update({"status": f["status"]}).eq("id", f["id"]).execute()   # restore
        check("cannot edit feedback text",
              blocked(lambda: adm.table("feedback").update({"message": "edited by admin"}).eq("id", f["id"]).execute()))

    print(f"\n{sum(results)} of {len(results)} checks passed.")
    if not all(results):
        raise SystemExit("SOME CHECKS FAILED - do not deploy until they pass.")
    print("All security checks passed.")


if __name__ == "__main__":
    main()
