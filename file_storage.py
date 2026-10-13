import os
import uuid

from werkzeug.utils import secure_filename

MAX_FILE_BYTES = 15 * 1024 * 1024


def uploads_dir():
    configured = os.getenv("UPLOAD_DIR")
    if configured:
        d = configured
    elif os.path.isdir("/var/data"):
        d = "/var/data/uploads"
    else:
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def is_persistent():
    return bool(os.getenv("UPLOAD_DIR")) or uploads_dir().startswith("/var/data")


def save_upload(file_storage, original_name):
    base, ext = os.path.splitext(original_name)
    safe = (secure_filename(base) or "file")[:80]
    ext = secure_filename(ext.lstrip(".")).lower()[:6]
    stored = f"{uuid.uuid4().hex[:16]}_{safe}" + (f".{ext}" if ext else "")
    path = os.path.join(uploads_dir(), stored)
    file_storage.save(path)
    if os.path.getsize(path) > MAX_FILE_BYTES:
        os.remove(path)
        raise ValueError("File must be under 15MB")
    return stored


if not is_persistent():
    print("[FILES] WARNING: saving uploads to a local folder. On Render this is wiped on every deploy/restart unless a Persistent Disk is mounted at /var/data.")
else:
    print(f"[FILES] Saving uploads to {uploads_dir()}")
