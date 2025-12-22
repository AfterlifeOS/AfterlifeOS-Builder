import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from datetime import datetime, timezone, timedelta
from utils import (
    get_quota_status, get_user_data, convert_to_raw_url,
    JENKINS_JOB_NAME, MAX_QUOTA_USER, ROLE_ADMIN, ROLE_OWNER, ADMIN_USER_IDS
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
    """
    Cancels a build (Queue or Running/Waiting).
    Usage: 
    /cancel <id> (Queue ID or Unique Build ID)
    /cancel <device> <id> (If multiple builds have same ID)
    """
    uid = update.effective_user.id
    server = get_jenkins(context)
    
    if not server:
        await update.message.reply_text("⚠️ Jenkins is disconnected.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ **Usage:**\n`/cancel <id>` (Queue/Build ID)\n`/cancel <device> <id>` (Specific)", parse_mode="Markdown")
        return

    # Parse Arguments
    target_device = None
    target_id = 0
    
    if len(context.args) == 2 and context.args[1].isdigit():
        target_device = context.args[0]
        target_id = int(context.args[1].lstrip('#'))
    elif len(context.args) == 1:
        clean_arg = context.args[0].lstrip('#')
        if clean_arg.isdigit():
            target_id = int(clean_arg)
        else:
            await update.message.reply_text("❌ ID must be a number.")
            return
    else:
        await update.message.reply_text("❌ Invalid format.")
        return

    status_msg = await update.message.reply_text(f"⏳ Searching for #{target_id}...")

    try:
        # --- 1. TRY CANCEL QUEUE (Global ID) ---
        try:
            queue_info = await asyncio.to_thread(server.get_queue_info)
            matched_item = next((item for item in queue_info if item['id'] == target_id), None)
            
            if matched_item:
                # Check Ownership
                q_params = {}
                for action in matched_item.get('actions', []):
                    if 'parameters' in action:
                        q_params = {x['name']: x['value'] for x in action['parameters']}
                        break
                
                # Check Device
                q_dev = q_params.get('DEVICE', matched_item.get('task', {}).get('name', 'Unknown'))
                if target_device and target_device.lower() not in q_dev.lower() and target_device.lower() not in q_dev.lower():
                    await status_msg.edit_text(f"❌ Queue ID #{target_id} matches `{q_dev}`, not `{target_device}`.", parse_mode="Markdown")
                    return

                owner_id = str(q_params.get('BUILD_USER_ID', ''))
                
                # AUTHORIZATION CHECK
                # 1. Is it my build?
                is_my_build = (str(uid) == owner_id)
                
                # 2. Am I a Superuser? (DB Role Admin/Owner ONLY)
                u_data = get_user_data(uid)
                u_role = u_data.get('role', 'user') if u_data else 'user'
                is_superuser = (u_role in [ROLE_ADMIN, ROLE_OWNER])
                
                if not (is_my_build or is_superuser) and owner_id:
                    await status_msg.edit_text("⛔ **Access Denied:** You can only cancel your own queue items.")
                    return

                await asyncio.to_thread(server.cancel_queue, target_id)
                await status_msg.edit_text(f"🗑 **Queue Item #{target_id} ({q_dev}) Cancelled.**", parse_mode="Markdown")
                return
        except Exception as e:
            print(f"[CANCEL] Queue check failed: {e}")

        # --- 2. TRY STOP RUNNING/WAITING BUILD ---
        # Scan folder 'AfterlifeOS' + Controller
        candidates = []
        
        # Helper to scan
        async def check_job(job_name):
            try:
                # Get specific build info directly if ID matches
                b_info = await asyncio.to_thread(server.get_build_info, job_name, target_id)
                # If valid, it exists!
                if b_info['building']:
                    return {'name': job_name, 'info': b_info}
            except: pass
            return None

        # Determine search scope
        jobs_to_check = []
        if target_device:
             # Targeted search
             jobs_to_check.append(f"AfterlifeOS/{target_device}")
        else:
             # Broad search: Scan all jobs in folder (Active or not, checking specific ID is cheap)
             try:
                folder_info = await asyncio.to_thread(server.get_job_info, 'AfterlifeOS')
                if folder_info and 'jobs' in folder_info:
                    for j in folder_info['jobs']:
                        # Add ALL jobs in folder to candidates
                        # We will verify if ID exists in check_job()
                        jobs_to_check.append(f"AfterlifeOS/{j['name']}")
                
                # Also check Controller
                jobs_to_check.append('AfterlifeOS-Builder')
             except: pass

        # Perform Search
        for jn in jobs_to_check:
            res = await check_job(jn)
            if res: candidates.append(res)

        if not candidates:
            await status_msg.edit_text(f"❌ ID #{target_id} not found running/waiting.")
            return

        if len(candidates) > 1:
            names = ", ".join([c['name'].replace('AfterlifeOS/', '') for c in candidates])
            await status_msg.edit_text(f"⚠️ **Ambiguous:** Multiple builds #{target_id} found ({names}).\nUse `/cancel <device> {target_id}`")
            return

        # Single Candidate
        target_build = candidates[0]
        job_name = target_build['name']
        b_info = target_build['info']
        
        # Check Owner
        build_owner_id = None
        actions = b_info.get('actions', [])
        for action in actions:
            if 'parameters' in action:
                for param in action['parameters']:
                    if param['name'] == 'BUILD_USER_ID':
                        build_owner_id = str(param['value'])
                        break
        
        # AUTHORIZATION CHECK
        is_my_build = build_owner_id and str(uid) == build_owner_id
        
        u_data = get_user_data(uid)
        u_role = u_data.get('role', 'user') if u_data else 'user'
        is_superuser = (u_role in [ROLE_ADMIN, ROLE_OWNER])
        
        if not (is_my_build or is_superuser) and build_owner_id:
            await status_msg.edit_text(f"⛔ **Access Denied:** Build belongs to another user.")
            return

        await asyncio.to_thread(server.stop_build, job_name, target_id)
        short_name = job_name.replace('AfterlifeOS/', '').replace('AfterlifeOS-', '')
        await status_msg.edit_text(f"🛑 **Build #{target_id} ({short_name}) Stopped.**", parse_mode="Markdown")

    except Exception as e:
        import traceback
        traceback.print_exc()
        await status_msg.edit_text(f"❌ Error: {e}")

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
    
    lim = "Unlimited" if role in [ROLE_ADMIN, ROLE_OWNER] else f"{MAX_QUOTA_USER}"
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
        msg = "<b>🔨 Jenkins Status</b>\n\n"
        has_activity = False

        # --- DATA GATHERING ---
        
        # 1. Hardware Running (Builds consuming executor)
        hw_running = await asyncio.to_thread(server.get_running_builds)
        
        # 2. Logical Running (All jobs marked as 'building' in Jenkins)
        # Scan 'AfterlifeOS' folder + Controller
        logical_running = []
        
        # A. Folder Scan (Deep Scan)
        async def deep_scan_job(job_name):
            found = []
            try:
                ji = await asyncio.to_thread(server.get_job_info, job_name)
                # Check InQueue (Pending Start)
                if ji.get('inQueue'):
                    next_id = ji.get('nextBuildNumber', 1)
                    found.append({
                        'name': job_name,
                        'number': next_id,
                        'url': '',
                        'is_pending': True
                    })

                # Check Active Builds (Loop last 10 builds)
                builds = ji.get('builds', [])[:10] 
                for b in builds:
                    try:
                        b_detail = await asyncio.to_thread(server.get_build_info, job_name, b['number'])
                        if b_detail.get('building'):
                            found.append({
                                'name': job_name,
                                'number': b['number'],
                                'url': b_detail['url'],
                                'detail': b_detail
                            })
                    except: pass
            except: pass
            return found

        try:
            folder_info = await asyncio.to_thread(server.get_job_info, 'AfterlifeOS')
            if folder_info and 'jobs' in folder_info:
                for j in folder_info['jobs']:
                    full_name = f"AfterlifeOS/{j['name']}"
                    res = await deep_scan_job(full_name)
                    logical_running.extend(res)
        except: pass
        
        # B. Controller Scan
        res_ctrl = await deep_scan_job('AfterlifeOS-Builder')
        logical_running.extend(res_ctrl)

        # --- CATEGORIZATION ---
        
        real_running = [] # Executing on node
        waiting_builds = [] # Started but waiting for node (Flyweight) or Pending

        def is_executing(l_build, hw_list):
            if l_build.get('is_pending'): return False
            for hw in hw_list:
                if hw['number'] == l_build['number']:
                    if hw['name'] in l_build['name']:
                        return True
            return False

        for lb in logical_running:
            if is_executing(lb, hw_running):
                real_running.append(lb)
            else:
                waiting_builds.append(lb)

        # 3. Queue (Pending/Placeholder)
        queue_info = await asyncio.to_thread(server.get_queue_info)
        true_queue = []
        for q in queue_info:
            q_name = q.get('task', {}).get('name', '')
            if q_name and "AfterlifeOS" in q_name:
                true_queue.append(q)

        # --- DISPLAY GENERATION ---

        # A. Running (Executing)
        if real_running:
             msg += "🚀 <b>Running Builds</b>\n\n"
             for build in real_running:
                has_activity = True
                try:
                    # Use cached detail if available
                    b_info = build.get('detail')
                    if not b_info:
                        b_info = await asyncio.to_thread(server.get_build_info, build['name'], build['number'])
                    
                    dur = (datetime.now().timestamp()*1000) - b_info['timestamp']
                    dmin = int((dur/1000)/60)
                    
                    p = {}
                    if 'actions' in b_info:
                        for a in b_info['actions']:
                            if 'parameters' in a:
                                p = {x['name']: x['value'] for x in a['parameters']}
                                break
                    
                    dev = p.get('DEVICE', build['name'].replace('AfterlifeOS/', '').replace('AfterlifeOS-', ''))
                    user = p.get('BUILD_USER', '?')
                    
                    msg += (
                        f"📱 <b>{dev}</b>\n"
                        f"🆔 ID: <code>{build['number']}</code>\n"
                        f"👤 {user}\n"
                        f"⏱ {dmin}m | <a href='{b_info['url']}pipeline-overview'>Pipeline</a>\n\n"
                    )
                except:
                    msg += f"📱 <b>{build['name'].replace('AfterlifeOS/', '')}</b>\n🆔 ID: <code>{build['number']}</code>\n(Info N/A)\n\n"

        # B. Waiting (Started but no executor) + Queue (Not started)
        if waiting_builds or true_queue:
            has_activity = True
            msg += "⏳ <b>Queue / Waiting</b>\n\n"
            
            # List Waiting Builds (Have Number)
            for wb in waiting_builds:
                if wb.get('is_pending'):
                     msg += f"🟡 <b>Pending Start</b>\n📱 {wb['name'].replace('AfterlifeOS/', '')}\n🆔 ID: <code>{wb['number']}</code>\n\n"
                     continue

                try:
                    b_info = wb.get('detail')
                    if not b_info:
                        b_info = await asyncio.to_thread(server.get_build_info, wb['name'], wb['number'])
                    
                    p = {}
                    if 'actions' in b_info:
                        for a in b_info['actions']:
                            if 'parameters' in a:
                                p = {x['name']: x['value'] for x in a['parameters']}
                                break
                    
                    dev = p.get('DEVICE', wb['name'].replace('AfterlifeOS/', '').replace('AfterlifeOS-', ''))
                    user = p.get('BUILD_USER', '?')
                    
                    msg += (
                        f"🟡 <b>Waiting Executor</b>\n"
                        f"📱 <b>{dev}</b>\n"
                        f"🆔 ID: <code>{wb['number']}</code>\n"
                        f"👤 {user}\n\n"
                    )
                except:
                    msg += f"🟡 <b>Waiting</b>\n📱 {wb['name']}\n🆔 ID: <code>{wb['number']}</code>\n\n"

            # List True Queue (No Number)
            for q in true_queue:
                qp = {}
                for action in q.get('actions', []):
                    if 'parameters' in action:
                        qp = {x['name']: x['value'] for x in action['parameters']}
                        break
                
                q_dev = qp.get('DEVICE', q['task']['name'].replace('AfterlifeOS/', '').replace('AfterlifeOS-', ''))
                q_user = qp.get('BUILD_USER', '?')
                msg += (
                    f"🟡 <b>Queue</b>\n"
                    f"📱 <b>{q_dev}</b>\n"
                    f"🆔 ID: <code>{q['id']}</code>\n"
                    f"👤 {q_user}\n\n"
                )


        if not has_activity:
            msg += "💤 <b>System Idle.</b>\nReady to build."
        
        await update.message.reply_text(msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

    except Exception as e:
        import traceback
        traceback.print_exc()
        await update.message.reply_text(f"❌ Error: {e}")

async def build_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    role, _, rem = get_quota_status(uid)
    
    if role is None:
        await update.message.reply_text("⛔ **Unauthorized.** Ask an admin to add you.", parse_mode="Markdown")
        return
    if role not in [ROLE_ADMIN, ROLE_OWNER] and rem <= 0:
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
    
    lim_str = "Unlimited" if role in [ROLE_ADMIN, ROLE_OWNER] else f"{rem} left"
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
            if role not in [ROLE_ADMIN, ROLE_OWNER] and rem <= 0:
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
                await query.edit_message_text(f"✅ <b>Job Queued!</b>\nDevice: {p['DEVICE']}\nCheck Builder Topic for start notification.", parse_mode=ParseMode.HTML)
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
            if role not in [ROLE_ADMIN, ROLE_OWNER]:
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
