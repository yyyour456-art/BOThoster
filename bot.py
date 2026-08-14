import os
import sys
import time
import threading
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

from config import BOT_TOKEN, ADMIN_IDS, STORAGE_DIR, is_admin
from web_server import run_web_server, keep_alive
from user_manager import (
    running_bots, file_expiry, file_owners, waiting_for_custom, 
    delete_file_and_process, cleanup_files
)

# ऑटो-क्लीनअप और ऑटो-पिंग
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_files, 'interval', minutes=1)
scheduler.add_job(keep_alive, 'interval', minutes=10)
scheduler.start()

def get_base_url():
    # Render का URL अपने आप उठा लेगा
    return os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_tag = " (👑 Admin)" if is_admin(user_id) else ""
    
    await update.message.reply_text(
        f"👋 **होस्टिंग हब में आपका स्वागत है!{admin_tag}**\n\n"
        "📁 मुझे कोई भी फाइल (.html, .py, .png, .mp4 आदि) भेजें।\n"
        "मैं उसे 24/7 वेब लिंक पर लाइव कर दूंगा।\n\n"
        "📌 **कमांड्स:**\n"
        "• `/myfiles` - आपकी फाइल्स\n"
        "• `/cleanup` - मैन्युअल क्लीनअप\n"
        + ("• `/admin` - एडमिन पैनल\n" if is_admin(user_id) else ""),
        parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in waiting_for_custom:
        filename = waiting_for_custom[user_id]
        text = update.message.text
        if text and text.isdigit():
            days = int(text)
            file_expiry[filename] = time.time() + (days * 86400)
            file_owners[filename] = user_id
            del waiting_for_custom[user_id]
            
            clean_name = filename.split("_", 1)[-1] if "_" in filename else filename
            msg = f"✅ **{clean_name}** लाइव हो गई!\n\n🔗 **डायरेक्ट लिंक:** {get_base_url()}/files/{filename}\n⏱️ **समय:** {days} दिन"
            
            if filename.endswith(".py"):
                proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
                running_bots[filename] = proc
                msg += f"\n🤖 **सब-बॉट चालू हो गया!**"
                
            await update.message.reply_text(msg, parse_mode="Markdown")
            return
        else:
            await update.message.reply_text("⚠️ कृपया केवल संख्या (दिनों की संख्या) भेजें।")
            return

    if update.message.document:
        raw_filename = update.message.document.file_name
        file_obj = await context.bot.get_file(update.message.document.file_id)
    elif update.message.photo:
        raw_filename = f"photo_{int(time.time())}.jpg"
        file_obj = await context.bot.get_file(update.message.photo[-1].file_id)
    else:
        return

    filename = f"{user_id}_{raw_filename}"
    await file_obj.download_to_drive(os.path.join(STORAGE_DIR, filename))
    file_owners[filename] = user_id

    keyboard = [
        [InlineKeyboardButton("⏱️ 1 घंटा", callback_data=f"t_3600_{filename}"), InlineKeyboardButton("⏱️ 1 दिन", callback_data=f"t_86400_{filename}")],
        [InlineKeyboardButton("⏱️ 7 दिन", callback_data=f"t_604800_{filename}"), InlineKeyboardButton("⏱️ 30 दिन", callback_data=f"t_2592000_{filename}")],
        [InlineKeyboardButton("♾️ परमानेंट", callback_data=f"t_perm_{filename}"), InlineKeyboardButton("✏️ कस्टम दिन", callback_data=f"t_custom_{filename}")]
    ]

    await update.message.reply_text(
        f"📁 **फाइल मिली:** `{raw_filename}`\n\n⏱️ कितने समय के लिए होस्ट करना है?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data.startswith("t_"):
        parts = data.split("_", 2)
        time_type = parts[1]
        filename = parts[2]

        if time_type == "custom":
            waiting_for_custom[user_id] = filename
            await query.edit_message_text("✏️ दिनों की संख्या लिख कर भेजें:")
            return

        if time_type == "perm":
            file_expiry[filename] = -1
            time_str = "♾️ परमानेंट"
        else:
            seconds = int(time_type)
            file_expiry[filename] = time.time() + seconds
            time_str = f"{seconds // 3600} घंटे/दिन"

        clean_name = filename.split("_", 1)[-1] if "_" in filename else filename
        msg = f"✅ **{clean_name}** लाइव है!\n\n🔗 **डायरेक्ट लिंक:** {get_base_url()}/files/{filename}\n⏱️ **समय:** {time_str}"

        if filename.endswith(".py"):
            if filename in running_bots:
                running_bots[filename].terminate()
            proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
            running_bots[filename] = proc
            msg += f"\n🤖 **सब-बॉट लाइव हो गया!**"

        keyboard = [[InlineKeyboardButton("🗑️ डिलीट करें", callback_data=f"del_{filename}")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("del_"):
        filename = data.replace("del_", "")
        if file_owners.get(filename) == user_id or is_admin(user_id):
            delete_file_and_process(filename)
            await query.edit_message_text("🗑️ फाइल डिलीट कर दी गई!")
        else:
            await query.edit_message_text("⛔ यह आपकी फाइल नहीं है।")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_files = [f for f, owner in file_owners.items() if owner == user_id]

    if not user_files:
        await update.message.reply_text("📂 आपकी कोई फाइल होस्ट नहीं है।")
        return

    msg = "📁 **आपकी फाइल्स:**\n\n"
    keyboard = []

    for fname in user_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"📄 `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton("🔗 View", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    all_files = os.listdir(STORAGE_DIR)
    msg = f"👑 **एडमिन पैनल**\n\n📁 कुल फाइल्स: `{len(all_files)}`\n\n"
    keyboard = []

    for fname in all_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 {clean_name[:10]}", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del_{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="Markdown")

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_files()
    await update.message.reply_text("🧹 क्लीनअप पूरा हुआ!")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myfiles", myfiles))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cleanup", manual_cleanup))
    app.add_handler(MessageHandler(filters.DOCUMENT | filters.PHOTO | filters.TEXT, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
