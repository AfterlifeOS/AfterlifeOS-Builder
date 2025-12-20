import os
import sys
import asyncio

# === CUSTOM LIBRARY LOADER (MUST BE FIRST) ===
custom_lib_path = os.path.expanduser("~/pylib")
if os.path.isdir(custom_lib_path):
    if custom_lib_path not in sys.path:
        sys.path.insert(0, custom_lib_path)
        print(f"[INIT] Loading custom libraries from: {custom_lib_path}")

# === IMPORTS ===
import redis
import jenkins
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from dotenv import load_dotenv

# Import Utils
from utils import BOT_TOKEN, REDIS_URL, JENKINS_URL, JENKINS_USER, JENKINS_TOKEN

# Import Handlers
from handlers.ota import (
    post_command, set_banner, remove_banner, view_banner, 
    handle_notes_reply, handle_ota_callbacks
)
from handlers.jenkins import (
    build_command, status_command, quota_command, cancel_command,
    handle_jenkins_callbacks
)
from handlers.admin import add_user_command, remove_user_command, set_role_command, add_quota_command
from handlers.general import start_command, help_command, list_users_command

def get_jenkins_server():
    if not JENKINS_URL: return None
    try:
        s = jenkins.Jenkins(JENKINS_URL, username=JENKINS_USER, password=JENKINS_TOKEN)
        print(f"[INIT] Jenkins Connected: {s.get_whoami()['fullName']}")
        return s
    except Exception as e:
        print(f"[ERROR] Jenkins: {e}")
        return None

async def main():
    # Load env explicitly if needed, though utils.py does it too
    if not BOT_TOKEN or not REDIS_URL:
        print("[ERROR] Config Missing (BOT_TOKEN or REDIS_URL). Check private.env")
        return

    # 1. Init Connections
    redis_client = None
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print("[INIT] Redis Connected.")
    except Exception as e:
        print(f"[ERROR] Redis: {e}")
        return

    jenkins_server = get_jenkins_server()

    # 2. Build App
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Inject dependencies into bot_data
    app.bot_data["redis"] = redis_client
    app.bot_data["jenkins"] = jenkins_server

    # 3. Register Handlers
    
    # --- GENERAL HANDLERS ---
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("listuser", list_users_command))

    # --- ADMIN HANDLERS ---
    app.add_handler(CommandHandler("adduser", add_user_command))
    app.add_handler(CommandHandler("removeuser", remove_user_command))
    app.add_handler(CommandHandler("setrole", set_role_command))
    app.add_handler(CommandHandler("addquota", add_quota_command))

    # --- JENKINS HANDLERS ---
    app.add_handler(CommandHandler("build", build_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("quota", quota_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    # Regex pattern for Jenkins Callbacks (starts with build_)
    app.add_handler(CallbackQueryHandler(handle_jenkins_callbacks, pattern=r"^(build_).*"))

    # --- OTA HANDLERS ---
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("setbanner", set_banner))
    app.add_handler(CommandHandler("removebanner", remove_banner))
    app.add_handler(CommandHandler("banner", view_banner))
    
    # Notes reply handler (Text reply to bot's prompt)
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, handle_notes_reply))
    
    # Regex pattern for OTA Callbacks (notes_, confirm_, cancel_)
    app.add_handler(CallbackQueryHandler(handle_ota_callbacks, pattern=r"^(notes_|confirm_|cancel_).*"))

    # 4. Run Loop
    print("Bot is Running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    try:
        # Keep running until interrupted
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        # Graceful Shutdown
        print("Shutting down...")
        if redis_client: 
            redis_client.close()
            print("Redis closed.")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        print("Bot Stopped.")

if __name__ == "__main__":
    asyncio.run(main())