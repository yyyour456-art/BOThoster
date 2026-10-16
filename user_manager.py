import os
import sys
import ast
import json
import time
import uuid
import shutil
import zipfile
import subprocess
import importlib.util
from config import STORAGE_DIR, DB_FILE, BASE_PACKAGES, PACKAGE_MAP

# मुख्य डेटा स्टोरेज
files_db = {}          # file_id -> dict
running_bots = {}      # file_id -> subprocess.Popen
user_sessions = {}     # user_id -> {mode, data...} (बटन स्टेप्स और HTML बिल्डर के लिए)

def save_db():
    """डेटाबेस को फाइल में सेव करता है ताकि रीस्टार्ट पर डेटा न उड़े"""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(files_db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"DB Save Error: {e}")

def load_db():
    """बॉट चालू होने पर पुरानी फाइल्स और टाइम वापस लोड करता है"""
    global files_db
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                files_db.update(json.load(f))
            # जो Python बॉट्स पहले चल रहे थे उन्हें वापस चालू करें
            for fid, info in list(files_db.items()):
                full_path = os.path.join(STORAGE_DIR, info["rel_path"])
                if not os.path.exists(full_path):
                    files_db.pop(fid, None)
                elif info["rel_path"].endswith(".py") and info.get("time_set", False):
                    start_python_bot(fid)
            save_db()
        except Exception as e:
            print(f"DB Load Error: {e}")

def generate_id() -> str:
    """6-अक्षर का छोटा यूनिक कोड बनाता है ताकि बटन कभी क्रैश न हो"""
    while True:
        fid = uuid.uuid4().hex[:6]
        if fid not in files_db:
            return fid

def register_file(rel_path: str, clean_name: str, owner_id: int, is_folder: bool = False, folder_name: str = "") -> str:
    file_id = generate_id()
    log_path = os.path.join(STORAGE_DIR, f"{file_id}.log")
    files_db[file_id] = {
        "rel_path": rel_path.replace("\\", "/"),
        "clean_name": clean_name,
        "owner": owner_id,
        "expiry": -1,
        "time_set": False,
        "uploaded_at": time.time(),
        "deps": [],
        "pending_deps": [],
        "log_path": log_path,
        "pin": None,
        "is_folder": is_folder,
        "folder_name": folder_name,
        "crash_notified": False
    }
    save_db()
    return file_id

def combine_html_bundle(html_code: str, css_list: list, js_list: list) -> str:
    """तरीका A: HTML + 2 CSS + JS को जोड़कर एक मास्टर सिंगल HTML फाइल बनाता है"""
    combined_css = "\n".join([f"<style>\n{c}\n</style>" for c in css_list if c.strip()])
    combined_js = "\n".join([f"<script>\n{j}\n</script>" for j in js_list if j.strip()])

    if not html_code.strip():
        html_code = "<!DOCTYPE html>\n<html>\n<head>\n<meta charset='UTF-8'>\n<title>Web Page</title>\n</head>\n<body>\n</body>\n</html>"

    # CSS को </head> से पहले जोड़ें
    if combined_css:
        if "</head>" in html_code.lower():
            idx = html_code.lower().rfind("</head>")
            html_code = html_code[:idx] + combined_css + "\n" + html_code[idx:]
        else:
            html_code = combined_css + "\n" + html_code

    # JS को </body> से पहले जोड़ें
    if combined_js:
        if "</body>" in html_code.lower():
            idx = html_code.lower().rfind("</body>")
            html_code = html_code[:idx] + combined_js + "\n" + html_code[idx:]
        else:
            html_code = html_code + "\n" + combined_js

    return html_code

def extract_zip_project(zip_filepath: str, folder_name: str) -> str:
    """ZIP फाइल को फोल्डर में एक्सट्रैक्ट करता है और मुख्य HTML फाइल ढूंढता है"""
    target_dir = os.path.join(STORAGE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    with zipfile.ZipFile(zip_filepath, "r") as zf:
        zf.extractall(target_dir)

    try:
        os.remove(zip_filepath)
    except Exception:
        pass

    # index.html या पहली .html फाइल ढूंढें
    entry_rel = None
    first_file = None
    for root, _, files in os.walk(target_dir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), STORAGE_DIR).replace("\\", "/")
            if not first_file:
                first_file = rel
            if f.lower() == "index.html":
                return rel
            if f.lower().endswith(".html") and not entry_rel:
                entry_rel = rel

    return entry_rel or first_file or folder_name

