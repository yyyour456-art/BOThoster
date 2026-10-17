import os

# अपना Bot Token और Admin ID यहाँ डालें (या Render के Environment Variables में सेट करें)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "bot")

# एक से ज्यादा एडमिन ID कॉमा (,) लगाकर डाल सकते हैं
ADMIN_IDS = [
    int(x) for x in os.environ.get("ADMIN_IDS", "id").split(",") if x.strip().isdigit()
]

STORAGE_DIR = "hosted_files"
DB_FILE = os.path.join(STORAGE_DIR, "database.json")
os.makedirs(STORAGE_DIR, exist_ok=True)

# बेस लाइब्रेरी जिन्हें कभी अनइंस्टॉल नहीं करना है
BASE_PACKAGES = {
    "telegram", "apscheduler", "flask", "requests", "psutil",
    "qrcode", "pil", "pillow", "pip", "setuptools", "wheel"
}

# Python import नाम और उनके असली pip पैकेज नाम की मैपिंग
PACKAGE_MAP = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python-headless",
    "PIL": "Pillow",
    "dotenv": "python-dotenv",
    "sklearn": "scikit-learn",
    "yaml": "PyYAML",
    "telebot": "pyTelegramBotAPI",
    "pyrogram": "pyrogram",
    "aiogram": "aiogram",
    "dns": "dnspython",
    "Crypto": "pycryptodome",
    "jwt": "PyJWT"
}

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
