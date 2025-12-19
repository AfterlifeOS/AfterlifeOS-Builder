import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, timezone, timedelta
from utils import (
    get_quota_status, get_user_data, convert_to_raw_url,
    JENKINS_JOB_NAME, MAX_QUOTA_USER, ROLE_ADMIN, ADMIN_USER_IDS
)

# === CONSTANTS ===
BUILD_OPTIONS = {
    'RELEASETYPE': ['user', 'userdebug', 'eng'],
    'GMS_VARIANT': ['Tree default', 'Full', 'Core', 'Basic', 'Vanilla'],
    'INSTALLCLEAN': ['Yes', 'No'],
    'FULLCLEAN': ['No', 'Yes'],
    'FSGEN': ['Enable', 'Disable'],
    'RELEASE_BUILD': ['No', 'Yes']
}

# === KEYBOARDS ===
def get_build_menu_keyboard(params):
    def btn(l, k): return InlineKeyboardButton(f"{l}: {params[k]}", callback_data=f"build_set:{k}")
    return InlineKeyboardMarkup([
        [btn("Type", "RELEASETYPE"), btn("GMS", "GMS_VARIANT")],
        [btn("Clean", "INSTALLCLEAN"), btn("Full Clean", "FULLCLEAN")],
        [btn("FSGen", "FSGEN"), btn("Release", "RELEASE_BUILD")],
        [InlineKeyboardButton("✅ START", callback_data="build_action:start"), InlineKeyboardButton("❌ CANCEL", callback_data="build_action:cancel")]
    ])

# === HELPERS ===
def get_jenkins(context):
    # Retrieve from bot_data (injected in main) or try reconnect (self-healing logic here if needed)
    return context.bot_data.get("jenkins")

