import os
import sys

# === CUSTOM LIBRARY LOADER ===
custom_lib_path = os.path.expanduser("~/pylib")
if os.path.isdir(custom_lib_path):
    if custom_lib_path not in sys.path:
        sys.path.insert(0, custom_lib_path)
        print(f"[INIT] Loading custom libraries from: {custom_lib_path}")
else:
    print(f"[WARNING] Library directories {custom_lib_path} not found. Make sure its installed.")

import requests
import asyncio
import html
from datetime import datetime, timezone, timedelta
import re
import redis
import json
import subprocess
from functools import partial
import jenkins  # Jenkins API
import time

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot, ForceReply
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)
from telegram.constants import ParseMode
from dotenv import load_dotenv

# === CONFIGURATION ===
# Load private.env relative to this script's location
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, 'private.env')
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
REDIS_URL = os.environ.get("REDIS_URL")
STICKER_ID = os.environ.get("STICKER_ID")

# --- Jenkins Configuration ---
JENKINS_URL = os.environ.get("JENKINS_URL")
JENKINS_USER = os.environ.get("JENKINS_USER")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN")
JENKINS_JOB_NAME = os.environ.get("JENKINS_JOB_NAME", "Afterlife_Build") 

BASE_URL = "https://raw.githubusercontent.com/AfterlifeOS/device_afterlife_ota/refs/heads/16"
DONATE_URL = "https://t.me/donate_zero/6"
AFL_SUPPORT = "https://t.me/AfterLifeOS"
SOURCE_CHANGELOGS_URL = "https://afterlifeos.com/changelog/"

# === Testing Env ===
TEST_GROUP_ID = int(os.environ.get("TEST_GROUP_ID", "0"))
TEST_CHANNEL_ID = os.environ.get("TEST_CHANNEL_ID")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Allowed Chat (Legacy for OTA)
allowed_ids_str = os.environ.get("ALLOWED_CHAT_IDS", "")
temp_ids_list = allowed_ids_str.split(",")
ALLOWED_CHAT_IDS = []
for item in temp_ids_list:
    item_stripped = item.strip()
    if item_stripped:
        try: ALLOWED_CHAT_IDS.append(int(item_stripped))
        except: pass

if TEST_GROUP_ID != 0 and TEST_GROUP_ID not in ALLOWED_CHAT_IDS:
    ALLOWED_CHAT_IDS.append(TEST_GROUP_ID)

# Admin Users (Legacy for OTA)
admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
temp_admin_list = admin_ids_str.split(",")
ADMIN_USER_IDS = []
for item in temp_admin_list:
    item_stripped = item.strip()
    if item_stripped:
        try: ADMIN_USER_IDS.append(int(item_stripped))
        except: pass

# === DATABASE & QUOTA CONSTANTS ===
DB_FILE = "database.json"
MAX_QUOTA_USER = 5
ROLE_ADMIN = "admin"
ROLE_USER = "user"

# === BUILD CONFIGURATION OPTIONS ===
BUILD_OPTIONS = {
    'RELEASETYPE': ['user', 'userdebug', 'eng'],
    'GMS_VARIANT': ['Tree default', 'Full', 'Core', 'Basic', 'Vanilla'],
    'INSTALLCLEAN': ['Yes', 'No'],
    'FULLCLEAN': ['No', 'Yes'],
    'FSGEN': ['Enable', 'Disable'],
    'RELEASE_BUILD': ['No', 'Yes']
}

# === DATABASE FUNCTIONS ===
def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}, "last_reset_date": ""}
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Load DB failed: {e}")
        return {"users": {}, "last_reset_date": ""}

