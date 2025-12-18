import os
import json
import asyncio
import requests
from datetime import datetime, timezone, timedelta
from functools import partial
from dotenv import load_dotenv

# === CONFIGURATION ===
# Load env relative to this file
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(base_dir, 'private.env'))

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
REDIS_URL = os.environ.get("REDIS_URL")
STICKER_ID = os.environ.get("STICKER_ID")

JENKINS_URL = os.environ.get("JENKINS_URL")
JENKINS_USER = os.environ.get("JENKINS_USER")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN")
JENKINS_JOB_NAME = os.environ.get("JENKINS_JOB_NAME", "Afterlife_Build") 

BASE_URL = "https://raw.githubusercontent.com/AfterlifeOS/device_afterlife_ota/refs/heads/16"
DONATE_URL = "https://t.me/donate_zero/6"
AFL_SUPPORT = "https://t.me/AfterLifeOS"
SOURCE_CHANGELOGS_URL = "https://afterlifeos.com/changelog/"

TEST_GROUP_ID = int(os.environ.get("TEST_GROUP_ID", "0"))
TEST_CHANNEL_ID = os.environ.get("TEST_CHANNEL_ID")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Parse Lists
def parse_list(env_str):
    if not env_str: return []
    return [int(x.strip()) for x in env_str.split(",") if x.strip().isdigit()]

ALLOWED_CHAT_IDS = parse_list(os.environ.get("ALLOWED_CHAT_IDS", ""))
if TEST_GROUP_ID != 0 and TEST_GROUP_ID not in ALLOWED_CHAT_IDS:
    ALLOWED_CHAT_IDS.append(TEST_GROUP_ID)

ADMIN_USER_IDS = parse_list(os.environ.get("ADMIN_USER_IDS", ""))

# === CONSTANTS ===
DB_FILE = os.path.join(base_dir, "..", "database.json")
MAX_QUOTA_USER = 5
ROLE_ADMIN = "admin"
ROLE_USER = "user"

# === DATABASE UTILS ===
def load_db():
    if not os.path.exists(DB_FILE): return {"users": {}}
    try:
        with open(DB_FILE, 'r') as f: return json.load(f)
    except: return {"users": {}}

def get_user_data(user_id):
    db = load_db()
    return db["users"].get(str(user_id))

def get_quota_status(user_id):
    user_data = get_user_data(user_id)
    if not user_data: return None, 0, 0
    role = user_data.get("role", ROLE_USER)
    
    last_date = user_data.get("last_build_date", "")
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    used = user_data.get("daily_count", 0) if last_date == today_str else 0
    limit = 999 if role == ROLE_ADMIN else MAX_QUOTA_USER
    return role, used, limit - used

# === REDIS UTILS ===
async def run_redis_command(redis_client, command_name, *args, **kwargs):
    try:
        cmd = getattr(redis_client, command_name)
        sync_call = partial(cmd, *args, **kwargs)
        return await asyncio.to_thread(sync_call)
    except Exception as e:
        print(f"[REDIS ERROR] {e}")
        return None

# === FORMATTING UTILS ===
def convert_to_raw_url(url):
    if not url: return ""
    if "github.com" in url and "/blob/" in url:
        return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
    if "gitlab.com" in url and "/blob/" in url:
        return url.replace("/blob/", "/raw/")
    return url

def bytes_to_gb(size_bytes):
    if not isinstance(size_bytes, (int, float)) or size_bytes == 0: return "N/A"
    return f"{size_bytes / (1024 ** 3):.2f} GB"

def format_date(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%d %B %Y")

def fetch_rom_data(device_codename):
    url = f"{BASE_URL}/{device_codename}/updates.json"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            j = res.json()
            if "response" in j and j["response"]:
                item = j["response"][0]
                mt_link = item.get("telegram", "")
                if mt_link and not mt_link.startswith("http"): mt_link = f"https://{mt_link}"
                
                return {
                    "device_codename": device_codename,
                    "device_name": item.get("device"),
                    "rom_name": "AfterlifeOS",
                    "version": item.get("version"),
                    "release_codename": item.get("codename"),
                    "download": item.get("download"),
                    "timestamp": item.get("timestamp"),
                    "size": item.get("size"),
                    "build_type": item.get("buildtype"),
                    "maintainer_name": item.get("maintainer"),
                    "maintainer_link": mt_link, 
                    "support_group": item.get("forum"),
                }
    except: pass
    return None
