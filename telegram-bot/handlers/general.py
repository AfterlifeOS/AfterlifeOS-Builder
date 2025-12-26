from telegram import Update
from telegram.ext import ContextTypes
from utils import ADMIN_USER_IDS, load_db, ROLE_ADMIN, ROLE_USER, ROLE_OWNER, restricted_command

@restricted_command
async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    users = db.get("users", {})
    
    if not users:
        await update.message.reply_text("📂 Database is empty.")
        return

    # Grouping
    owners, admins, regular_users = [], [], []
    for uid, data in users.items():
        role = data.get("role", ROLE_USER)
        entry = (data.get("username", "Unknown"), uid)
        
        if role == ROLE_OWNER: owners.append(entry)
        elif role == ROLE_ADMIN: admins.append(entry)
        else: regular_users.append(entry)

    msg = ""

    blocks = []
    if owners: blocks.append(('Owner', owners, '👑'))
    if admins: blocks.append(('Admin', admins, '🛡'))
    if regular_users: blocks.append(('User', regular_users, '👤'))

    for title, items, icon in blocks:
        # Title is the Root of this block's tree
        msg += f"{icon} **{title}s**\n"
        
        items.sort(key=lambda x: x[0].lower())
        for j, (name, uid) in enumerate(items):
            is_last_item = (j == len(items) - 1)
            sub_branch = "└" if is_last_item else "├"
            
            msg += f"{sub_branch} `{name}` (`{uid}`)\n"
        
        # Add spacing between blocks
        msg += "\n"

    if not msg:
        msg = "No users found."

    await update.message.reply_text(msg.strip(), parse_mode="Markdown")

@restricted_command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 **Welcome to AfterlifeOS Build Bot!**\n\n"
        "I can help you manage Jenkins builds and OTA posts.\n"
        "Type `/help` to see available commands.",
        parse_mode="Markdown"
    )

@restricted_command
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
        "`/cancel <RunID>` - Cancel a running build (ID from /status).\n"
        "`/quota` - Check your daily build quota.\n"
        "`/status` - View current build queue.\n"
        "`/post <device>` - Post OTA update to channel.\n"
        "`/banner` - View OTA banner.\n"
        "`/listuser` - List all registered users.\n\n"
    )

    if is_admin:
        help_text += (
            "**🛡️ Admin Commands:**\n"
            "`/adduser <ID> <Name> [role]` - Add/Update a user in DB.\n"
            "`/removeuser <ID>` - Remove a user from DB.\n"
            "`/setbanner` - Set banner (Reply to image).\n"
            "`/removebanner` - Remove banner.\n"
            "_(Admins and Owner have unlimited quota and can cancel any build)_\n\n"
        )
    
    if is_owner:
        help_text += (
            "**👑 Owner Commands:**\n"
            "`/setrole <ID> <role>` - Promote/Demote users (admin/user).\n"
            "`/addquota <User> <Amt>` - Add extra quota (Owner Only).\n"
        )
    elif not is_admin:
        help_text += "_Request admin access for more features._"

    await update.message.reply_text(help_text, parse_mode="Markdown")
