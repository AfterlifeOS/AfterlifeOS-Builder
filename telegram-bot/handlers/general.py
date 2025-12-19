from telegram import Update
from telegram.ext import ContextTypes
from utils import ADMIN_USER_IDS, load_db, ROLE_ADMIN

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to AfterlifeOS Build Bot!**\n\n"
        "I can help you manage Jenkins builds and OTA posts.\n"
        "Type `/help` to see available commands.",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # Check Admin Status
    is_env_admin = uid in ADMIN_USER_IDS
    db = load_db()
    user_data = db.get("users", {}).get(str(uid), {})
    is_db_admin = user_data.get("role") == ROLE_ADMIN
    is_admin = is_env_admin or is_db_admin

    help_text = (
        "🤖 **AfterlifeOS Bot Help**\n\n"
        "**👤 User Commands:**\n"
        "`/build <device> [manifest_url]` - Start a new build menu.\n"
        "`/cancel <BuildID>` - Cancel your running build.\n"
        "`/quota` - Check your daily build quota.\n"
        "`/status` - View current Jenkins status.\n"
        "`/banner <device>` - View OTA banner for a device.\n\n"
    )

    if is_admin:
        help_text += (
            "**🛡️ Admin Commands:**\n"
            "`/adduser <ID> <Name> [role]` - Add/Update a user in DB.\n"
            "`/removeuser <ID>` - Remove a user from DB.\n"
            "`/post <device>` - Post OTA update to channel.\n"
            "`/setbanner <device> <image>` - Set banner (Reply to image).\n"
            "`/removebanner <device>` - Remove banner.\n"
            "_(Admins have unlimited quota and can cancel any build)_"
        )
    else:
        help_text += "_Request admin access for more features._"

    await update.message.reply_text(help_text, parse_mode="Markdown")
