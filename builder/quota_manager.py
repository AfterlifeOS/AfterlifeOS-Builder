#!/usr/bin/env python3
import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from utils.telegram import TelegramBot

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "database.json")
MAX_QUOTA = 5
ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"

def run_git(args, check=True):
    """Helper to run git commands"""
    try:
        subprocess.run(args, check=check, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"[GIT ERROR] Command {' '.join(args)} failed.")
        if check: raise e

def get_target_branch():
    env_branch = os.environ.get("GIT_BRANCH") or os.environ.get("BRANCH_NAME")
    if env_branch:
        return env_branch.split("origin/")[1] if "origin/" in env_branch else env_branch
    
    try:
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
        return "main" if branch == "HEAD" else branch
    except:
        return "main"

def prepare_git_env(branch):
    print(f"[GIT] Preparing environment on branch: {branch}...")
    # Ignore permission changes (chmod +x) to avoid dirty tree errors
    run_git(['git', 'config', 'core.filemode', 'false'], check=False)
    
    run_git(['git', 'config', 'user.email', 'bot@jenkins.local'], check=False)
    run_git(['git', 'config', 'user.name', 'Jenkins Bot'], check=False)
    
    # 1. Stash any dirty changes to allow pull
    run_git(['git', 'stash'], check=False)
    
    # 2. Pull latest changes
    print(f"[GIT] Pulling latest data from {branch}...")
    run_git(['git', 'pull', '--rebase', 'origin', branch])

def finalize_git_changes(username, branch):
    print("[GIT] Committing and Pushing...")
    try:
        run_git(['git', 'add', DB_PATH])
        run_git(['git', 'commit', '-m', f"quota: Update build quota for {username}"])
        run_git(['git', 'push', 'origin', f"HEAD:{branch}"])
        print("[GIT] Success.")
    except Exception as e:
        print(f"[GIT WARN] Push failed: {e}")
    finally:
        # 3. Restore stashed changes (optional, ignore errors if conflict)
        run_git(['git', 'stash', 'pop'], check=False)

def load_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found!")
        sys.exit(1)
    with open(DB_PATH, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def main():
    if len(sys.argv) < 3:
        print("Usage: quota_manager.py <USER_ID> <USERNAME> [FULL_CLEAN]")
        sys.exit(1)

    user_id = sys.argv[1]
    username = sys.argv[2]
    # Argumen ke-3 opsional, default "No"
    is_full_clean = sys.argv[3] if len(sys.argv) > 3 else "No"
    
    branch = get_target_branch()

    # STEP 1: Sync with Remote First
    prepare_git_env(branch)

    # STEP 2: Process Logic
    print(f"Processing quota for User: {username} (ID: {user_id})")
    db = load_db() # Reload DB after pull to ensure we have latest
    
    if user_id not in db["users"]:
        print("User not found in DB. Skipping quota update.")
        sys.exit(0)

    user_data = db["users"][user_id]
    role = user_data.get("role", "user")
    
    # --- SECURITY CHECK: FULL CLEAN ---
    if is_full_clean == "Yes" and role not in [ROLE_ADMIN, ROLE_OWNER]:
        print("⛔ SECURITY ALERT: Full Clean is restricted to Admins only!")
        sys.exit(1)
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last_date = user_data.get("last_build_date", "")
    
    if last_date != today_str:
        print(f"New day detected (Last: {last_date}, Today: {today_str}). Resetting counter.")
        user_data["daily_count"] = 0
        user_data["last_build_date"] = today_str
    
    # CHECK LIMIT
    current_count = user_data.get("daily_count", 0)
    if role not in [ROLE_ADMIN, ROLE_OWNER] and current_count >= MAX_QUOTA:
        print(f"[ERROR] Quota Exceeded! Used: {current_count}/{MAX_QUOTA}")
        
        # --- NOTIFICATION HANDLER ---
        token = os.environ.get("TELEGRAM_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        topic_id = os.environ.get("TOPIC_BUILDER")
        
        if token and chat_id:
            try:
                bot = TelegramBot(token)
                
                # Calculate Reset Time
                now = datetime.now(timezone.utc)
                reset_time = (now.replace(hour=23, minute=59, second=59, microsecond=999999) - now)
                hours, remainder = divmod(reset_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                msg = (
                    f"⛔ **Quota Exceeded**\n\n"
                    f"👤 **User:** `{username}`\n"
                    f"🏷 **Role:** `{role.upper()}`\n"
                    f"🔢 **Used:** `{current_count}/{MAX_QUOTA}`\n"
                    f"⏳ **Reset in:** `{hours}h {minutes}m`\n\n"
                    f"Please wait for the daily reset or ask an admin."
                )
                bot.send_message(chat_id, msg, topic_id=topic_id)
                print("[NOTIF] Quota exceeded notification sent.")
            except Exception as e:
                print(f"[NOTIF ERROR] Failed to send notification: {e}")

        # Create marker file for Jenkins pipeline to detect and skip failure report
        workspace = os.environ.get("WORKSPACE", ".")
        with open(os.path.join(workspace, ".quota_exceeded"), "w") as f:
            f.write("true")

        sys.exit(1) 

    # INCREMENT
    user_data["daily_count"] += 1
    # Update Username
    user_data["username"] = username
    
    # STEP 3: Save & Push
    save_db(db)
    finalize_git_changes(username, branch)

if __name__ == "__main__":
    main()
