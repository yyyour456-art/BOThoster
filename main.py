import io
import os
import html
import time
import psutil
import qrcode
import threading
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from apscheduler.schedulers.background import BackgroundScheduler

from config import BOT_TOKEN, STORAGE_DIR, is_admin
from web_server import run_web_server, keep_alive, get_base_url
from user_manager import (
    files_db, running_bots, user_sessions, save_db, load_db,
    register_file, combine_html_bundle, extract_zip_project,
    detect_missing_packages, start_python_bot, stop_python_bot,
    install_packages, delete_file_and_process, cleanup_files,
    format_remaining_time
)

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_files, "interval", minutes=1)
scheduler.add_job(keep_alive, "interval", minutes=10)
scheduler.start()

# ==================== HELPER FUNCTIONS ====================

def make_file_url(rel_path: str) -> str:
    safe_path = "/".join(urllib.parse.quote(part) for part in rel_path.split("/"))
    return f"{get_base_url()}/files/{safe_path}"

def is_valid_telegram_url(url: str) -> bool:
    return url.startswith("http") and "localhost" not in url and "127.0.0.1" not in url

def get_dashboard_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton("🛠️ Create HTML (Combine 4 Files)", callback_data="menu|combine"),
            InlineKeyboardButton("📁 Multi-File Web Folder", callback_data="menu|folder")
        ],
        [
            InlineKeyboardButton("📝 Direct Code Paste", callback_data="menu|paste"),
            InlineKeyboardButton("📂 My Hosted Files", callback_data="menu|myfiles")
        ],
        [
            InlineKeyboardButton("🖥️ Server & Uptime Status", callback_data="menu|status"),
            InlineKeyboardButton("🧹 Manual Cleanup", callback_data="menu|cleanup")
        ]
    ]
    if is_admin(user_id):
        kb.append([InlineKeyboardButton("👑 Admin Master Panel", callback_data="menu|admin")])
    return InlineKeyboardMarkup(kb)

def get_file_action_keyboard(file_id: str) -> InlineKeyboardMarkup:
    """जहाँ भी लिंक दिया जाएगा, उसके नीचे यही सेम फुल कंट्रोल बटन आएंगे"""
    info = files_db.get(file_id)
    if not info:
        return InlineKeyboardMarkup([])

    url = make_file_url(info["rel_path"])
    row1 = []
    if is_valid_telegram_url(url):
        row1.append(InlineKeyboardButton("🔗 View Live", url=url))
    row1.append(InlineKeyboardButton("⏱️ Time & Details", callback_data=f"info|{file_id}"))
    row1.append(InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{file_id}"))

    row2 = [
        InlineKeyboardButton("📱 Generate QR", callback_data=f"qr|{file_id}"),
        InlineKeyboardButton("➕ Extend Time", callback_data=f"extmenu|{file_id}"),
        InlineKeyboardButton("🔄 Replace", callback_data=f"rep|{file_id}")
    ]

    pin_label = "🔓 Remove PIN" if info.get("pin") else "🔒 Set PIN"
    row3 = [
        InlineKeyboardButton(pin_label, callback_data=f"pin|{file_id}"),
        InlineKeyboardButton("📥 Download File", callback_data=f"dl|{file_id}")
    ]

    keyboard = [row1, row2, row3]

    if info["rel_path"].endswith(".py"):
        keyboard.append([
            InlineKeyboardButton("📜 Live Logs", callback_data=f"log|{file_id}"),
            InlineKeyboardButton("🔄 Restart Bot", callback_data=f"restart|{file_id}")
        ])
    return InlineKeyboardMarkup(keyboard)

def get_time_selection_keyboard(file_id: str, prefix: str = "time") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱️ 1 घंटा", callback_data=f"{prefix}|3600|{file_id}"),
            InlineKeyboardButton("⏱️ 1 दिन", callback_data=f"{prefix}|86400|{file_id}")
        ],
        [
            InlineKeyboardButton("⏱️ 7 दिन", callback_data=f"{prefix}|604800|{file_id}"),
            InlineKeyboardButton("⏱️ 30 दिन", callback_data=f"{prefix}|2592000|{file_id}")
        ],
        [
            InlineKeyboardButton("✍️ कस्टम समय", callback_data=f"custom|{file_id}"),
            InlineKeyboardButton("♾️ परमानेंट", callback_data=f"{prefix}|perm|{file_id}")
        ],
        [
            InlineKeyboardButton("❌ कैंसिल / डिलीट करें", callback_data=f"del|{file_id}")
        ]
    ])

