from telegram import Update
from telegram.ext import ContextTypes
from utils import ADMIN_USER_IDS, load_db, ROLE_ADMIN, ROLE_USER, ROLE_OWNER

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    users = db.get("users", {})
    
    if not users:
        await update.message.reply_text("📂 Database is empty.")
        return

    msg = "📋 **Registered Users**\n\n"
    
    # Sort by role priority (Owner > Admin > User) then Username
    def sort_key(item):
        uid, data = item
        role = data.get("role", ROLE_USER)
        priority = {ROLE_OWNER: 0, ROLE_ADMIN: 1, ROLE_USER: 2}.get(role, 3)
        return (priority, data.get("username", "").lower())

    sorted_users = sorted(users.items(), key=sort_key)

    for uid, data in sorted_users:
        username = data.get("username", "Unknown")
        role = data.get("role", ROLE_USER)
        
        icon = "👤"
        if role == ROLE_ADMIN: icon = "🛡️"
        if role == ROLE_OWNER: icon = "👑"
        
        msg += f"{icon} `{username}` (`{uid}`) - **{role.upper()}**\n"

    # Split message if too long (Telegram limit ~4096 chars)
    if len(msg) > 4000:
        # Simple splitting for now, sending multiple messages
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to AfterlifeOS Build Bot!**\n\n"
        "I can help you manage Jenkins builds and OTA posts.\n"
        "Type `/help` to see available commands.",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    
    # Load DB & Check Role
    db = load_db()
    user_data = db.get("users", {}).get(str(uid), {})
    role = user_data.get("role", ROLE_USER)
    
    is_owner = (role == ROLE_OWNER)
    is_db_admin = (role == ROLE_ADMIN)
    is_env_admin = uid in ADMIN_USER_IDS
    
    is_admin = is_env_admin or is_db_admin or is_owner

    help_text = (
        "🤖 **AfterlifeOS Bot Help**\n\n"
        "**👤 User Commands:**\n"
        "`/build <device> [manifest_url]` - Start a new build menu.\n"
        "`/cancel <BuildID>` - Cancel your running build.\n"
        "`/quota` - Check your daily build quota.\n"
        "`/status` - View current Jenkins status.\n"
        "`/banner` - View OTA banner.\n"
        "`/listuser` - List all registered users.\n\n"
    )

    if is_admin:
        help_text += (
            "**🛡️ Admin Commands:**\n"
            "`/adduser <ID> <Name> [role]` - Add/Update a user in DB.\n"
            "`/removeuser <ID>` - Remove a user from DB.\n"
            "`/post <device>` - Post OTA update to channel.\n"
            "`/setbanner` - Set banner (Reply to image).\n"
            "`/removebanner` - Remove banner.\n"
            "_(Admins and Owner have unlimited quota and can cancel any build)_\n\n"
        )
    
    if is_owner:
        help_text += (
            "**👑 Owner Commands:**\n"
            "`/setrole <ID> <role>` - Promote/Demote users (admin/user).\n"
        )
    elif not is_admin:
        help_text += "_Request admin access for more features._"

    await update.message.reply_text(help_text, parse_mode="Markdown")
