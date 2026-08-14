# ==========================================
# यहाँ अपनी डिटेल्स डाल दो, Render पर कुछ नहीं भरना पड़ेगा
# ==========================================

BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"  # यहाँ अपना Bot Token डालो
ADMIN_IDS = [123456789]                       # यहाँ अपनी Telegram ID डालो (उदा: [123456789, 987654321])

# ==========================================
# बाकी सब ऑटोमेटिक है
# ==========================================
import os

STORAGE_DIR = "storage"
os.makedirs(STORAGE_DIR, exist_ok=True)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