def build_live_message(file_id: str, extra_header: str = "") -> str:
    info = files_db[file_id]
    link = make_file_url(info["rel_path"])
    rem_str = format_remaining_time(info["expiry"])
    pin_str = f"\n🔒 <b>PIN Lock:</b> <code>{info['pin']}</code>" if info.get("pin") else ""
    header = f"{extra_header}\n\n" if extra_header else ""

    return (
        f"{header}✅ <b>{html.escape(info['clean_name'])}</b> लाइव है!\n\n"
        f"🔗 <b>डायरेक्ट वेब लिंक:</b>\n<code>{link}</code>\n\n"
        f"⏳ <b>वैधता (Time):</b> {rem_str}{pin_str}"
    )

# ==================== START & COMMANDS ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions.pop(user_id, None)
    admin_tag = " (👑 Admin)" if is_admin(user_id) else ""

    text = (
        f"👋 <b>अल्टीमेट होस्टिंग हब में आपका स्वागत है!{admin_tag}</b>\n\n"
        "📤 <b>सीधे कोई भी फाइल भेजें:</b>\n"
        "• <code>.html / .css / .js</code> - लाइव वेबसाइट पेज चलेगा\n"
        "• <code>.zip</code> - ऑटो-एक्सट्रैक्ट होकर पूरा वेब फोल्डर लाइव होगा\n"
        "• <code>.py</code> - 24/7 बैकग्राउंड बॉट (Auto Library Installer के साथ)\n"
        "• <code>.pdf / .jpg / .png / .mp4</code> - डायरेक्ट ब्राउज़र लिंक\n\n"
        "👇 <b>नीचे दिए गए स्मार्ट टूल्स का उपयोग करें:</b>"
    )
    await update.message.reply_text(
        text,
        reply_markup=get_dashboard_keyboard(user_id),
        parse_mode="HTML"
    )

async def myfiles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_myfiles_list(update.message, update.effective_user.id)

async def send_myfiles_list(target_msg, user_id: int):
    user_items = [(fid, data) for fid, data in files_db.items() if data["owner"] == user_id]
    if not user_items:
        await target_msg.reply_text("📂 आपकी कोई फाइल अभी होस्ट नहीं है।")
        return

    await target_msg.reply_text(
        f"📁 <b>आपकी एक्टिव फाइल्स ({len(user_items)}):</b>",
        parse_mode="HTML"
    )
    for fid, _ in user_items:
        await target_msg.reply_text(
            build_live_message(fid),
            reply_markup=get_file_action_keyboard(fid),
            parse_mode="HTML"
        )

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_status_info(update.message)

async def send_status_info(target_msg):
    ram = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.4)
    active_bots = sum(1 for p in running_bots.values() if p.poll() is None)
    url = get_base_url()

    text = (
        "🖥️ <b>सर्वर हेल्थ & UptimeRobot स्टेटस:</b>\n\n"
        f"🌐 <b>UptimeRobot URL:</b>\n<code>{url}</code>\n\n"
        f"🧠 <b>RAM उपयोग:</b> <code>{ram.percent}%</code> ({ram.used // (1024*1024)} MB / {ram.total // (1024*1024)} MB)\n"
        f"⚡ <b>CPU लोड:</b> <code>{cpu}%</code>\n"
        f"📂 <b>कुल होस्टेड फाइल्स:</b> <code>{len(files_db)}</code>\n"
        f"🤖 <b>रनिंग Python बॉट्स:</b> <code>{active_bots}</code>"
    )
    await target_msg.reply_text(text, parse_mode="HTML")

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if not files_db:
        await update.message.reply_text("👑 <b>एडमिन पैनल:</b> कोई फाइल होस्ट नहीं है।", parse_mode="HTML")
        return

    await update.message.reply_text(f"👑 <b>एडमिन पैनल (कुल फाइल्स: {len(files_db)})</b>", parse_mode="HTML")
    for fid, data in list(files_db.items()):
        await update.message.reply_text(
            build_live_message(fid, extra_header=f"👤 Owner ID: <code>{data['owner']}</code>"),
            reply_markup=get_file_action_keyboard(fid),
            parse_mode="HTML"
        )

async def cleanup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_files()
    await update.message.reply_text("🧹 एक्सपायर फाइल्स और फालतू लाइब्रेरी का क्लीनअप पूरा हुआ!")

