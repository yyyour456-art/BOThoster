import os
import sys
import time
import threading
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler

# Import local modules
from config import BOT_TOKEN, ADMIN_IDS, STORAGE_DIR, is_admin
from web_server import run_web_server, keep_alive
from user_manager import (
    running_bots, file_expiry, file_owners, waiting_for_custom, 
    delete_file_and_process, cleanup_files
)

# Scheduler setup
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_files, 'interval', minutes=1)
scheduler.add_job(keep_alive, 'interval', minutes=10)
scheduler.start()

def get_base_url():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    return url if url else "https://bothoster-0ch7.onrender.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_tag = " (👑 Admin)" if is_admin(user_id) else ""
    await update.message.reply_text(
        f"👋 **होस्टिंग हब में आपका स्वागत है!{admin_tag}**\n\n"
        "📁 मुझे कोई भी फाइल भेजें, मैं उसे 24/7 वेब लिंक पर लाइव कर दूंगा।",
        parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
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
            [InlineKeyboardButton("⏱️ 1 घंटा", callback_data=f"time|3600|{filename}"), 
             InlineKeyboardButton("⏱️ 1 दिन", callback_data=f"time|86400|{filename}")],
            [InlineKeyboardButton("⏱️ 7 दिन", callback_data=f"time|604800|{filename}"), 
             InlineKeyboardButton("⏱️ 30 दिन", callback_data=f"time|2592000|{filename}")],
            [InlineKeyboardButton("♾️ परमानेंट", callback_data=f"time|perm|{filename}")]
        ]
        await update.message.reply_text(f"📁 **फाइल:** `{raw_filename}`\nसमय चुनें:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except Exception as e:
        print(f"Doc error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    try:
        if data.startswith("time|"):
            _, time_val, filename = data.split("|", 2)
            # यहाँ इंडेंटेशन बिल्कुल सीधा रखा गया है
            clean_name = filename.split("_", 1)[-1] if "_" in filename else filename
            
            if time_val == "perm":
                file_expiry[filename] = -1
            else:
                file_expiry[filename] = time.time() + int(time_val)

            base_url = get_base_url()
            link = f"{base_url}/files/{filename}"
            msg = f"✅ **{clean_name}** लाइव है!\n🔗 {link}"
            
            if filename.endswith(".py"):
                proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
                running_bots[filename] = proc
                msg += "\n\n🤖 **सब-बॉट चालू हो गया!**"
                
            await query.edit_message_text(msg, parse_mode="Markdown")

        elif data.startswith("del|"):
            _, filename = data.split("|", 1)
            if file_owners.get(filename) == user_id or is_admin(user_id):
                delete_file_and_process(filename)
                await query.edit_message_text("🗑️ फाइल डिलीट हो गई!")
    except Exception as e:
        print(f"Button error: {e}")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
            clean_name = filename.split("_", 1)[-1] if "_" in filename else filename
            base_url = get_base_url()
            link = f"{base_url}/files/{filename}"

            msg = (
                f"✅ **{clean_name}** सफलता से लाइव हो गई!\n\n"
                f"🔗 **डायरेक्ट वेब लिंक:**\n{link}\n\n"
                f"⏱️ **वैधता:** {time_str}"
            )

            if filename.endswith(".py"):
                if filename in running_bots:
                    try:
                        running_bots[filename].terminate()
                    except Exception as e:
                        print(f"Terminate error: {e}")
                proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
                running_bots[filename] = proc
                msg += "\n\n🤖 **सब-बॉट बैकग्राउंड में स्टार्ट हो गया!**"

            keyboard = [[InlineKeyboardButton("🗑️ फाइल डिलीट करें", callback_data=f"del|{filename}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data.startswith("del|"):
            parts = data.split("|", 1)
            filename = parts[1]
            if file_owners.get(filename) == user_id or is_admin(user_id):
                delete_file_and_process(filename)
                await query.edit_message_text("🗑️ फाइल सफलता से डिलीट कर दी गई!")
            else:
                await query.edit_message_text("⛔ यह आपकी फाइल नहीं है।")

    except Exception as e:
        print(f"Error in button_callback: {e}")
        await query.message.reply_text("❌ बटन प्रोसेस करने में त्रुटि हुई।")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_files = [f for f, owner in file_owners.items() if owner == user_id]

    if not user_files:
        await update.message.reply_text("📂 आपकी कोई फाइल होस्ट नहीं है।")
        return

    msg = "📁 **आपकी एक्टिव फाइल्स:**\n\n"
    keyboard = []

    for fname in user_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View File", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    all_files = os.listdir(STORAGE_DIR)
    if not all_files:
        await update.message.reply_text("👑 **एडमिन पैनल:** कोई फाइल नहीं है।")
        return

    msg = f"👑 **एडमिन पैनल**\n\n📁 कुल फाइल्स: `{len(all_files)}`\n\n"
    keyboard = []

    for fname in all_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="Markdown")

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_files()
    await update.message.reply_text("🧹 मैन्युअल क्लीनअप पूरा हुआ!")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myfiles", myfiles))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cleanup", manual_cleanup))
    
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
            clean_name = filename.split("_", 1)[-1] if "_" in filename else filename
            base_url = get_base_url()
            link = f"{base_url}/files/{filename}"

            msg = (
                f"✅ **{clean_name}** सफलता से लाइव हो गई!\n\n"
                f"🔗 **डायरेक्ट वेब लिंक:**\n{link}\n\n"
                f"⏱️ **वैधता:** {time_str}"
            )

            if filename.endswith(".py"):
                if filename in running_bots:
                    try:
                        running_bots[filename].terminate()
                    except Exception as e:
                        print(f"Subprocess terminate error: {e}")
                proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
                running_bots[filename] = proc
                msg += "\n\n🤖 **सब-बॉट बैकग्राउंड में स्टार्ट हो गया!**"

            keyboard = [[InlineKeyboardButton("🗑️ फाइल डिलीट करें", callback_data=f"del|{filename}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data.startswith("del|"):
            _, filename = data.split("|", 1)
            if file_owners.get(filename) == user_id or is_admin(user_id):
                delete_file_and_process(filename)
                await query.edit_message_text("🗑️ फाइल सफलता से डिलीट कर दी गई!")
            else:
                await query.edit_message_text("⛔ यह आपकी फाइल नहीं है।")

    except Exception as e:
        print(f"Error in button_callback: {e}")
        await query.message.reply_text("❌ बटन प्रोसेस करने में त्रुटि हुई।")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_files = [f for f, owner in file_owners.items() if owner == user_id]

    if not user_files:
        await update.message.reply_text("📂 आपकी कोई फाइल होस्ट नहीं है।")
        return

    msg = "📁 **आपकी एक्टिव फाइल्स:**\n\n"
    keyboard = []

    for fname in user_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View File", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    all_files = os.listdir(STORAGE_DIR)
    if not all_files:
        await update.message.reply_text("👑 **एडमिन पैनल:** कोई फाइल नहीं है।")
        return

    msg = f"👑 **एडमिन पैनल**\n\n📁 कुल फाइल्स: `{len(all_files)}`\n\n"
    keyboard = []

    for fname in all_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="Markdown")

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_files()
    await update.message.reply_text("🧹 मैन्युअल क्लीनअप पूरा हुआ!")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myfiles", myfiles))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cleanup", manual_cleanup))
    
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
            clean_name = filename.split("_", 1)[-1] if "_" in filename else filename
            base_url = get_base_url()
            link = f"{base_url}/files/{filename}"

            msg = (
                f"✅ **{clean_name}** सफलता से लाइव हो गई!\n\n"
                f"🔗 **डायरेक्ट वेब लिंक:**\n{link}\n\n"
                f"⏱️ **वैधता:** {time_str}"
            )

            if filename.endswith(".py"):
                if filename in running_bots:
                    try:
                        running_bots[filename].terminate()
                    except:
                        pass
                proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
                running_bots[filename] = proc
                msg += "\n\n🤖 **सब-बॉट बैकग्राउंड में स्टार्ट हो गया!**"

            keyboard = [[InlineKeyboardButton("🗑️ फाइल डिलीट करें", callback_data=f"del|{filename}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data.startswith("del|"):
            _, filename = data.split("|", 1)
            if file_owners.get(filename) == user_id or is_admin(user_id):
                delete_file_and_process(filename)
                await query.edit_message_text("🗑️ फाइल सफलता से डिलीट कर दी गई!")
            else:
                await query.edit_message_text("⛔ यह आपकी फाइल नहीं है।")

    except Exception as e:
        print(f"Error in button_callback: {e}")
        await query.message.reply_text("❌ बटन प्रोसेस करने में त्रुटि हुई।")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_files = [f for f, owner in file_owners.items() if owner == user_id]

    if not user_files:
        await update.message.reply_text("📂 आपकी कोई फाइल होस्ट नहीं है।")
        return

    msg = "📁 **आपकी एक्टिव फाइल्स:**\n\n"
    keyboard = []

    for fname in user_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View File", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    all_files = os.listdir(STORAGE_DIR)
    if not all_files:
        await update.message.reply_text("👑 **एडमिन पैनल:** कोई फाइल नहीं है।")
        return

    msg = f"👑 **एडमिन पैनल**\n\n📁 कुल फाइल्स: `{len(all_files)}`\n\n"
    keyboard = []

    for fname in all_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="Markdown")

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_files()
    await update.message.reply_text("🧹 मैन्युअल क्लीनअप पूरा हुआ!")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myfiles", myfiles))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cleanup", manual_cleanup))
    
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()

            if filename.endswith(".py"):
                if filename in running_bots:
                    try:
                        running_bots[filename].terminate()
                    except:
                        pass
                proc = subprocess.Popen([sys.executable, os.path.join(STORAGE_DIR, filename)])
                running_bots[filename] = proc
                msg += "\n\n🤖 **सब-बॉट बैकग्राउंड में स्टार्ट हो गया!**"

            keyboard = [[InlineKeyboardButton("🗑️ फाइल डिलीट करें", callback_data=f"del|{filename}")]]
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

        elif data.startswith("del|"):
            _, filename = data.split("|", 1)
            if file_owners.get(filename) == user_id or is_admin(user_id):
                delete_file_and_process(filename)
                await query.edit_message_text("🗑️ फाइल सफलता से डिलीट कर दी गई!")
            else:
                await query.edit_message_text("⛔ यह आपकी फाइल नहीं है।")

    except Exception as e:
        print(f"Error in button_callback: {e}")
        await query.message.reply_text("❌ बटन प्रोसेस करने में त्रुटि हुई।")

async def myfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_files = [f for f, owner in file_owners.items() if owner == user_id]

    if not user_files:
        await update.message.reply_text("📂 आपकी कोई फाइल होस्ट नहीं है।")
        return

    msg = "📁 **आपकी एक्टिव फाइल्स:**\n\n"
    keyboard = []

    for fname in user_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View File", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    all_files = os.listdir(STORAGE_DIR)
    if not all_files:
        await update.message.reply_text("👑 **एडमिन पैनल:** कोई फाइल नहीं है।")
        return

    msg = f"👑 **एडमिन पैनल**\n\n📁 कुल फाइल्स: `{len(all_files)}`\n\n"
    keyboard = []

    for fname in all_files:
        clean_name = fname.split("_", 1)[-1] if "_" in fname else fname
        msg += f"• `{clean_name}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🔗 View", url=f"{get_base_url()}/files/{fname}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"del|{fname}")
        ])

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None, parse_mode="Markdown")

async def manual_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_files()
    await update.message.reply_text("🧹 मैन्युअल क्लीनअप पूरा हुआ!")

def main():
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myfiles", myfiles))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cleanup", manual_cleanup))
    
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_document))
    app.add_handler(CallbackQueryHandler(button_callback))

    print("Bot Running...")
    app.run_polling()

if __name__ == "__main__":
    main()