def detect_missing_packages(filepath: str) -> list:
    """Python फाइल में कौन-सी लाइब्रेरी इंस्टॉल नहीं है, उसका पता लगाता है"""
    missing = set()
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=filepath)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if not _is_module_installed(mod):
                        missing.add(PACKAGE_MAP.get(mod, mod))
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    mod = node.module.split(".")[0]
                    if not _is_module_installed(mod):
                        missing.add(PACKAGE_MAP.get(mod, mod))
    except Exception as e:
        print(f"AST Scan Error: {e}")
    return list(missing)

def _is_module_installed(mod_name: str) -> bool:
    if mod_name in sys.builtin_module_names:
        return True
    # लोकल प्रोजेक्ट की फाइलों को इग्नोर करें
    if mod_name in ("config", "user_manager", "web_server", "main"):
        return True
    try:
        return importlib.util.find_spec(mod_name) is not None
    except Exception:
        return False

def start_python_bot(file_id: str) -> bool:
    if file_id not in files_db:
        return False
    stop_python_bot(file_id)
    info = files_db[file_id]
    filepath = os.path.join(STORAGE_DIR, info["rel_path"])
    if not os.path.exists(filepath):
        return False

    log_file = open(info["log_path"], "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-u", os.path.abspath(filepath)],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(os.path.abspath(filepath))
    )
    running_bots[file_id] = proc
    info["crash_notified"] = False
    save_db()
    return True

def stop_python_bot(file_id: str):
    proc = running_bots.pop(file_id, None)
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

def install_packages(packages: list) -> tuple[bool, str]:
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-cache-dir", *packages],
            capture_output=True,
            text=True,
            timeout=150
        )
        out = res.stdout[-500:] if res.returncode == 0 else res.stderr[-500:]
        return (res.returncode == 0), out
    except Exception as e:
        return False, str(e)

def uninstall_unused_packages(packages: list, ignore_file_id: str):
    still_needed = set()
    for fid, data in files_db.items():
        if fid != ignore_file_id:
            still_needed.update(data.get("deps", []))

    to_remove = [
        p for p in packages
        if p.lower() not in BASE_PACKAGES and p not in still_needed
    ]
    if to_remove:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", *to_remove],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"Auto-uninstalled packages: {to_remove}")
        except Exception as e:
            print(f"Uninstall error: {e}")

def delete_file_and_process(file_id: str) -> bool:
    info = files_db.pop(file_id, None)
    if not info:
        return False

    stop_python_bot(file_id)

    if info.get("deps"):
        uninstall_unused_packages(info["deps"], file_id)

    if info.get("is_folder") and info.get("folder_name"):
        folder_path = os.path.join(STORAGE_DIR, info["folder_name"])
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
    else:
        filepath = os.path.join(STORAGE_DIR, info["rel_path"])
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass

    log_path = info.get("log_path", "")
    if log_path and os.path.exists(log_path):
        try:
            os.remove(log_path)
        except Exception:
            pass

    save_db()
    return True

def cleanup_files():
    now = time.time()
    expired_ids = [
        fid for fid, data in list(files_db.items())
        if data["expiry"] != -1 and now >= data["expiry"]
    ]
    for fid in expired_ids:
        delete_file_and_process(fid)

def format_remaining_time(expiry: float) -> str:
    if expiry == -1:
        return "♾️ परमानेंट"
    rem = int(expiry - time.time())
    if rem <= 0:
        return "⌛ समाप्त हो गया"
    days, rem = divmod(rem, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)

    parts = []
    if days > 0:
        parts.append(f"{days} दिन")
    if hours > 0:
        parts.append(f"{hours} घंटा")
    if minutes > 0 or not parts:
        parts.append(f"{minutes} मिनट")
    return " ".join(parts)
