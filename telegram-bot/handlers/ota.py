import html
import asyncio
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from utils import (
    ALLOWED_CHAT_IDS, ADMIN_USER_IDS, CHANNEL_ID, TEST_GROUP_ID, TEST_CHANNEL_ID,
    STICKER_ID, BOT_TOKEN, SOURCE_CHANGELOGS_URL, AFL_SUPPORT, DONATE_URL,
    fetch_rom_data, format_date, bytes_to_gb, run_redis_command, restricted_command
)
from telegram import Bot

# === KEYBOARDS ===
def build_keyboard(data):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Download", url=data['download']), InlineKeyboardButton("Source Changelogs", url=SOURCE_CHANGELOGS_URL)],
        [InlineKeyboardButton("Support Group", url=AFL_SUPPORT), InlineKeyboardButton("Donate", url=DONATE_URL)],
        [InlineKeyboardButton("Device Support", url=data.get('support_group') or AFL_SUPPORT)]
    ])

def confirm_keyboard(dev, uid, has_notes=False):
    btns = [[InlineKeyboardButton("✅ Post to Channel", callback_data=f"confirm_send:{dev}:{uid}")]]
    if has_notes: btns.append([InlineKeyboardButton("🗑 Remove Notes", callback_data=f"notes_clear:{dev}:{uid}")])
    btns.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_post:{uid}")])
    return InlineKeyboardMarkup(btns)

def ask_notes_keyboard(dev, uid):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, add notes", callback_data=f"notes_yes:{dev}:{uid}")],
        [InlineKeyboardButton("No, continue", callback_data=f"notes_no:{dev}:{uid}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_post:{uid}")]
    ])

# === FORMATTER ===
def format_post(data, posted_by, notes_list=None):
    rom = data.get("rom_name", "AfterlifeOS")
    ver = data.get("version", "Unknown")
    dev_name = data.get("device_name", data['device_codename'])
    dev_code = data['device_codename']
    date = format_date(int(data.get("timestamp", 0)))
    size = bytes_to_gb(data.get("size", 0))
    rel_type = data.get("build_type", "Unofficial").capitalize()
    
    maintainer = data.get("maintainer_name", posted_by)
    m_link = data.get("maintainer_link", f"https://t.me/{posted_by}")

    post = (
        f"<b>{rom} v{ver} {data.get('release_codename','')} | {rel_type} | Android 16</b>\n"
        f"Supported Device: {dev_name} - {dev_code}\n"
        f"Build date: {date}\n"
        f"Maintainer: <a href='{m_link}'>{maintainer}</a>\n"
    )

    if notes_list:
        # Process links: [text] (url) OR [text](url) -> <a href="url">text</a>
        processed_notes = []
        for note in notes_list:
            clean_note = note.lstrip('- ')
            # Regex Explanation:
            # \[ (.*?) \]  : Capture group 1 (Text) inside brackets
            # \s*          : Allow optional spaces between brackets and parentheses
            # \( (.*?) \)  : Capture group 2 (URL) inside parentheses
            clean_note = re.sub(r'\[(.*?)\]\s*\((.*?)\)', r'<a href="\2">\1</a>', clean_note)
            
            # Optional: Clean up any double spaces created
            clean_note = re.sub(r'\s+', ' ', clean_note).strip()
            
            if clean_note:
                processed_notes.append(f"- {clean_note}")
        
        notes_str = "\n".join(processed_notes)
        if notes_str: post += f"\n<b>Notes:</b>\n{notes_str}\n"

    post += (
        f"\nThere's nothing special about my rom, you can skip if you don't like, or you can taste it.\n"
        f"Subscribe For More <a href='https://t.me/Afterlife_update'>AfterlifeOS</a>\n\n"
        f"Hope you all have a happy life\n"
        f"Thank you.\n\n"
        f"#{rom} #{dev_code} #NeverDie"
    )
    return post

# === HANDLERS ===
@restricted_command
async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check removed as handled by decorator
    
    redis_client = context.bot_data.get("redis")
    if not redis_client:
        await update.message.reply_text("❌ Redis not connected.")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ **Usage:** `/post <codename>`", parse_mode="Markdown")
        return

    dev = context.args[0]
    data = fetch_rom_data(dev)
    if not data:
        await update.message.reply_text("❌ Data not found for this device.")
        return

    banner = await run_redis_command(redis_client, "get", "banner_file_id")
    if not banner:
        await update.message.reply_text("⚠️ **Banner not set.** Use `/setbanner` first.", parse_mode="Markdown")
        return

    poster = update.effective_user.username or update.effective_user.first_name
    preview = format_post(data, poster)
    await update.message.reply_photo(banner, caption=preview, parse_mode=ParseMode.HTML, reply_markup=ask_notes_keyboard(dev, update.effective_user.id))