# ==================== FILE & TEXT HANDLERS ====================

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        session = user_sessions.get(user_id)

        if update.message.document:
            raw_filename = update.message.document.file_name or f"file_{int(time.time())}"
            file_obj = await context.bot.get_file(update.message.document.file_id)
        elif update.message.photo:
            raw_filename = f"photo_{int(time.time())}.jpg"
            file_obj = await context.bot.get_file(update.message.photo[-1].file_id)
        elif update.message.video:
            raw_filename = update.message.video.file_name or f"video_{int(time.time())}.mp4"
            file_obj = await context.bot.get_file(update.message.video.file_id)
        elif update.message.audio:
            raw_filename = update.message.audio.file_name or f"audio_{int(time.time())}.mp3"
            file_obj = await context.bot.get_file(update.message.audio.file_id)
        else:
            return

        safe_clean = os.path.basename(raw_filename).replace(" ", "_")

        # 1. अगर यूजर "Create HTML (Combine 4 Files)" मोड में है
        if session and session.get("mode") == "combine":
            temp_path = os.path.join(STORAGE_DIR, f"temp_{user_id}_{safe_clean}")
            await file_obj.download_to_drive(temp_path)
            with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            os.remove(temp_path)

            ext = safe_clean.lower().rsplit(".", 1)[-1] if "." in safe_clean else ""
            if ext in ("html", "htm"):
                session["html"] = content
                tag = "HTML फाइल"
            elif ext == "css":
                session["css"].append(content)
                tag = f"CSS फाइल (#{len(session['css'])})"
            elif ext == "js":
                session["js"].append(content)
                tag = f"JS फाइल (#{len(session['js'])})"
            else:
                await update.message.reply_text("⚠️ कृपया केवल `.html`, `.css` या `.js` फाइल भेजें!")
                return

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Build & Generate Live Link", callback_data="combine|build")],
                [InlineKeyboardButton("❌ Cancel", callback_data="combine|cancel")]
            ])
            await update.message.reply_text(
                f"📥 <b>{tag} (`{html.escape(safe_clean)}`) जुड़ गई!</b>\n\n"
                f"📊 <b>अभी तक:</b> HTML: <code>{'1' if session['html'] else '0'}</code> | "
                f"CSS: <code>{len(session['css'])}</code> | JS: <code>{len(session['js'])}</code>\n\n"
                "और फाइलें भेजें या नीचे <b>Build & Generate Live Link</b> दबाएं:",
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

        # 2. अगर यूजर "Multi-File Web Folder" मोड में है
        if session and session.get("mode") == "folder":
            folder_name = session["folder_name"]
            folder_dir = os.path.join(STORAGE_DIR, folder_name)
            os.makedirs(folder_dir, exist_ok=True)
            dest = os.path.join(folder_dir, safe_clean)
            await file_obj.download_to_drive(dest)
            session["files"].append(safe_clean)

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Publish Web Folder", callback_data="folder|build")],
                [InlineKeyboardButton("❌ Cancel", callback_data="folder|cancel")]
            ])
            await update.message.reply_text(
                f"📂 फोल्डर में <b>{html.escape(safe_clean)}</b> सेव हो गई!\n"
                f"कुल फाइलें: <code>{', '.join(session['files'])}</code>\n\n"
                "बाकी फाइलें (`index.html`, `style.css`, `ui.css`, `script.js` आदि) भेजें या <b>Publish</b> दबाएं:",
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

        # 3. अगर यूजर किसी पुरानी फाइल को "Replace / Update" कर रहा है
        if session and session.get("mode") == "replace":
            target_fid = session["file_id"]
            user_sessions.pop(user_id, None)
            if target_fid not in files_db:
                await update.message.reply_text("❌ पुरानी फाइल अब मौजूद नहीं है।")
                return
            info = files_db[target_fid]
            dest = os.path.join(STORAGE_DIR, info["rel_path"])
            await file_obj.download_to_drive(dest)
            if info["rel_path"].endswith(".py"):
                start_python_bot(target_fid)
            await update.message.reply_text(
                build_live_message(target_fid, extra_header="🔄 <b>फाइल सफलतापूर्वक अपडेट (Replace) हो गई! लिंक वही सेम है:</b>"),
                reply_markup=get_file_action_keyboard(target_fid),
                parse_mode="HTML"
            )
            return

        # 4. अगर यूजर ने `.zip` फाइल भेजी है (Auto-Extractor)
        if safe_clean.lower().endswith(".zip"):
            folder_name = f"zip_{user_id}_{int(time.time())}"
            temp_zip = os.path.join(STORAGE_DIR, f"{folder_name}.zip")
            await file_obj.download_to_drive(temp_zip)
            entry_rel = extract_zip_project(temp_zip, folder_name)
            file_id = register_file(entry_rel, f"📦 {safe_clean}", user_id, is_folder=True, folder_name=folder_name)

            await update.message.reply_text(
                f"📦 <b>ZIP प्रोजेक्ट ({html.escape(safe_clean)}) अनज़िप हो गया!</b>\n\n"
                "⏱️ <b>कृपया समय चुनें ताकि लाइव लिंक जनरेट हो सके:</b>",
                reply_markup=get_time_selection_keyboard(file_id),
                parse_mode="HTML"
            )
            return

        # 5. नॉर्मल सिंगल फाइल अपलोड (.html, .py, .pdf, .jpg आदि)
        stored_name = f"{user_id}_{int(time.time())}_{safe_clean}"
        filepath = os.path.join(STORAGE_DIR, stored_name)
        await file_obj.download_to_drive(filepath)
        file_id = register_file(stored_name, safe_clean, user_id)

        await update.message.reply_text(
            f"📁 <b>फाइल प्राप्त हुई:</b> <code>{html.escape(safe_clean)}</code>\n\n"
            "⏱️ <b>आप इसे कितने समय के लिए लाइव रखना चाहते हैं?</b>",
            reply_markup=get_time_selection_keyboard(file_id),
            parse_mode="HTML"
        )

    except Exception as e:
        print(f"Error in handle_document: {e}")
        await update.message.reply_text("❌ फाइल प्रोसेस करने में समस्या आई।")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = user_sessions.get(user_id)
    if not session:
        return

    mode = session.get("mode")
    text = update.message.text.strip()

    # 1. कस्टम समय इनपुट (जैसे 30m, 5h, 2d)
    if mode == "custom_time":
        file_id = session["file_id"]
        user_sessions.pop(user_id, None)
        if file_id not in files_db:
            await update.message.reply_text("❌ फाइल पहले ही हटाई जा चुकी है।")
            return
        raw = text.lower()
        try:
            if raw.endswith("m"):
                seconds = int(raw[:-1]) * 60
            elif raw.endswith("h"):
                seconds = int(raw[:-1]) * 3600
            elif raw.endswith("d"):
                seconds = int(raw[:-1]) * 86400
            else:
                seconds = int(raw) * 60
            files_db[file_id]["expiry"] = time.time() + max(60, seconds)
            files_db[file_id]["time_set"] = True
            save_db()
            await activate_hosted_file(update.message, file_id, is_callback=False)
        except ValueError:
            await update.message.reply_text(
                "⚠️ गलत फॉर्मेट! कृपया ऐसे लिखें: <code>30m</code>, <code>5h</code>, या <code>2d</code>",
                parse_mode="HTML"
            )

    # 2. PIN पासवर्ड सेट करना
    elif mode == "set_pin":
        file_id = session["file_id"]
        user_sessions.pop(user_id, None)
        if file_id in files_db:
            files_db[file_id]["pin"] = text
            save_db()
            await update.message.reply_text(
                build_live_message(file_id, extra_header=f"🔒 <b>PIN पासवर्ड ({html.escape(text)}) सेट हो गया!</b>"),
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

    # 3. Direct Code Paste: स्टेप 1 (फाइल का नाम) -> स्टेप 2 (कोड)
    elif mode == "paste_name":
        safe_name = os.path.basename(text).replace(" ", "_")
        if "." not in safe_name:
            safe_name += ".html"
        session["filename"] = safe_name
        session["mode"] = "paste_code"
        await update.message.reply_text(
            f"✅ नाम सेट: <code>{html.escape(safe_name)}</code>\n\n"
            "📝 <b>अब अपना पूरा कोड (HTML / Python / CSS / JS) यहाँ चैट में पेस्ट करके भेजें:</b>",
            parse_mode="HTML"
        )

    elif mode == "paste_code":
        safe_name = session["filename"]
        user_sessions.pop(user_id, None)
        stored_name = f"{user_id}_{int(time.time())}_{safe_name}"
        filepath = os.path.join(STORAGE_DIR, stored_name)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(update.message.text)

        file_id = register_file(stored_name, safe_name, user_id)
        await update.message.reply_text(
            f"📝 <b>कोड से फाइल बन गई:</b> <code>{html.escape(safe_name)}</code>\n\n"
            "⏱️ <b>कृपया समय चुनें:</b>",
            reply_markup=get_time_selection_keyboard(file_id),
            parse_mode="HTML"
        )

# ==================== FILE ACTIVATION & PYTHON CHECK ====================

async def activate_hosted_file(message_or_query, file_id: str, is_callback: bool = True):
    info = files_db.get(file_id)
    if not info:
        return

    filepath = os.path.join(STORAGE_DIR, info["rel_path"])

    # अगर Python फाइल है तो मिसिंग लाइब्रेरी चेक करें
    if info["rel_path"].endswith(".py"):
        missing = detect_missing_packages(filepath)
        if missing:
            info["pending_deps"] = missing
            save_db()
            deps_str = ", ".join(missing)
            msg = (
                f"{build_live_message(file_id)}\n\n"
                f"⚠️ <b>ध्यान दें:</b> इस Python बॉट में ये लाइब्रेरी सर्वर पर नहीं हैं:\n"
                f"📦 <code>{html.escape(deps_str)}</code>\n\n"
                "क्या मैं इन्हें इंस्टॉल करके बॉट चालू कर दूं? (फाइल डिलीट होने पर ये खुद अनइंस्टॉल हो जाएंगी)"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 हां, Install & Run करें", callback_data=f"inst|{file_id}")],
                [InlineKeyboardButton("▶️ बिना इंस्टॉल किए चलाएं", callback_data=f"runraw|{file_id}")],
                [InlineKeyboardButton("🗑️ फाइल डिलीट करें", callback_data=f"del|{file_id}")]
            ])
            if is_callback:
                await message_or_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
            else:
                await message_or_query.reply_text(msg, reply_markup=kb, parse_mode="HTML")
            return
        else:
            start_python_bot(file_id)
            msg = build_live_message(file_id, extra_header="🤖 <b>सब-बॉट बैकग्राउंड में स्टार्ट हो गया है!</b>")
    else:
        msg = build_live_message(file_id)

    kb = get_file_action_keyboard(file_id)
    if is_callback:
        await message_or_query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_query.reply_text(msg, reply_markup=kb, parse_mode="HTML")

# ==================== BUTTON CALLBACK HANDLER ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    try:
        action, *params = data.split("|")

        # --- होम मेनू के बटन ---
        if action == "menu":
            sub = params[0]
            await query.answer()
            if sub == "combine":
                user_sessions[user_id] = {"mode": "combine", "html": "", "css": [], "js": []}
                await query.message.reply_text(
                    "🛠️ <b>Create HTML Page (Auto-Combine Mode) चालू!</b>\n\n"
                    "अब आप अपनी फाइलें एक-एक करके भेजें:\n"
                    "• <code>index.html</code>\n"
                    "• <code>style.css</code> / <code>ui.css</code> (जितनी भी CSS हों)\n"
                    "• <code>script.js</code>\n\n"
                    "सारी फाइलें भेजने के बाद <b>✅ Build & Generate Live Link</b> बटन दबाएं।",
                    parse_mode="HTML"
                )
            elif sub == "folder":
                folder_name = f"web_{user_id}_{int(time.time())}"
                user_sessions[user_id] = {"mode": "folder", "folder_name": folder_name, "files": []}
                await query.message.reply_text(
                    "📁 <b>Multi-File Web Folder Mode चालू!</b>\n\n"
                    "अपनी वेबसाइट की सारी फाइलें (जैसे `index.html`, `style.css`, `ui.css`, `script.js`, फोटो आदि) एक-एक करके भेजें।\n"
                    "बॉट सबको एक ही फोल्डर में रखेगा और `index.html` का लाइव लिंक बना देगा!",
                    parse_mode="HTML"
                )
            elif sub == "paste":
                user_sessions[user_id] = {"mode": "paste_name"}
                await query.message.reply_text(
                    "📝 <b>Direct Code Paste Mode</b>\n\n"
                    "सबसे पहले फाइल का नाम लिखकर भेजें (जैसे: <code>index.html</code> या <code>bot.py</code>):",
                    parse_mode="HTML"
                )
            elif sub == "myfiles":
                await send_myfiles_list(query.message, user_id)
            elif sub == "status":
                await send_status_info(query.message)
            elif sub == "cleanup":
                cleanup_files()
                await query.message.reply_text("🧹 क्लीनअप पूरा हुआ!")
            elif sub == "admin" and is_admin(user_id):
                await admin_cmd(update, context)
            return

        # --- तरीका A: Combine HTML Build ---
        if action == "combine":
            sub = params[0]
            session = user_sessions.pop(user_id, None)
            if sub == "cancel" or not session:
                await query.answer("❌ कैंसिल कर दिया गया।")
                await query.edit_message_text("❌ <b>HTML Builder कैंसिल कर दिया गया।</b>", parse_mode="HTML")
                return

            await query.answer("🔨 मास्टर HTML फाइल बनाई जा रही है...")
            merged_html = combine_html_bundle(session["html"], session["css"], session["js"])
            stored_name = f"{user_id}_{int(time.time())}_combined_index.html"
            filepath = os.path.join(STORAGE_DIR, stored_name)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(merged_html)

            file_id = register_file(stored_name, "combined_index.html", user_id)

            # यूजर को बनी हुई मास्टर HTML फाइल चैट में भी भेज दें
            with open(filepath, "rb") as doc_f:
                await query.message.reply_document(
                    document=doc_f,
                    filename="index.html",
                    caption="🎁 <b>आपकी कंबाइंड मास्टर <code>index.html</code> फाइल तैयार है!</b>",
                    parse_mode="HTML"
                )

            await query.edit_message_text(
                "✅ <b>HTML + CSS + JS को जोड़कर मास्टर वेबपेज बना दिया गया है!</b>\n\n"
                "⏱️ <b>अब लाइव लिंक के लिए समय चुनें:</b>",
                reply_markup=get_time_selection_keyboard(file_id),
                parse_mode="HTML"
            )
            return

        # --- तरीका B: Multi-File Folder Build ---
        if action == "folder":
            sub = params[0]
            session = user_sessions.pop(user_id, None)
            if sub == "cancel" or not session or not session.get("files"):
                await query.answer("❌ कैंसिल कर दिया गया।")
                await query.edit_message_text("❌ <b>Web Folder Mode कैंसिल कर दिया गया।</b>", parse_mode="HTML")
                return

            folder_name = session["folder_name"]
            uploaded = session["files"]
            entry_file = "index.html" if "index.html" in uploaded else next((f for f in uploaded if f.endswith(".html")), uploaded[0])
            rel_path = f"{folder_name}/{entry_file}"
            file_id = register_file(rel_path, f"📁 {folder_name} ({entry_file})", user_id, is_folder=True, folder_name=folder_name)

            await query.edit_message_text(
                f"📂 <b>वेब फोल्डर तैयार है! कुल फाइलें ({len(uploaded)}):</b> <code>{', '.join(uploaded)}</code>\n\n"
                "⏱️ <b>लाइव लिंक एक्टिवेट करने के लिए समय चुनें:</b>",
                reply_markup=get_time_selection_keyboard(file_id),
                parse_mode="HTML"
            )
            return

        # --- फाइल स्पेसिफिक एक्शन ---
        file_id = params[-1] if params else ""
        info = files_db.get(file_id)

        if not info:
            await query.answer("❌ यह फाइल अब मौजूद नहीं है या डिलीट हो चुकी है!", show_alert=True)
            await query.edit_message_text("🗑️ <b>यह फाइल हटाई जा चुकी है।</b>", parse_mode="HTML")
            return

        if info["owner"] != user_id and not is_admin(user_id):
            await query.answer("⛔ यह आपकी फाइल नहीं है!", show_alert=True)
            return

        if action == "time":
            await query.answer("⏱️ समय सेट हो गया!")
            time_val = params[0]
            info["expiry"] = -1 if time_val == "perm" else (time.time() + int(time_val))
            info["time_set"] = True
            save_db()
            await activate_hosted_file(query, file_id, is_callback=True)

        elif action == "extmenu":
            await query.answer()
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("➕ +1 घंटा", callback_data=f"addtime|3600|{file_id}"),
                    InlineKeyboardButton("➕ +1 दिन", callback_data=f"addtime|86400|{file_id}")
                ],
                [
                    InlineKeyboardButton("➕ +7 दिन", callback_data=f"addtime|604800|{file_id}"),
                    InlineKeyboardButton("♾️ परमानेंट करें", callback_data=f"addtime|perm|{file_id}")
                ],
                [InlineKeyboardButton("🔙 वापस जाएं", callback_data=f"back|{file_id}")]
            ])
            await query.edit_message_text(
                f"{build_live_message(file_id)}\n\n➕ <b>कितना समय और बढ़ाना चाहते हैं?</b>",
                reply_markup=kb,
                parse_mode="HTML"
            )

        elif action == "addtime":
            val = params[0]
            if val == "perm":
                info["expiry"] = -1
            else:
                base = max(time.time(), info["expiry"]) if info["expiry"] != -1 else time.time()
                info["expiry"] = base + int(val)
            save_db()
            await query.answer("✅ समय बढ़ा दिया गया!", show_alert=True)
            await query.edit_message_text(
                build_live_message(file_id, extra_header="⏳ <b>फाइल की वैधता बढ़ा दी गई है!</b>"),
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "back":
            await query.answer()
            await query.edit_message_text(
                build_live_message(file_id),
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "custom":
            user_sessions[user_id] = {"mode": "custom_time", "file_id": file_id}
            await query.answer()
            await query.edit_message_text(
                f"✍️ <b>{html.escape(info['clean_name'])}</b> के लिए समय लिखकर भेजें:\n\n"
                "उदाहरण: <code>45m</code> (45 मिनट), <code>6h</code> (6 घंटे), <code>3d</code> (3 दिन)",
                parse_mode="HTML"
            )

        elif action == "inst":
            pending = info.get("pending_deps", [])
            await query.answer("📥 लाइब्रेरी इंस्टॉल हो रही है...")
            await query.edit_message_text(
                f"⏳ <b>इंस्टॉल हो रहा है:</b> <code>{', '.join(pending)}</code>\nकृपया 10-20 सेकंड प्रतीक्षा करें...",
                parse_mode="HTML"
            )
            ok, out = install_packages(pending)
            if ok:
                info["deps"].extend(pending)
                info["pending_deps"] = []
                start_python_bot(file_id)
                save_db()
                await query.edit_message_text(
                    build_live_message(
                        file_id,
                        extra_header=f"✅ <b>लाइब्रेरी (<code>{', '.join(info['deps'])}</code>) इंस्टॉल हो गईं और बॉट चालू हो गया!</b>"
                    ),
                    reply_markup=get_file_action_keyboard(file_id),
                    parse_mode="HTML"
                )
            else:
                await query.edit_message_text(
                    f"❌ <b>इंस्टॉल करने में एरर आया:</b>\n<pre>{html.escape(out)}</pre>\n\n{build_live_message(file_id)}",
                    reply_markup=get_file_action_keyboard(file_id),
                    parse_mode="HTML"
                )

        elif action == "runraw":
            await query.answer("▶️ बॉट स्टार्ट किया जा रहा है...")
            start_python_bot(file_id)
            await query.edit_message_text(
                build_live_message(file_id, extra_header="🤖 <b>बॉट बिना एक्स्ट्रा पैकेज के स्टार्ट कर दिया गया!</b>"),
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "info":
            filepath = os.path.join(STORAGE_DIR, info["rel_path"])
            size_kb = round(os.path.getsize(filepath) / 1024, 2) if os.path.exists(filepath) else 0
            rem_str = format_remaining_time(info["expiry"])
            link = make_file_url(info["rel_path"])

            status_line = ""
            if info["rel_path"].endswith(".py"):
                proc = running_bots.get(file_id)
                if proc and proc.poll() is None:
                    status_line = f"\n🤖 <b>बॉट स्टेटस:</b> 🟢 Running (PID: {proc.pid})"
                else:
                    status_line = "\n🤖 <b>बॉट स्टेटस:</b> 🔴 Stopped / Crashed"
                if info.get("deps"):
                    status_line += f"\n📦 <b>इंस्टॉल्ड लाइब्रेरी:</b> <code>{', '.join(info['deps'])}</code>"

            await query.answer(f"⏳ बचा समय: {rem_str}")
            detail_msg = (
                f"📊 <b>फाइल की पूरी जानकारी (Time & Details):</b>\n\n"
                f"📄 <b>नाम:</b> <code>{html.escape(info['clean_name'])}</code>\n"
                f"💾 <b>साइज:</b> <code>{size_kb} KB</code>\n"
                f"⏳ <b>बचा हुआ समय:</b> {rem_str}\n"
                f"🔒 <b>PIN Lock:</b> <code>{info['pin'] or 'Off'}</code>"
                f"{status_line}\n\n"
                f"🔗 <b>डायरेक्ट वेब लिंक:</b>\n<code>{link}</code>"
            )
            await query.edit_message_text(
                detail_msg,
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "qr":
            await query.answer("📱 QR कोड जनरेट हो रहा है...")
            link = make_file_url(info["rel_path"])
            qr_img = qrcode.make(link)
            bio = io.BytesIO()
            qr_img.save(bio, format="PNG")
            bio.seek(0)
            await query.message.reply_photo(
                photo=bio,
                caption=build_live_message(file_id, extra_header="📱 <b>स्कैन करें या नीचे दिए गए कंट्रोल बटन इस्तेमाल करें:</b>"),
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "rep":
            user_sessions[user_id] = {"mode": "replace", "file_id": file_id}
            await query.answer()
            await query.message.reply_text(
                f"🔄 <b>{html.escape(info['clean_name'])}</b> को अपडेट करने के लिए नई फाइल अभी भेजें:\n"
                "(आपका वेब लिंक वही पुराना सेम रहेगा!)",
                parse_mode="HTML"
            )

        elif action == "pin":
            if info.get("pin"):
                info["pin"] = None
                save_db()
                await query.answer("🔓 PIN हटा दिया गया!", show_alert=True)
                await query.edit_message_text(
                    build_live_message(file_id, extra_header="🔓 <b>PIN लॉक हटा दिया गया है!</b>"),
                    reply_markup=get_file_action_keyboard(file_id),
                    parse_mode="HTML"
                )
            else:
                user_sessions[user_id] = {"mode": "set_pin", "file_id": file_id}
                await query.answer()
                await query.message.reply_text(
                    f"🔒 <b>{html.escape(info['clean_name'])}</b> के लिए नया PIN / पासवर्ड लिखकर भेजें (जैसे <code>1234</code>):",
                    parse_mode="HTML"
                )

        elif action == "dl":
            filepath = os.path.join(STORAGE_DIR, info["rel_path"])
            if os.path.exists(filepath):
                await query.answer("📥 फाइल भेजी जा रही है...")
                with open(filepath, "rb") as f:
                    await query.message.reply_document(
                        document=f,
                        filename=os.path.basename(filepath),
                        caption=build_live_message(file_id),
                        reply_markup=get_file_action_keyboard(file_id),
                        parse_mode="HTML"
                    )
            else:
                await query.answer("❌ फाइल डिस्क पर नहीं मिली!", show_alert=True)

        elif action == "log":
            await query.answer("📜 लॉग्स लोड हो रहे हैं...")
            log_path = info.get("log_path", "")
            logs = "अभी तक कोई आउटपुट या एरर नहीं है।"
            if log_path and os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                    if content:
                        logs = content[-1200:]
            await query.edit_message_text(
                f"📜 <b>{html.escape(info['clean_name'])} के लाइव लॉग्स:</b>\n"
                f"<pre>{html.escape(logs)}</pre>\n\n"
                f"{build_live_message(file_id)}",
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "restart":
            start_python_bot(file_id)
            await query.answer("🔄 बॉट सफलतापूर्वक रीस्टार्ट हो गया!", show_alert=True)
            await query.edit_message_text(
                build_live_message(file_id, extra_header="🔄 <b>बॉट अभी रीस्टार्ट किया गया है!</b>"),
                reply_markup=get_file_action_keyboard(file_id),
                parse_mode="HTML"
            )

        elif action == "del":
            clean_name = info["clean_name"]
            had_deps = list(info.get("deps", []))
            delete_file_and_process(file_id)
            extra_note = f"\n🧹 अनइंस्टॉल की गई लाइब्रेरी: <code>{', '.join(had_deps)}</code>" if had_deps else ""
            await query.answer("🗑️ फाइल डिलीट कर दी गई!")
            await query.edit_message_text(
                f"🗑️ <b>{html.escape(clean_name)}</b> सफलता से डिलीट कर दी गई!{extra_note}",
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"Callback Error: {e}")
        await query.answer("⚠️ प्रोसेस किया गया।")

# ==================== AUTO-CRASH MONITOR ====================

async def monitor_crashed_bots(context: ContextTypes.DEFAULT_TYPE):
    """अगर कोई होस्टेड Python बॉट अचानक क्रैश होता है, तो यूजर को तुरंत मैसेज और सेम बटन भेजता है"""
    for fid, proc in list(running_bots.items()):
        info = files_db.get(fid)
        if not info:
            continue
        if proc.poll() is not None and not info.get("crash_notified", False):
            info["crash_notified"] = True
            save_db()
            err_tail = "No error output."
            if info.get("log_path") and os.path.exists(info["log_path"]):
                with open(info["log_path"], "r", encoding="utf-8", errors="ignore") as f:
                    err_tail = f.read().strip()[-800:] or "Process exited."

            alert_msg = (
                f"🚨 <b>Auto-Crash Alert!</b>\n"
                f"आपका बॉट <b>{html.escape(info['clean_name'])}</b> अचानक बंद हो गया है!\n\n"
                f"📜 <b>आखिरी एरर लॉग:</b>\n<pre>{html.escape(err_tail)}</pre>\n\n"
                f"{build_live_message(fid)}"
            )
            try:
                await context.bot.send_message(
                    chat_id=info["owner"],
                    text=alert_msg,
                    reply_markup=get_file_action_keyboard(fid),
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Crash alert error: {e}")

# ==================== MAIN RUNNER ====================

def main():
    load_db()
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # हर 20 सेकंड में चेक करेगा कि कोई सब-बॉट क्रैश तो नहीं हुआ
    if app.job_queue:
        app.job_queue.run_repeating(monitor_crashed_bots, interval=20, first=15)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myfiles", myfiles_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("cleanup", cleanup_cmd))

    app.add_handler(
        MessageHandler(
            filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
            handle_document
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("🚀 Ultimate Hosting Hub Bot Running 24/7...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
