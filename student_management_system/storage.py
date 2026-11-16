"""storage.py - private cloud document storage (Supabase Storage + documents table)."""
import re
import uuid
import streamlit as st
import database as db

BUCKET = "documents"
CATEGORIES = ["Academic Certificates", "Internship Certificates", "Resume",
              "Assignments", "Identity Documents", "Other Documents"]
ALLOWED = {"pdf": "application/pdf", "png": "image/png", "jpg": "image/jpeg",
           "jpeg": "image/jpeg", "doc": "application/msword",
           "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           "txt": "text/plain", "zip": "application/zip"}
MAX_BYTES = 10 * 1024 * 1024


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def upload_document(uploaded_file, category: str):
    """Returns (True, message) or (False, error)."""
    if category not in CATEGORIES:
        return False, "Choose a valid category."
    if uploaded_file is None:
        return False, "Choose a file first."
    name = uploaded_file.name
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        return False, f"File type .{ext or '?'} is not allowed. Allowed: {', '.join(sorted(ALLOWED))}."
    data = uploaded_file.getvalue()
    if len(data) == 0:
        return False, "The file is empty."
    if len(data) > MAX_BYTES:
        return False, "File is too large. Maximum size is 10 MB."

    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[-100:]
    path = f"{db.user_id()}/{uuid.uuid4().hex}_{safe}"
    sb = db.client()
    try:
        sb.storage.from_(BUCKET).upload(path, data, {"content-type": ALLOWED[ext]})
    except Exception as exc:
        return False, f"Upload failed: {exc}"
    try:
        sb.table("documents").insert({
            "student_id": db.user_id(), "category": category, "file_name": name,
            "file_type": ext.upper(), "file_size": len(data), "storage_path": path,
        }).execute()
    except Exception as exc:
        try:   # do not leave an orphan file in the cloud
            sb.storage.from_(BUCKET).remove([path])
        except Exception:
            pass
        return False, f"Could not save document details: {exc}"
    return True, f"'{name}' uploaded successfully."


def list_documents(search: str = "", category: str = "All"):
    rows = (db.client().table("documents").select("*").eq("student_id", db.user_id())
            .order("uploaded_at", desc=True).execute().data)
    if category != "All":
        rows = [r for r in rows if r["category"] == category]
    if search.strip():
        s = search.strip().lower()
        rows = [r for r in rows if s in r["file_name"].lower()]
    return rows


def get_download_url(storage_path: str, seconds: int = 300):
    """Short-lived authorised link (expires after 5 minutes)."""
    try:
        res = db.client().storage.from_(BUCKET).create_signed_url(storage_path, seconds)
        return res.get("signedURL") or res.get("signedUrl") or res.get("signed_url")
    except Exception:
        return None


def delete_document(doc: dict):
    """Returns (True, msg) or (False, error)."""
    try:
        db.client().storage.from_(BUCKET).remove([doc["storage_path"]])
        db.client().table("documents").delete().eq("id", doc["id"]).execute()
        return True, f"'{doc['file_name']}' deleted."
    except Exception as exc:
        return False, f"Delete failed: {exc}"