# === HANDLERS ===
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels a specific Jenkins build ID"""
    uid = update.effective_user.id
    # Access check is moved to logic below (Owner or Admin)

    server = get_jenkins(context)
    if not server:
        await update.message.reply_text("⚠️ Jenkins is disconnected.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Usage:** `/cancel <BuildID>`", parse_mode="Markdown")
        return

    try:
        build_id = int(context.args[0])
        status_msg = await update.message.reply_text(f"⏳ Checking Build #{build_id}...")
        
        # 1. Get Build Info to check ownership
        try:
            build_info = await asyncio.to_thread(server.get_build_info, JENKINS_JOB_NAME, build_id)
        except Exception:
            await status_msg.edit_text(f"❌ Build #{build_id} not found or unreachable.")
            return

        # 2. Extract BUILD_USER_ID parameter
        build_owner_id = None
        actions = build_info.get('actions', [])
        for action in actions:
            if 'parameters' in action:
                for param in action['parameters']:
                    if param['name'] == 'BUILD_USER_ID':
                        build_owner_id = str(param['value'])
                        break
        
        # 3. Check Permissions (Admin OR Owner)
        is_owner = build_owner_id and str(uid) == build_owner_id
        is_admin = uid in ADMIN_USER_IDS
        
        if not (is_owner or is_admin):
            await status_msg.edit_text("⛔ **Access Denied:** You can only cancel your own builds.")
            return

        # 4. Execute Cancel
        await status_msg.edit_text(f"⏳ Stopping Build #{build_id}...")
        await asyncio.to_thread(server.stop_build, JENKINS_JOB_NAME, build_id)
        await status_msg.edit_text(f"🛑 **Build #{build_id} Cancelled.**", parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid Build ID. Please provide a number.")
    except Exception as e:
        await update.message.reply_text(f"❌ **Failed to cancel:** {e}", parse_mode="Markdown")

async def quota_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    role, used, remaining = get_quota_status(uid)
    if not role:
        await update.message.reply_text("⛔ **Not registered.** Ask an admin to add you.", parse_mode="Markdown")
        return

    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    h, r = divmod((tomorrow - now).seconds, 3600)
    m, _ = divmod(r, 60)
    
    lim = "Unlimited" if role == ROLE_ADMIN else f"{MAX_QUOTA_USER}"
    msg = (f"<b>📊 Quota Status</b>\n📅 {now.strftime('%Y-%m-%d')}\n👤 {update.effective_user.first_name}\n🏷 {role.upper()}\n🔢 {used} / {lim}\n⏳ Reset in: {h}h {m}m")
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not get_user_data(uid):
        await update.message.reply_text("⛔ **Not registered.**", parse_mode="Markdown")
        return

    server = get_jenkins(context)
    if not server:
        await update.message.reply_text("⚠️ **Jenkins disconnected.**", parse_mode="Markdown")
        return

    try:
        jinfo = await asyncio.to_thread(server.get_job_info, JENKINS_JOB_NAME)
        lnum = jinfo['lastBuild']['number']
        linfo = await asyncio.to_thread(server.get_build_info, JENKINS_JOB_NAME, lnum)
        
        msg = "<b>🔨 Jenkins Status</b>\n\n"
        base_url = linfo['url'].rstrip('/')
        pipeline_url = f"{base_url}/pipeline-overview"
        
        if linfo['building']:
            dur = (datetime.now().timestamp()*1000) - linfo['timestamp']
            dmin = int((dur/1000)/60)
            p = {x['name']: x['value'] for x in linfo['actions'][0].get('parameters', [])}
            msg += f"🟢 <b>Building:</b> #{lnum}\n📱 {p.get('DEVICE')}\n👤 {p.get('BUILD_USER','?')}\n⏱ {dmin} mins\n🔗 <a href='{pipeline_url}'>Pipeline Overview</a>"
        else:
            msg += f"💤 <b>Idle</b>. Last: #{lnum}\nResult: {linfo['result']}\n🔗 <a href='{pipeline_url}'>View Result</a>"
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    role, _, rem = get_quota_status(uid)
    
    if role is None:
        await update.message.reply_text("⛔ **Unauthorized.** Ask an admin to add you.", parse_mode="Markdown")
        return
    if role != ROLE_ADMIN and rem <= 0:
        await update.message.reply_text("⛔ **Quota Exceeded.** Please wait for reset.", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ **Invalid Usage**\n\n"
            "Format: `/build <device> [manifest_url]`\n"
            "Example: `/build walleye`", 
            parse_mode="Markdown"
        )
        return

    dev = context.args[0]
    url = convert_to_raw_url(context.args[1]) if len(context.args) > 1 else ""
    
    params = {
        'DEVICE': dev, 'RELEASETYPE': 'user', 'GMS_VARIANT': 'Tree default',
        'INSTALLCLEAN': 'Yes', 'FULLCLEAN': 'No', 'FSGEN': 'Enable', 'RELEASE_BUILD': 'No',
        'LOCAL_MANIFEST_URL': url, 
        'BUILD_USER': update.effective_user.username or update.effective_user.first_name,
        'BUILD_USER_ID': str(uid)
    }
    context.user_data['pending_build'] = params
    
    lim_str = "Unlimited" if role == ROLE_ADMIN else f"{rem} left"
    msg = f"<b>🛠 Build Config</b>\n👤 {params['BUILD_USER']} ({lim_str})\n📱 {dev}\n\n<i>Adjust settings & Start.</i>"
    await update.message.reply_text(msg, reply_markup=get_build_menu_keyboard(params), parse_mode=ParseMode.HTML)

async def handle_jenkins_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data_str = query.data
    
    # BUILD ACTION
    if data_str.startswith("build_action:"):
        act = data_str.split(":")[1]
        if act == "cancel":
            await query.edit_message_text("❌ **Cancelled by user.**", parse_mode="Markdown")
            if 'pending_build' in context.user_data: del context.user_data['pending_build']
        elif act == "start":
            # Re-check quota
            role, _, rem = get_quota_status(query.from_user.id)
            if role != ROLE_ADMIN and rem <= 0:
                await query.answer("⛔ Quota exceeded!", show_alert=True)
                return
            
            p = context.user_data.get('pending_build')
            if not p:
                await query.edit_message_text("⚠️ **Session Expired.** Please run /build again.", parse_mode="Markdown")
                return
            
            srv = get_jenkins(context)
            if not srv:
                await query.answer("⚠️ Jenkins Unreachable", show_alert=True)
                return

            try:
                await asyncio.to_thread(srv.build_job, JENKINS_JOB_NAME, parameters=p)
                await query.edit_message_text(f"✅ <b>Job Queued!</b>\nDevice: {p['DEVICE']}\nQuota will update on success.", parse_mode=ParseMode.HTML)
            except Exception as e:
                await query.edit_message_text(f"❌ Failed to queue: {e}")

    # BUILD SET
    elif data_str.startswith("build_set:"):
        k = data_str.split(":")[1]
        p = context.user_data.get('pending_build')
        if not p: return
        
        # --- SECURITY CHECK: FULL CLEAN ---
        if k == 'FULLCLEAN':
            role, _, _ = get_quota_status(query.from_user.id)
            if role != ROLE_ADMIN:
                await query.answer("⛔ Full Clean is restricted to Admins!", show_alert=True)
                return

        opts = BUILD_OPTIONS.get(k)
        if opts:
            try: p[k] = opts[(opts.index(p[k])+1)%len(opts)]
            except: p[k] = opts[0]
            context.user_data['pending_build'] = p
            try: await query.edit_message_reply_markup(get_build_menu_keyboard(p))
            except: pass
        await query.answer()
