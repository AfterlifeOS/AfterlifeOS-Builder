#!/usr/bin/env python3
import json
import os
import sys
import subprocess
from datetime import datetime, timezone

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "..", "database.json")
MAX_QUOTA = 5
ROLE_ADMIN = "admin"

def load_db():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found!")
        sys.exit(1)
    with open(DB_PATH, 'r') as f:
        return json.load(f)

def save_db(data):
    with open(DB_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def git_commit_push(username):
    try:
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()
        print(f"Committing to branch: {branch}")
        
        # Configure Git if not already set (for CI environment)
        subprocess.run(['git', 'config', 'user.email', 'bot@jenkins.local'], check=False)
        subprocess.run(['git', 'config', 'user.name', 'Jenkins Bot'], check=False)
        
        subprocess.run(['git', 'add', DB_PATH], check=True)
        subprocess.run(['git', 'commit', '-m', f"quota: Update build quota for {username}"], check=True)
        
        # Pull first to avoid conflicts
        subprocess.run(['git', 'pull', '--rebase', 'origin', branch], check=True)
        subprocess.run(['git', 'push', 'origin', branch], check=True)
        print("Git push successful.")
    except subprocess.CalledProcessError as e:
        print(f"Git Error: {e}")
        # Don't fail the build just because git failed
        sys.exit(0) 

def main():
    # Arguments passed from Jenkins: script.py <USER_ID> <USERNAME>
    if len(sys.argv) < 3:
        print("Usage: quota_manager.py <USER_ID> <USERNAME>")
        sys.exit(1)

    user_id = sys.argv[1]
    username = sys.argv[2]
    
    print(f"Processing quota for User: {username} (ID: {user_id})")

    db = load_db()
    
    if user_id not in db["users"]:
        print("User not found in DB. Skipping quota update.")
        sys.exit(0)

    user_data = db["users"][user_id]
    role = user_data.get("role", "user")
    
    # Date Logic
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    last_date = user_data.get("last_build_date", "")
    
    if last_date != today_str:
        print(f"New day detected (Last: {last_date}, Today: {today_str}). Resetting counter.")
        user_data["daily_count"] = 0
        user_data["last_build_date"] = today_str
    
    # CHECK QUOTA LIMIT
    current_count = user_data.get("daily_count", 0)
    if role != ROLE_ADMIN and current_count >= MAX_QUOTA:
        print(f"[ERROR] Quota Exceeded! Used: {current_count}/{MAX_QUOTA}")
        sys.exit(1) # Fail the build immediately

    # INCREMENT & SAVE
    user_data["daily_count"] += 1
    print(f"Quota Approved. Incrementing counter to {user_data['daily_count']}")

    # Update Username just in case
    user_data["username"] = username
    
    # Save & Push
    save_db(db)
    git_commit_push(username)

if __name__ == "__main__":
    main()
