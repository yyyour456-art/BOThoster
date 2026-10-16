import os
import mimetypes
import requests
from flask import Flask, send_from_directory, abort, Response, request
from config import STORAGE_DIR
from user_manager import files_db

app = Flask(__name__)

def get_base_url() -> str:
    url = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
    return url if url else "http://localhost:8080"

def find_file_record(rel_path: str):
    norm = rel_path.replace("\\", "/")
    for fid, info in files_db.items():
        if info["rel_path"] == norm:
            return info
        if info.get("is_folder") and info.get("folder_name") and norm.startswith(info["folder_name"] + "/"):
            return info
    return None

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hosting Hub 24/7</title>
        <style>
            body { background:#0f172a; color:#f8fafc; font-family:system-ui,sans-serif; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; text-align:center; }
            .card { background:#1e293b; padding:35px; border-radius:16px; box-shadow:0 10px 30px rgba(0,0,0,0.5); border:1px solid #334155; }
            h1 { color:#38bdf8; margin-top:0; }
            .badge { background:#22c55e; color:#fff; padding:6px 14px; border-radius:20px; font-weight:bold; font-size:14px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 Personal Hosting Hub</h1>
            <p>UptimeRobot Active • Server is Running 24/7</p>
            <span class="badge">● ONLINE</span>
        </div>
    </body>
    </html>
    """

@app.route("/files/<path:rel_path>")
def serve_file(rel_path):
    filepath = os.path.join(STORAGE_DIR, rel_path)
    if not os.path.exists(filepath) or os.path.isdir(filepath):
        abort(404, description="File not found or expired!")

    # PIN Lock जांचें
    record = find_file_record(rel_path)
    if record and record.get("pin"):
        user_pin = request.args.get("pin", "")
        cookie_pin = request.cookies.get(f"pin_{record['owner']}", "")
        if user_pin != str(record["pin"]) and cookie_pin != str(record["pin"]):
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>🔒 Protected File</title>
                <style>
                    body {{ background:#0f172a; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0; }}
                    .box {{ background:#1e293b; padding:30px; border-radius:12px; text-align:center; width:300px; border:1px solid #334155; }}
                    input {{ width:85%; padding:10px; margin:15px 0; border-radius:8px; border:1px solid #475569; background:#0f172a; color:#fff; font-size:16px; text-align:center; }}
                    button {{ background:#3b82f6; color:#fff; border:none; padding:10px 20px; border-radius:8px; font-size:16px; cursor:pointer; width:92%; }}
                </style>
            </head>
            <body>
                <div class="box">
                    <h2>🔒 PIN लॉक</h2>
                    <p>इस फाइल/पेज को देखने के लिए पासवर्ड (PIN) डालें:</p>
                    <form method="GET">
                        <input type="password" name="pin" placeholder="Enter PIN..." required autofocus>
                        <button type="submit">🔓 Unlock</button>
                    </form>
                </div>
            </body>
            </html>
            """

    ext = rel_path.lower().rsplit(".", 1)[-1] if "." in rel_path else ""
    resp = None
    if ext in ("html", "htm"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            resp = Response(f.read(), mimetype="text/html; charset=utf-8")
    elif ext == "css":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            resp = Response(f.read(), mimetype="text/css; charset=utf-8")
    elif ext == "js":
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            resp = Response(f.read(), mimetype="application/javascript; charset=utf-8")
    else:
        mime_type, _ = mimetypes.guess_type(filepath)
        resp = send_from_directory(
            STORAGE_DIR,
            rel_path,
            mimetype=mime_type or "application/octet-stream",
            as_attachment=False
        )

    # अगर सही PIN डाला गया है, तो कुकी सेव कर दें ताकि फोल्डर की CSS/JS भी खुल जाएं
    if record and record.get("pin") and request.args.get("pin") == str(record["pin"]):
        resp.set_cookie(f"pin_{record['owner']}", str(record["pin"]), max_age=3600)

    return resp

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def keep_alive():
    url = get_base_url()
    if "localhost" not in url:
        try:
            requests.get(url, timeout=10)
        except Exception:
            pass
