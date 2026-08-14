import os

# Render के Environment Variables से ऑटोमैटिक टोकन और एडमिन आईडी लोड होगी
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
ADMIN_IDS = [int(i) for i in os.environ.get("ADMIN_IDS", "123456789").split(",") if i.isdigit()]

STORAGE_DIR = os.path.join(os.getcwd(), "storage")
if not os.path.exists(STORAGE_DIR):
    os.makedirs(STORAGE_DIR)

def is_admin(user_id):
    return user_id in ADMIN_IDS
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