async def handle_ota_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data_str = query.data
    
    # 1. NOTES YES
    if data_str.startswith("notes_yes:"):
        _, dev, uid = data_str.split(":", 2)
        if str(user_id) != uid: return
        await query.answer()
        await query.edit_message_reply_markup(None)
        
        # FIX: Explicit double backslash for safety or proper raw string usage
        txt = (
            r"Reply with your notes\." "\n"
            r"• Do NOT add dash \(\-\)" " manually\." "\n"
            r"• To add a link, use format: `[text] (url)`"
        )
        msg = await query.message.reply_text(txt, reply_markup=ForceReply(selective=True), parse_mode=ParseMode.MARKDOWN_V2)
        context.user_data['awaiting_notes_for'] = {'orig_id': query.message.message_id, 'prompt_id': msg.message_id, 'dev': dev, 'uid': user_id}

    # 2. NOTES NO
    elif data_str.startswith("notes_no:"):
        _, dev, uid = data_str.split(":", 2)
        if str(user_id) != uid: return
        await query.answer()
        await query.edit_message_reply_markup(confirm_keyboard(dev, uid, False))

    # 3. NOTES CLEAR
    elif data_str.startswith("notes_clear:"):
        _, dev, uid = data_str.split(":", 2)
        if str(user_id) != uid: return
        await query.answer()
        data = fetch_rom_data(dev)
        if data:
            clean_msg = format_post(data, query.from_user.first_name, None)
            await query.edit_message_caption(caption=clean_msg, parse_mode=ParseMode.HTML, reply_markup=ask_notes_keyboard(dev, uid))

    # 4. CANCEL
    elif data_str.startswith("cancel_post:"):
        uid = data_str.split(":")[-1]
        if str(user_id) != uid: return
        await query.edit_message_reply_markup(None)
        await query.message.reply_text("❌ Cancelled.")
        if 'awaiting_notes_for' in context.user_data: del context.user_data['awaiting_notes_for']

    # 5. CONFIRM SEND
    elif data_str.startswith("confirm_send:"):
        _, dev, uid = data_str.split(":", 2)
        if str(user_id) != uid: return
        
        banner = await run_redis_command(context.bot_data["redis"], "get", "banner_file_id")
        data = fetch_rom_data(dev)
        if banner and data:
            target = CHANNEL_ID if query.message.chat.id != TEST_GROUP_ID else TEST_CHANNEL_ID
            notes = []
            if "<b>Notes:</b>" in query.message.caption_html:
                try: notes = [l.lstrip('- ') for l in query.message.caption_html.split("<b>Notes:</b>\n")[1].split("\n\n")[0].split("\n") if l.strip()]
                except: pass
            
            final_msg = format_post(data, query.from_user.first_name, notes)
            kb = build_keyboard(data)
            
            await query.edit_message_reply_markup(None)
            bot = Bot(token=BOT_TOKEN) # Fresh instance for send
            
            if STICKER_ID:
                try:
                    await bot.send_sticker(target, STICKER_ID)
                    w_msg = await query.message.reply_text("⏳ Sticker sent. Waiting 15s...", parse_mode=ParseMode.HTML)
                    await asyncio.sleep(15)
                    await context.bot.delete_message(query.message.chat.id, w_msg.message_id)
                except: pass
            
            await bot.send_photo(target, banner, caption=final_msg, parse_mode=ParseMode.HTML, reply_markup=kb)
            await query.message.reply_text("✅ Sent.")

async def handle_notes_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'awaiting_notes_for' not in context.user_data: return
    st = context.user_data['awaiting_notes_for']
    if update.message.reply_to_message.message_id == st['prompt_id']:
        notes = [f"- {l.strip()}" for l in html.escape(update.message.text).split("\n") if l.strip()]
        data = fetch_rom_data(st['dev'])
        if data:
            msg = format_post(data, update.effective_user.first_name, notes)
            await context.bot.edit_message_caption(update.effective_chat.id, st['orig_id'], caption=msg, parse_mode=ParseMode.HTML, reply_markup=confirm_keyboard(st['dev'], st['uid'], True))
            del context.user_data['awaiting_notes_for']
            await context.bot.delete_message(update.effective_chat.id, st['prompt_id'])
            await context.bot.delete_message(update.effective_chat.id, update.message.message_id)

@restricted_command
async def set_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS: return
    if update.message.reply_to_message and update.message.reply_to_message.photo:
        await run_redis_command(context.bot_data["redis"], "set", "banner_file_id", update.message.reply_to_message.photo[-1].file_id)
        await update.message.reply_text("✅ Banner set.")

@restricted_command
async def remove_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_USER_IDS: return
    await run_redis_command(context.bot_data["redis"], "delete", "banner_file_id")
    await update.message.reply_text("✅ Banner removed.")

@restricted_command
async def view_banner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    b = await run_redis_command(context.bot_data["redis"], "get", "banner_file_id")
    if b: await update.message.reply_photo(b)
    else: await update.message.reply_text("No banner.")