def save_db(data):
    try:
        with open(DB_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[ERROR] Save DB failed: {e}")

def get_user_data(user_id):
    db = load_db()
    return db["users"].get(str(user_id))

def check_access(user_id):
    """Returns (has_access, role, quota_left)"""
    user_data = get_user_data(user_id)
    if not user_data:
        return False, None, 0
    
    role = user_data.get("role", ROLE_USER)
    used = user_data.get("quota_used", 0)
    
    if role == ROLE_ADMIN:
        return True, role, 999
    
    left = MAX_QUOTA_USER - used
    if left > 0:
        return True, role, left
    else:
        return False, role, 0

def increment_quota(user_id, username):
    db = load_db()
    uid_str = str(user_id)
    if uid_str in db["users"]:
        db["users"][uid_str]["quota_used"] += 1
        db["users"][uid_str]["username"] = username
        save_db(db)
        # Trigger Git Push
        asyncio.create_task(git_quota_update(username))
        return True
    return False

# === GIT FUNCTIONS ===
def get_current_branch():
    try:
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except: return "main"

async def git_quota_update(username):
    branch = get_current_branch()
    commit_msg = f"quota: Update build quota for {username}"
    print(f"[GIT] Updating quota for {username}...")
    try:
        subprocess.run(['git', 'config', 'user.email', 'bot@jenkins.local'], check=False)
        subprocess.run(['git', 'config', 'user.name', 'Jenkins Bot'], check=False)
        subprocess.run(['git', 'add', DB_FILE], check=True)
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', branch], check=True)
        subprocess.run(['git', 'push', 'origin', branch], check=True)
        print(f"[GIT] Pushed.")
    except Exception as e:
        print(f"[GIT ERROR] {e}")

# === REDIS & JENKINS HELPERS ===
async def run_redis_command(redis_client, command_name, *args, **kwargs):
    try:
        command_method = getattr(redis_client, command_name)
        sync_call = partial(command_method, *args, **kwargs)
        return await asyncio.to_thread(sync_call)
    except Exception as e:
        print(f"[ERROR] Redis command '{command_name}' failed: {e}")
        return None

def get_jenkins_server():
    try:
        if not JENKINS_URL: return None
        return jenkins.Jenkins(JENKINS_URL, username=JENKINS_USER, password=JENKINS_TOKEN)
    except: return None

def convert_to_raw_url(url):
    if not url: return ""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "gitlab.com" in url and "/blob/" in url:
        return url.replace("/blob/", "/raw/")
    return url

# === OTA HELPERS (RESTORED ORIGINAL) ===
def format_date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%d %B %Y")

def fetch_rom_data(device_codename):
    url = f"{BASE_URL}/{device_codename}/updates.json"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            json_data = res.json()
            if "response" in json_data and json_data["response"]:
                j = json_data["response"][0]
                maintainer_link = j.get("telegram", "")
                if maintainer_link and not maintainer_link.startswith("http"):
                    maintainer_link = f"https://{maintainer_link}"
                
                return {
                    "device_codename": device_codename,
                    "device_name": j.get("device"),
                    "rom_name": "AfterlifeOS",
                    "version": j.get("version"),
                    "release_codename": j.get("codename"),
                    "download_url": j.get("download"),
                    "build_date": j.get("timestamp"),
                    "size": j.get("size"),
                    "build_type": j.get("buildtype"),
                    "maintainer_name": j.get("maintainer"),
                    "maintainer_link": maintainer_link, 
                    "support_group": j.get("forum"),
                }
    except Exception as e:
        print(f"[ERROR] Failed to fetch JSON {device_codename}: {e}")
    return None

def bytes_to_gb(size_bytes):
    if not isinstance(size_bytes, (int, float)) or size_bytes == 0:
        return "N/A"
    return f"{size_bytes / (1024 ** 3):.2f} GB"

def format_post(data, posted_by_username, notes_list=None):
    rom_name = data.get("rom_name", "AfterlifeOS")
    version = data.get("version", "Unknown")
    device_name = data.get("device_name", data['device_codename'])
    maintainer_name = data.get("maintainer_name", posted_by_username)
    maintainer_link = data.get("maintainer_link", f"https://t.me/{posted_by_username}")
    build_date = format_date(int(data['build_date'])) if data.get("build_date") else "Unknown"
    size = bytes_to_gb(data.get("size"))
    release_type = data.get("build_type", "unofficial").capitalize()
    device_codename = data['device_codename']
    device_codename_tag = f"#{data['device_codename']}"
    release_codename = data['release_codename'].capitalize() if data.get("release_codename") else ""
    release_codename_tag = f"#{data['release_codename']}" if data.get("release_codename") else ""

    post = (
        f"<b>{rom_name} v{version} {release_codename} | {release_type} | Android 16</b>\n"
        f"Supported Device: {device_name} - {device_codename}\n"
        f"Build date: {build_date}\n"
        f"Maintainer: <a href='{maintainer_link}'>{maintainer_name}</a>\n"
    )

    if notes_list:
        notes_section = "\n".join([f"- {note.lstrip('- ')}" for note in notes_list if note.strip()])
        if notes_section:
            post += f"\n<b>Notes:</b>\n{notes_section}\n"

    post += (
        f"\nThere's nothing special about my rom, you can skip if you don't like, or you can taste it.\n"
        f"Subscribe For More <a href='https://t.me/Afterlife_update'>AfterlifeOS</a>\n\n"
        f"Hope you all have a happy life\n"
        f"Thank you.\n"
    )

    post += f"\n#{rom_name} {device_codename_tag} {release_codename_tag} #NeverDie"
    return post

def build_keyboard(data):
    codename = data['device_codename']
    mt_support = data.get("support_group") or AFL_SUPPORT
    buttons = [
        [
            InlineKeyboardButton("Download", url=f"https://afterlifeos.com/device/{codename}/",),
            InlineKeyboardButton("Source Changelogs", url=SOURCE_CHANGELOGS_URL),
        ],
        [
            InlineKeyboardButton("Support Group", url=AFL_SUPPORT),
            InlineKeyboardButton("Donate", url=DONATE_URL),
        ],
        [
            InlineKeyboardButton("Device Support", url=mt_support)
        ],
    ]
    return InlineKeyboardMarkup(buttons)

def confirm_keyboard(device_codename, user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Post to Channel", callback_data=f"confirm_send:{device_codename}:{user_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_post:{user_id}")]
    ])

def ask_notes_keyboard(device_codename, user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, add notes", callback_data=f"notes_yes:{device_codename}:{user_id}")],
        [InlineKeyboardButton("No, continue", callback_data=f"notes_no:{device_codename}:{user_id}")]
    ])

