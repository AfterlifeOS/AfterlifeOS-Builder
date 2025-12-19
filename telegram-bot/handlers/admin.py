from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime, timezone
from utils import load_db, commit_db_to_github, ADMIN_USER_IDS, ROLE_ADMIN, ROLE_USER

async def add_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sender_id = user.id
    
    # --- 1. Check Permissions ---
    # Allow if sender is in ENV ADMIN list OR has 'admin' role in DB
    is_env_admin = sender_id in ADMIN_USER_IDS
    
    db = load_db()
    user_data = db.get("users", {}).get(str(sender_id), {})
    is_db_admin = user_data.get("role") == ROLE_ADMIN
    
    if not (is_env_admin or is_db_admin):
        await update.message.reply_text("⛔ **Access Denied:** You are not an admin.")
        return

    # --- 2. Parse Arguments ---
    # Usage: /adduser <ID> <Username> [role]
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ **Usage:** `/adduser <TelegramID> <Username> [role]`\n"
            "Example: `/adduser 123456789 user123 admin`",
            parse_mode="Markdown"
        )
        return

    target_id = args[0]
    target_username = args[1]
    target_role = args[2].lower() if len(args) > 2 else ROLE_USER
    
    # Validate Role
    if target_role not in [ROLE_ADMIN, ROLE_USER]:
        await update.message.reply_text(f"⚠️ Invalid role. Use `{ROLE_ADMIN}` or `{ROLE_USER}`.", parse_mode="Markdown")
        return

    # --- 3. Prepare Data ---
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    new_user_data = {
        "username": target_username,
        "role": target_role,
        "last_build_date": today_utc,
        "daily_count": 0
    }
    
    # --- 4. Update & Save ---
    if "users" not in db: db["users"] = {}
    
    db["users"][str(target_id)] = new_user_data
    
    status_msg = await update.message.reply_text("⏳ Syncing to GitHub...")
    
    commit_msg = f"database: Add {target_username} to database as {target_role}"
    if commit_db_to_github(db, commit_msg):
        msg = (
            f"✅ **User Added/Updated**\n\n"
            f"🆔 **ID:** `{target_id}`\n"
            f"👤 **Name:** `{target_username}`\n"
            f"🔰 **Role:** `{target_role}`\n"
            f"📅 **Date:** `{today_utc}` (UTC)\n"
            f"☁️ **Synced:** GitHub"
        )
        await status_msg.edit_text(msg, parse_mode="Markdown")
    else:
        await status_msg.edit_text("❌ Failed to sync to GitHub. Check logs.")

async def remove_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sender_id = user.id
    
    # --- 1. Check Permissions ---
    is_env_admin = sender_id in ADMIN_USER_IDS
    db = load_db()
    user_data = db.get("users", {}).get(str(sender_id), {})
    is_db_admin = user_data.get("role") == ROLE_ADMIN
    
    if not (is_env_admin or is_db_admin):
        await update.message.reply_text("⛔ **Access Denied:** You are not an admin.")
        return

    # --- 2. Parse Arguments ---
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "⚠️ **Usage:** `/removeuser <TelegramID>`\n"
            "Example: `/removeuser 123456789`",
            parse_mode="Markdown"
        )
        return

    target_id = args[0]
    
    if "users" not in db or target_id not in db["users"]:
        await update.message.reply_text(f"❌ User ID `{target_id}` not found in database.", parse_mode="Markdown")
        return

    # --- 3. Process Removal ---
    target_username = db["users"][target_id].get("username", "Unknown")
    del db["users"][target_id]
    
    status_msg = await update.message.reply_text("⏳ Syncing removal to GitHub...")
    
    commit_msg = f"database: Remove {target_username} from database"
    if commit_db_to_github(db, commit_msg):
        msg = (
            f"✅ **User Removed**\n\n"
            f"🆔 **ID:** `{target_id}`\n"
            f"👤 **Name:** `{target_username}`\n"
            f"🗑 **Action:** Removed from DB\n"
            f"☁️ **Synced:** GitHub"
        )
        await status_msg.edit_text(msg, parse_mode="Markdown")
    else:
        await status_msg.edit_text("❌ Failed to sync to GitHub. Check logs.")
