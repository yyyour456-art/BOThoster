import os
import requests
from flask import Flask, send_from_directory
from config import STORAGE_DIR

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "<h1>Bot Web Server Active!</h1>"

@flask_app.route('/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(STORAGE_DIR, filename)

def run_web_server():
    # Render अपने आप PORT देता है
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    # Render का URL ऑटोमैटिक डिटेक्ट कर लेगा
    render_url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if render_url:
        try:
            requests.get(render_url)
            print("🔄 Auto-ping successful!")
        except Exception as e:
            print(f"⚠️ Ping error: {e}")