# === OTA COMMANDS (RESTORED ORIGINAL) ===

async def set_banner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("Sorry, this command is only allowed in specific groups.")
        return
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this command.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("Usage: Reply to a photo with `/setbanner` to capture its ID.")
        return
    file_id = update.message.reply_to_message.photo[-1].file_id
    try:
        redis_client: redis.Redis = context.bot_data["redis"]
        await run_redis_command(redis_client, "set", "banner_file_id", file_id)
        await update.message.reply_text("✅ Banner ID set successfully.", parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"Failed to set banner in Redis: {e}")

async def remove_banner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if chat_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("Sorry, this command is only allowed in specific groups.")
        return
    if user_id not in ADMIN_USER_IDS:
        await update.message.reply_text("Sorry, you are not authorized to use this command.")
        return
    try:
        redis_client: redis.Redis = context.bot_data["redis"]
        await run_redis_command(redis_client, "delete", "banner_file_id")
        await update.message.reply_text("✅ Banner removed successfully.")
    except Exception as e:
        await update.message.reply_text(f"Failed to remove banner from Redis: {e}")

async def view_banner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("Sorry, this command is only allowed in specific groups.")
        return
    redis_client: redis.Redis = context.bot_data["redis"]
    banner_file_id = await run_redis_command(redis_client, "get", "banner_file_id")
    if banner_file_id:
        try:
            await update.message.reply_photo(photo=banner_file_id, caption="This is the currently used banner.")
        except Exception as e:
            await update.message.reply_text(f"Failed to send banner: {e}")
    else:
        await update.message.reply_text("Banner not set. Please set one using `/setbanner`.")

