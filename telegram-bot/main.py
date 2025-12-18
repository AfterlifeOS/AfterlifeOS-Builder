import os
import sys

# === CUSTOM LIBRARY LOADER ===
custom_lib_path = os.path.expanduser("~/pylib")
if os.path.isdir(custom_lib_path):
    if custom_lib_path not in sys.path:
        sys.path.insert(0, custom_lib_path)
        print(f"[INIT] Loading custom libraries from: {custom_lib_path}")

import requests
import asyncio
import html
from datetime import datetime, timezone, timedelta
import re
import redis
import json
from functools import partial
import jenkins
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

# Allowed Chat (Legacy)
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

# Admin Users (Legacy)
admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
temp_admin_list = admin_ids_str.split(",")
ADMIN_USER_IDS = []
for item in temp_admin_list:
    item_stripped = item.strip()
    if item_stripped:
        try: ADMIN_USER_IDS.append(int(item_stripped))
        except: pass

# === DATABASE & QUOTA CONSTANTS ===
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "database.json")
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

# === DATABASE FUNCTIONS (READ ONLY FOR BOT) ===
def load_db():
    if not os.path.exists(DB_FILE):
        return {"users": {}}
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Load DB failed: {e}")
        return {"users": {}}

def get_user_data(user_id):
    db = load_db()
    return db["users"].get(str(user_id))

def get_quota_status(user_id):
    user_data = get_user_data(user_id)
    if not user_data:
        return None, 0, 0
    
    role = user_data.get("role", ROLE_USER)
    
    # Check Date
    last_date = user_data.get("last_build_date", "")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    if last_date == today_str:
        used = user_data.get("daily_count", 0)
    else:
        used = 0
        
    limit = 999 if role == ROLE_ADMIN else MAX_QUOTA_USER
    remaining = limit - used
    
    return role, used, remaining

# === JENKINS & REDIS HELPERS ===
def get_jenkins_server():
    print(f"[JENKINS] Connecting to {JENKINS_URL}...")
    if not JENKINS_URL: return None
    try:
        server = jenkins.Jenkins(JENKINS_URL, username=JENKINS_USER, password=JENKINS_TOKEN)
        user = server.get_whoami()
        print(f"[JENKINS] Connected as: {user['fullName']}")
        return server
    except Exception as e:
        print(f"[JENKINS ERROR] {e}")
        return None

async def run_redis_command(redis_client, command_name, *args, **kwargs):
    try:
        command_method = getattr(redis_client, command_name)
        sync_call = partial(command_method, *args, **kwargs)
        return await asyncio.to_thread(sync_call)
    except Exception as e:
        print(f"[ERROR] Redis command '{command_name}' failed: {e}")
        return None

def convert_to_raw_url(url):
    if not url: return ""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "gitlab.com" in url and "/blob/" in url:
        return url.replace("/blob/", "/raw/")
    return url

# === OTA HELPERS ===
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
                    "download": j.get("download"),
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

def format_date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%d %B %Y")

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

# UPDATED KEYBOARDS
def confirm_keyboard(device_codename, user_id, has_notes=False):
    buttons = [[InlineKeyboardButton("✅ Post to Channel", callback_data=f"confirm_send:{device_codename}:{user_id}")]]
    
    if has_notes:
        buttons.append([InlineKeyboardButton("🗑 Remove Notes", callback_data=f"notes_clear:{device_codename}:{user_id}")])
        
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_post:{user_id}")])
    return InlineKeyboardMarkup(buttons)

def ask_notes_keyboard(device_codename, user_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, add notes", callback_data=f"notes_yes:{device_codename}:{user_id}")],
        [InlineKeyboardButton("No, continue", callback_data=f"notes_no:{device_codename}:{user_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_post:{user_id}")] # Added Cancel here too
    ])

# === COMMANDS ===