async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id 
    if chat_id not in ALLOWED_CHAT_IDS:
        await update.message.reply_text("Sorry, this command is only allowed in specific groups.")
        return
    if chat_id == TEST_GROUP_ID:
        if user_id != OWNER_ID:
            await update.message.reply_text("⛔ In this test group, only the Owner is allowed to post.")
            return
    else:
        if user_id not in ADMIN_USER_IDS:
            await update.message.reply_text("Sorry, you are not authorized to use this command.")
            return

    redis_client: redis.Redis = context.bot_data["redis"]
    banner_file_id = await run_redis_command(redis_client, "get", "banner_file_id")

    if not banner_file_id:
        await update.message.reply_text(f"⚠️ Banner not found.\nPlease set a banner using `/setbanner`.", parse_mode=ParseMode.HTML)
        return

    if not context.args:
        await update.message.reply_text("Usage:\n/post <codename>\nExample: /post surya")
        return

    device_codename = context.args[0]
    data = fetch_rom_data(device_codename)
    if not data:
        await update.message.reply_text(f"Failed to fetch data for <code>{device_codename}</code>.", parse_mode=ParseMode.HTML)
        return

    poster_username = data.get("maintainer_name", update.effective_user.username or update.effective_user.first_name)
    post_preview = format_post(data, poster_username, notes_list=None) 
    keyboard = ask_notes_keyboard(device_codename, update.effective_user.id)

    try:
        await update.message.reply_photo(
            photo=banner_file_id, 
            caption=post_preview,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
    except Exception as e:
        await update.message.reply_text(f"Failed to send preview: {e}")

async def handle_notes_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if 'awaiting_notes_for' not in context.user_data: return 
    state = context.user_data['awaiting_notes_for']
    
    if (update.message.reply_to_message and 
        update.message.reply_to_message.message_id == state['prompt_message_id'] and
        user_id == state['user_id']):

        notes_raw = update.message.text
        notes_safe = html.escape(notes_raw)
        notes_with_html_links = re.sub(r'\[(.*?)]\s*\(\s*(.*?)\s*\)', r'<a href="\2">\1</a>', notes_safe)
        notes_list = [f"- {line.strip()}" for line in notes_with_html_links.split("\n") if line.strip()]

        device_codename = state['device_codename']
        original_preview_message_id = state['original_preview_message_id']

        data = fetch_rom_data(device_codename)
        if not data:
            await update.message.reply_text("Error: Failed to re-fetch device data.")
            del context.user_data['awaiting_notes_for']
            return

        poster_username = data.get("maintainer_name", update.effective_user.first_name)
        post_with_notes = format_post(data, poster_username, notes_list)
        keyboard = confirm_keyboard(device_codename, user_id)

        try:
            await context.bot.edit_message_caption(
                chat_id=update.effective_chat.id,
                message_id=original_preview_message_id,
                caption=post_with_notes,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=state['prompt_message_id'])
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
        except Exception as e:
            await update.message.reply_text(f"Error updating post: {e}")
        finally:
            del context.user_data['awaiting_notes_for']

# === NEW JENKINS COMMANDS (WITH DB & QUOTA) ===

async def quota_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    if not user_data:
        await update.message.reply_text("⛔ Not registered.")
        return
    role = user_data.get("role", ROLE_USER)
    used = user_data.get("quota_used", 0)
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    delta = tomorrow - now
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    limit_str = "Unlimited" if role == ROLE_ADMIN else str(MAX_QUOTA_USER)
    msg = (f"<b>📊 Quota Status</b>\n👤 {update.effective_user.first_name}\n🏷 Role: {role.upper()}\n🔢 Used: {used} / {limit_str}\n⏳ Reset in: {hours}h {minutes}m (00:00 UTC)")
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user_data(user_id):
        await update.message.reply_text("⛔ Access Denied (Not in DB).")
        return
    server = context.bot_data.get("jenkins")
    if not server:
        await update.message.reply_text("⚠️ Jenkins disconnected.")
        return
    try:
        job_info = await asyncio.to_thread(server.get_job_info, JENKINS_JOB_NAME)
        last_build_number = job_info['lastBuild']['number']
        last_build_info = await asyncio.to_thread(server.get_build_info, JENKINS_JOB_NAME, last_build_number)
        msg = "<b>🔨 Jenkins Build Status</b>\n\n"
        if last_build_info['building']:
            duration = (datetime.now().timestamp() * 1000) - last_build_info['timestamp']
            duration_min = int((duration / 1000) / 60)
            params = {p['name']: p['value'] for p in last_build_info['actions'][0].get('parameters', [])}
            msg += f"🟢 <b>Building Now:</b> #{last_build_number}\n📱 Device: {params.get('DEVICE')}\n⏱ Time: {duration_min} mins\n🔗 <a href='{last_build_info['url']}console'>Console Output</a>\n"
        else:
            msg += f"💤 <b>Idle</b>. Last build (#{last_build_number}) finished.\nResult: {last_build_info['result']}\n"
        queue_info = await asyncio.to_thread(server.get_queue_info)
        if queue_info:
            msg += "\n<b>⏳ Queue:</b>\n"
            for item in queue_info:
                if 'task' in item and item['task']['name'] == JENKINS_JOB_NAME:
                    msg += f"- ID {item['id']}: Pending...\n"
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    has_access, role, quota_left = check_access(user_id)
    if not has_access:
        msg = "⛔ Quota Exceeded." if role else "⛔ Access Denied."
        await update.message.reply_text(msg)
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /build <device> [manifest_url]")
        return
    
    device = args[0]
    manifest_url = convert_to_raw_url(args[1]) if len(args) > 1 else ""
    
    params = {
        'DEVICE': device,
        'RELEASETYPE': 'user',
        'GMS_VARIANT': 'Tree default',
        'INSTALLCLEAN': 'Yes',
        'FULLCLEAN': 'No',
        'FSGEN': 'Enable',
        'RELEASE_BUILD': 'No',
        'LOCAL_MANIFEST_URL': manifest_url,
        'BUILD_USER': username
    }
    context.user_data['pending_build'] = params
    
    limit_info = "Unlimited" if role == ROLE_ADMIN else f"{quota_left} left"
    msg = (f"<b>🛠 Build Config</b>\n👤 {username} ({limit_info})\n📱 {device}\n\n<i>Adjust settings & Start.</i>")
    
    await update.message.reply_text(msg, reply_markup=get_build_menu_keyboard(params), parse_mode=ParseMode.HTML)

def get_build_menu_keyboard(params):
    def btn(l, k): return InlineKeyboardButton(f"{l}: {params[k]}", callback_data=f"build_set:{k}")
    return InlineKeyboardMarkup([
        [btn("Type", "RELEASETYPE"), btn("GMS", "GMS_VARIANT")],
        [btn("Clean", "INSTALLCLEAN"), btn("Full Clean", "FULLCLEAN")],
        [btn("FSGen", "FSGEN"), btn("Release", "RELEASE_BUILD")],
        [InlineKeyboardButton("✅ START", callback_data="build_action:start"), InlineKeyboardButton("❌ CANCEL", callback_data="build_action:cancel")]
    ])

# === UNIFIED CALLBACK HANDLER ===
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    username = query.from_user.username or query.from_user.first_name
    redis_client = context.bot_data["redis"]

    # 1. BUILD ACTIONS
    if query.data.startswith("build_action:"):
        action = query.data.split(":")[1]
        if action == "cancel":
            await query.edit_message_text("❌ Cancelled.")
            if 'pending_build' in context.user_data: del context.user_data['pending_build']
            return
        if action == "start":
            has_access, role, quota_left = check_access(user_id)
            if not has_access:
                await query.answer("Quota exceeded!", show_alert=True)
                return
            params = context.user_data.get('pending_build')
            if not params:
                await query.edit_message_text("⚠️ Expired.")
                return
            server = context.bot_data.get("jenkins")
            try:
                await asyncio.to_thread(server.build_job, JENKINS_JOB_NAME, parameters=params)
                if role != ROLE_ADMIN:
                    increment_quota(user_id, username)
                await query.edit_message_text(f"✅ <b>Build Queued!</b>\nDevice: {params['DEVICE']}", parse_mode=ParseMode.HTML)
            except Exception as e:
                await query.edit_message_text(f"❌ Failed: {e}")
            return

    # 2. BUILD SETTINGS (CYCLE)
    if query.data.startswith("build_set:"):
        key = query.data.split(":")[1]
        params = context.user_data.get('pending_build')
        if not params:
            await query.answer("Expired.", show_alert=True)
            return
        if key in BUILD_OPTIONS:
            opts = BUILD_OPTIONS[key]
            try: params[key] = opts[(opts.index(params[key]) + 1) % len(opts)]
            except: params[key] = opts[0]
            context.user_data['pending_build'] = params
            try: await query.edit_message_reply_markup(get_build_menu_keyboard(params))
            except: pass
        await query.answer()
        return

    # 3. OTA ACTIONS (RESTORED ORIGINAL)
    if query.data.startswith("notes_yes:"):
        try: _, device_codename, expected_user_id = query.data.split(":", 2)
        except: return
        if str(user_id) != expected_user_id:
            await query.answer("Not allowed.", show_alert=True)
            return
        await query.answer()
        await query.edit_message_reply_markup(None)
        prompt_msg = await query.message.reply_text(
            "Reply with notes\\. For add URL text follow this\nFormat: `[text] (url)`",
            reply_markup=ForceReply(selective=True), parse_mode=ParseMode.MARKDOWN_V2
        )
        context.user_data['awaiting_notes_for'] = {
            'original_preview_message_id': query.message.message_id,
            'prompt_message_id': prompt_msg.message_id,
            'device_codename': device_codename,
            'user_id': user_id
        }
        return

    if query.data.startswith("notes_no:"):
        try: _, device_codename, expected_user_id = query.data.split(":", 2)
        except: return
        if str(user_id) != expected_user_id: return
        await query.answer()
        await query.edit_message_reply_markup(confirm_keyboard(device_codename, user_id))
        return

    if query.data.startswith("cancel_post:"):
        try: expected_user_id = query.data.split(":")[-1]
        except: return
        if str(user_id) != expected_user_id: return
        await query.edit_message_reply_markup(None)
        await query.message.reply_text("❌ Canceled.")
        if 'awaiting_notes_for' in context.user_data: del context.user_data['awaiting_notes_for']
        return

    if query.data.startswith("confirm_send:"):
        try: _, device_codename, expected_user_id = query.data.split(":", 2)
        except: return
        if str(user_id) != expected_user_id: return
        
        current_chat_id = query.message.chat.id
        target_chat_id = CHANNEL_ID
        if current_chat_id == TEST_GROUP_ID:
            if TEST_CHANNEL_ID: target_chat_id = TEST_CHANNEL_ID

        banner_file_id = await run_redis_command(redis_client, "get", "banner_file_id")
        if not banner_file_id:
            await query.message.reply_text("Banner missing.")
            return

        data = fetch_rom_data(device_codename)
        if not data:
            await query.edit_message_text("Failed to fetch JSON.")
            return

        poster_username = data.get("maintainer_name", query.from_user.first_name)
        original_caption = query.message.caption_html
        notes_list_final = []
        if "<b>Notes:</b>" in original_caption:
            try:
                notes_part = original_caption.split("<b>Notes:</b>\n")[1]
                if "\n\n" in notes_part: notes_section = notes_part.split("\n\n")[0]
                else: notes_section = notes_part 
                notes_list_final = [line.lstrip('- ') for line in notes_section.split("\n") if line.strip()]
            except: pass

        msg = format_post(data, poster_username, notes_list_final)
        kb = build_keyboard(data)
        bot = Bot(token=BOT_TOKEN)

        await query.edit_message_reply_markup(None)
        
        if STICKER_ID:
            try:
                await bot.send_sticker(target_chat_id, STICKER_ID)
                await query.message.reply_text(f"Sticker sent. Waiting 30s...")
                await asyncio.sleep(30)
            except: pass

        try:
            await bot.send_photo(target_chat_id, banner_file_id, caption=msg, parse_mode=ParseMode.HTML, reply_markup=kb)
            await query.message.reply_text(f"✅ Sent to {target_chat_id}")
        except Exception as e:
            await query.message.reply_text(f"Failed: {e}")

# === RESET TASK ===
async def daily_reset_task():
    print("Reset Task Started.")
    while True:
        now = datetime.now(timezone.utc)
        db = load_db()
        last = db.get("last_reset_date", "")
        today = now.strftime("%Y-%m-%d")
        if last != today:
            print(f"[RESET] Resetting quotas for {today}...")
            for uid in db["users"]:
                db["users"][uid]["quota_used"] = 0
            db["last_reset_date"] = today
            save_db(db)
        await asyncio.sleep(60)

# === MAIN ===
async def main():
    if not BOT_TOKEN or not REDIS_URL:
        print(f"[ERROR] Config missing! Check private.env. BOT_TOKEN found: {bool(BOT_TOKEN)}, REDIS_URL found: {bool(REDIS_URL)}")
        return

    try:
        print(f"[INIT] Connecting to Redis...")
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print(f"[INIT] Redis connected successfully.")
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return

    jenkins_server = get_jenkins_server()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["redis"] = redis_client
    app.bot_data["jenkins"] = jenkins_server
    
    # Original OTA Commands
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("banner", view_banner_command))
    app.add_handler(CommandHandler("setbanner", set_banner_command))
    app.add_handler(CommandHandler("removebanner", remove_banner_command))
    
    # New Jenkins Commands
    app.add_handler(CommandHandler("build", build_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("quota", quota_command))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, handle_notes_reply))

    asyncio.create_task(daily_reset_task())

    print("Bot Running...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    try: await asyncio.Event().wait()
    except: pass
    finally:
        redis_client.close()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