async def quota_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    role, used, remaining = get_quota_status(user_id)
    
    if not role:
        await update.message.reply_text("⛔ You are not registered.")
        return

    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    hours, remainder = divmod((tomorrow - now).seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    limit_disp = "Unlimited" if role == ROLE_ADMIN else f"{MAX_QUOTA_USER}"
    
    msg = (
        f"<b>📊 Build Quota Status</b>\n"
        f"📅 Date (UTC): {now.strftime('%Y-%m-%d')}\n\n"
        f"👤 User: {update.effective_user.first_name}\n"
        f"🏷 Role: {role.upper()}\n"
        f"🔢 Used Today: {used} / {limit_disp}\n"
        f"⏳ Next Reset: {hours}h {minutes}m"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not get_user_data(user_id):
        await update.message.reply_text("⛔ Not registered.")
        return

    # Self-healing
    server = context.bot_data.get("jenkins")
    if not server:
        server = get_jenkins_server()
        if server: context.bot_data["jenkins"] = server
    if not server:
        await update.message.reply_text("⚠️ Jenkins disconnected.")
        return

    try:
        job_info = await asyncio.to_thread(server.get_job_info, JENKINS_JOB_NAME)
        last_build_number = job_info['lastBuild']['number']
        last_build_info = await asyncio.to_thread(server.get_build_info, JENKINS_JOB_NAME, last_build_number)
        
        build_url = last_build_info['url']
        
        msg = "<b>🔨 Jenkins Build Status</b>\n\n"
        
        if last_build_info['building']:
            duration = (datetime.now().timestamp() * 1000) - last_build_info['timestamp']
            duration_min = int((duration / 1000) / 60)
            params = {p['name']: p['value'] for p in last_build_info['actions'][0].get('parameters', [])}
            
            msg += f"🟢 <b>Building Now:</b> #{last_build_number}\n"
            msg += f"📱 Device: {params.get('DEVICE')}\n"
            msg += f"👤 User: {params.get('BUILD_USER', 'Unknown')}\n"
            msg += f"⏱ Time: {duration_min} mins\n"
            msg += f"🔗 <a href='{build_url}'>View Pipeline Overview</a>\n"
        else:
            msg += f"💤 <b>Idle</b>. Last build (#{last_build_number}) finished.\nResult: {last_build_info['result']}\n"
            msg += f"🔗 <a href='{build_url}'>View Result</a>\n"

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
    
    # Self-healing
    server = context.bot_data.get("jenkins")
    if not server:
        server = get_jenkins_server()
        if server: context.bot_data["jenkins"] = server
    if not server:
        await update.message.reply_text("⚠️ Jenkins disconnected.")
        return

    # Check Quota (Read Only)
    role, used, remaining = get_quota_status(user_id)
    
    if role is None:
        await update.message.reply_text("⛔ You are not authorized.")
        return
        
    if role != ROLE_ADMIN and remaining <= 0:
        await update.message.reply_text("⛔ <b>Quota Exceeded for Today.</b>\nTry again at 00:00 UTC.", parse_mode=ParseMode.HTML)
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
        'BUILD_USER': username,
        'BUILD_USER_ID': str(user_id)
    }
    
    context.user_data['pending_build'] = params
    
    limit_info = "Unlimited" if role == ROLE_ADMIN else f"{remaining} remaining"
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

# === CALLBACK ===
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    redis_client = context.bot_data["redis"]

    # BUILD ACTIONS
    if query.data.startswith("build_action:"):
        action = query.data.split(":")[1]
        if action == "cancel":
            await query.edit_message_text("❌ Cancelled.")
            if 'pending_build' in context.user_data: del context.user_data['pending_build']
            return
        if action == "start":
            role, _, remaining = get_quota_status(user_id)
            if role != ROLE_ADMIN and remaining <= 0:
                await query.answer("Quota exceeded!", show_alert=True)
                return
            params = context.user_data.get('pending_build')
            if not params:
                await query.edit_message_text("⚠️ Expired.")
                return
            server = context.bot_data.get("jenkins")
            try:
                await asyncio.to_thread(server.build_job, JENKINS_JOB_NAME, parameters=params)
                await query.edit_message_text(f"✅ <b>Build Queued!</b>\nDevice: {params['DEVICE']}\nQuota will update after build success.", parse_mode=ParseMode.HTML)
            except Exception as e:
                await query.edit_message_text(f"❌ Failed: {e}")
            return

    # BUILD SETTINGS
    if query.data.startswith("build_set:"):
        key = query.data.split(":")[1]
        params = context.user_data.get('pending_build')
        if not params: return
        opts = BUILD_OPTIONS[key]
        try: params[key] = opts[(opts.index(params[key]) + 1) % len(opts)]
        except: params[key] = opts[0]
        context.user_data['pending_build'] = params
        try: await query.edit_message_reply_markup(get_build_menu_keyboard(params))
        except: pass
        await query.answer()
        return

    # OTA ACTIONS
    # 1. Notes YES
    if query.data.startswith("notes_yes:"):
        try: _, dev, uid = query.data.split(":", 2)
        except: return
        if str(user_id) != uid: return
        await query.answer()
        await query.edit_message_reply_markup(None)
        
        # FIXED INSTRUCTION MESSAGE
        instruction_text = (
            r"Reply with your notes\." "\n"
            r"• Do NOT add dash \(\-\)" " manually\." "\n"
            r"• To add a link, use format: `[text] (url)`"
        )
        msg = await query.message.reply_text(instruction_text, reply_markup=ForceReply(selective=True), parse_mode=ParseMode.MARKDOWN_V2)
        
        context.user_data['awaiting_notes_for'] = {'original_preview_message_id': query.message.message_id, 'prompt_message_id': msg.message_id, 'device_codename': dev, 'user_id': user_id}
        return

    # 2. Notes NO
    if query.data.startswith("notes_no:"):
        try: _, dev, uid = query.data.split(":", 2)
        except: return
        if str(user_id) != uid: return
        await query.answer()
        # Show Confirm Keyboard (No notes, so has_notes=False)
        await query.edit_message_reply_markup(confirm_keyboard(dev, uid, has_notes=False))
        return

    # 3. Notes CLEAR
    if query.data.startswith("notes_clear:"):
        try: _, dev, uid = query.data.split(":", 2)
        except: return
        if str(user_id) != uid: return
        
        await query.answer()
        
        # Re-fetch data to get clean caption
        data = fetch_rom_data(dev)
        if data:
            # Re-render caption without notes
            poster = query.from_user.first_name
            clean_msg = format_post(data, poster, notes_list=None)
            
            # Edit caption back to clean state
            await query.edit_message_caption(
                caption=clean_msg, 
                parse_mode=ParseMode.HTML, 
                reply_markup=ask_notes_keyboard(dev, uid) # Go back to Ask Notes
            )
        return

    # 4. Cancel
    if query.data.startswith("cancel_post:"):
        try: uid = query.data.split(":")[-1]
        except: return
        if str(user_id) != uid: return
        await query.edit_message_reply_markup(None)
        await query.message.reply_text("Cancelled.")
        if 'awaiting_notes_for' in context.user_data: del context.user_data['awaiting_notes_for']
        return

    # 5. Confirm Send
    if query.data.startswith("confirm_send:"):
        try: _, dev, uid = query.data.split(":", 2)
        except: return
        if str(user_id) != uid: return
        
        banner = await run_redis_command(redis_client, "get", "banner_file_id")
        if not banner: return
        data = fetch_rom_data(dev)
        if data:
            target = CHANNEL_ID if query.message.chat.id != TEST_GROUP_ID else TEST_CHANNEL_ID
            notes = []
            if "<b>Notes:</b>" in query.message.caption_html:
                try: notes = [l.lstrip('- ') for l in query.message.caption_html.split("<b>Notes:</b>\n")[1].split("\n\n")[0].split("\n") if l.strip()]
                except: pass
            
            msg = format_post(data, query.from_user.first_name, notes)
            kb = build_keyboard(data)
            bot = Bot(token=BOT_TOKEN)
            
            await query.edit_message_reply_markup(None)
            
            # STICKER DELAY LOGIC (15 Seconds)
            if STICKER_ID: 
                try: 
                    await bot.send_sticker(target, STICKER_ID)
                    status_msg = await query.message.reply_text(f"⏳ Sticker sent. Waiting 15s before posting...", parse_mode=ParseMode.HTML)
                    await asyncio.sleep(15)
                    await context.bot.delete_message(query.message.chat.id, status_msg.message_id)
                except Exception as e: 
                    print(f"Sticker error: {e}")

            # SEND MAIN POST
            await bot.send_photo(target, banner, caption=msg, parse_mode=ParseMode.HTML, reply_markup=kb)
            await query.message.reply_text("✅ Sent.")
    

# OTA COMMANDS (LEGACY)
async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id not in ALLOWED_CHAT_IDS: return
    if update.effective_user.id not in ADMIN_USER_IDS: return
    if not context.args: return
    dev = context.args[0]
    data = fetch_rom_data(dev)
    if not data: return
    banner = await run_redis_command(context.bot_data["redis"], "get", "banner_file_id")
    if not banner: await update.message.reply_text("No Banner."); return
    await update.message.reply_photo(banner, caption=format_post(data, update.effective_user.first_name), parse_mode=ParseMode.HTML, reply_markup=ask_notes_keyboard(dev, update.effective_user.id))

async def set_banner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS: return
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        await run_redis_command(context.bot_data["redis"], "set", "banner_file_id", update.message.reply_to_message.photo[-1].file_id)
        await update.message.reply_text("✅ Banner set.")

async def remove_banner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS: return
    await run_redis_command(context.bot_data["redis"], "delete", "banner_file_id")
    await update.message.reply_text("✅ Banner removed.")

async def view_banner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    banner = await run_redis_command(context.bot_data["redis"], "get", "banner_file_id")
    if banner: await update.message.reply_photo(banner)
    else: await update.message.reply_text("No banner.")

async def handle_notes_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'awaiting_notes_for' not in context.user_data: return
    st = context.user_data['awaiting_notes_for']
    if update.message.reply_to_message.message_id == st['prompt_message_id']:
        notes = [f"- {l.strip()}" for l in html.escape(update.message.text).split("\n") if l.strip()]
        data = fetch_rom_data(st['device_codename'])
        if data:
            msg = format_post(data, update.effective_user.first_name, notes)
            await context.bot.edit_message_caption(update.effective_chat.id, st['original_preview_message_id'], caption=msg, parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard(st['device_codename'], st['user_id'], has_notes=True))
            del context.user_data['awaiting_notes_for']
            await context.bot.delete_message(update.effective_chat.id, st['prompt_message_id'])
            await context.bot.delete_message(update.effective_chat.id, update.message.message_id)

# === MAIN ===
async def main():
    if not BOT_TOKEN or not REDIS_URL:
        print("[ERROR] Config Missing.")
        return
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print("[INIT] Redis Connected.")
    except Exception as e:
        print(f"[ERROR] Redis Failed: {e}")
        return

    jenkins_server = get_jenkins_server()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["redis"] = redis_client
    app.bot_data["jenkins"] = jenkins_server
    
    app.add_handler(CommandHandler("build", build_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("quota", quota_command))
    app.add_handler(CommandHandler("post", post_command))
    app.add_handler(CommandHandler("setbanner", set_banner_command))
    app.add_handler(CommandHandler("removebanner", remove_banner_command))
    app.add_handler(CommandHandler("banner", view_banner_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.REPLY & filters.TEXT & ~filters.COMMAND, handle_notes_reply))

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