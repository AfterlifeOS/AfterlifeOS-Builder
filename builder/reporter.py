#!/usr/bin/env python3
import os
import sys
import argparse
import glob
import requests
import subprocess
from utils.telegram import TelegramBot

def upload_to_gofile(file_path):
    print(f"Uploading {file_path} to GoFile...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    url = "https://upload.gofile.io/uploadFile"
    
    try:
        with open(file_path, 'rb') as f:
            upload_req = requests.post(
                url,
                files={'file': f},
                headers=headers
            )
            
            try:
                upload_data = upload_req.json()
            except ValueError:
                 print(f"GoFile JSON Error: {upload_req.text}")
                 return None

            if upload_data['status'] == 'ok':
                return upload_data['data']['downloadPage']
            else:
                print(f"GoFile upload failed: {upload_data}")
                return None
    except Exception as e:
        print(f"GoFile Exception: {e}")
        return None

def get_file_tail(file_path, lines=200):
    try:
        result = subprocess.check_output(['tail', '-n', str(lines), file_path])
        return result.decode('utf-8', errors='ignore')
    except Exception as e:
        return f"Error reading log: {e}"

def create_telegram_link(chat_id, topic_id, message_id):
    # Remove -100 prefix for supergroup links
    clean_chat_id = str(chat_id)
    if clean_chat_id.startswith("-100"):
        clean_chat_id = clean_chat_id[4:]
    
    if topic_id:
        return f"https://t.me/c/{clean_chat_id}/{topic_id}/{message_id}"
    return f"https://t.me/c/{clean_chat_id}/{message_id}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--status', required=True, choices=['started', 'success', 'failure', 'aborted'])
    parser.add_argument('--device', required=True)
    parser.add_argument('--build-type', required=True)
    parser.add_argument('--gms', required=True)
    parser.add_argument('--fsgen', required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--chat-id', required=True)
    parser.add_argument('--topic-builder', required=True, help="Topic for main notifications")
    parser.add_argument('--topic-error-logs', required=True, help="Topic for Error Logs")
    parser.add_argument('--topic-release-json', required=True, help="Topic for Release JSONs")
    parser.add_argument('--token', required=True)
    parser.add_argument('--build-url', required=True, help="Jenkins Build URL")
    parser.add_argument('--release-status', required=True, help="Release Build (Yes/No)")
    parser.add_argument('--source-dir', required=True, help="AOSP Source Directory")
    parser.add_argument('--install-clean', default="No", help="Install Clean (Yes/No)")
    parser.add_argument('--full-clean', default="No", help="Full Clean (Yes/No)")
    
    args = parser.parse_args()
    bot = TelegramBot(args.token)
    workspace = os.environ.get('WORKSPACE', '.')
    out_dir = os.path.join(args.source_dir, 'out', 'target', 'product', args.device)
    
    # Common Info Block
    info_block = (
        f"📱 **Device:** `{args.device}`\n"
        f"🚀 **Type:** `{args.build_type}`\n"
        f"📢 **Release:** `{args.release_status}`\n"
        f"🧩 **GMS:** `{args.gms}`\n"
        f"🛠 **FSGen:** `{args.fsgen}`\n"
        f"🧹 **Clean:** `{args.install_clean}` | **Full:** `{args.full_clean}`\n"
        f"👤 **User:** `{args.user}`"
    )

    # --- STARTED ---
    if args.status == 'started':
        msg = (
            f"🟢 **Build Started**\n\n"
            f"{info_block}\n\n"
            f"📊 [Pipeline Overview]({args.build_url}pipeline-overview)"
        )
        bot.send_message(args.chat_id, msg, topic_id=args.topic_builder)
        return

    # --- ABORTED ---
    if args.status == 'aborted':
        msg = (
            f"⛔ **Build Aborted**\n\n"
            f"{info_block}\n\n"
            f"📊 [Pipeline Overview]({args.build_url}pipeline-overview)"
        )
        bot.send_message(args.chat_id, msg, topic_id=args.topic_builder)
        return

    # --- FAILURE ---
    if args.status == 'failure':
        print("Handling Build Failure...")
        log_link = "Not Available"
        
        # 1. Upload Log to Error Logs Topic
        # Prioritize out/error.log (Root of out)
        error_log_root = os.path.join(args.source_dir, 'out', 'error.log')
        # Also check device specific (just in case)
        error_log_device = os.path.join(out_dir, 'error.log')
        
        log_file_to_upload = None
        log_caption = f"❌ Error Log - {args.device}"
        
        if os.path.exists(error_log_root):
            print(f"Found error.log at: {error_log_root}")
            log_file_to_upload = error_log_root
        elif os.path.exists(error_log_device):
            print(f"Found error.log at: {error_log_device}")
            log_file_to_upload = error_log_device
        else:
            # Check for sync.log (Sync Failure)
            sync_log = os.path.join(workspace, 'sync.log')
            if os.path.exists(sync_log):
                 print("error.log not found, found sync.log. Tailing it...")
                 temp_log = "sync_failure_tail.txt"
                 with open(temp_log, 'w') as f:
                     f.write(get_file_tail(sync_log, 200))
                 log_file_to_upload = temp_log
                 log_caption = f"❌ Sync Log - {args.device}"
            else:
                # Create snippet from build.log (Build Failure)
                print("error.log and sync.log not found, tailing build.log...")
                build_log = os.path.join(workspace, 'build.log')
                if os.path.exists(build_log):
                    temp_log = "build_failure_tail.txt"
                    with open(temp_log, 'w') as f:
                        f.write(get_file_tail(build_log, 200))
                    log_file_to_upload = temp_log
        
        if log_file_to_upload:
            resp = bot.send_document(args.chat_id, log_file_to_upload, caption=log_caption, topic_id=args.topic_error_logs)
            if resp and 'result' in resp:
                msg_id = resp['result']['message_id']
                log_link = f"[View Log File]({create_telegram_link(args.chat_id, args.topic_error_logs, msg_id)})"
            
            # Clean up temp
            if log_file_to_upload in ["build_failure_tail.txt", "sync_failure_tail.txt"]:
                os.remove(log_file_to_upload)

        # 2. Send Notification to Builder Topic
        msg = (
            f"❌ **Build Failed**\n\n"
            f"{info_block}\n\n"
            f"📋 **Log:** {log_link}\n"
            f"📊 [Pipeline Overview]({args.build_url}pipeline-overview)"
        )
        bot.send_message(args.chat_id, msg, topic_id=args.topic_builder)
        return

    # --- SUCCESS ---
    print("Handling Build Success...")
    
    if not os.path.exists(out_dir):
        print(f"Error: Output directory not found: {out_dir}")
        bot.send_message(args.chat_id, f"⚠️ Build Success but Output Dir not found: `{out_dir}`", topic_id=args.topic_builder)
        return

    print(f"Searching for ZIPs in: {out_dir}")
    try:
        print(f"Files in dir: {os.listdir(out_dir)}")
    except Exception as e:
        print(f"Error listing dir: {e}")

    # Find ROM
    zip_pattern = os.path.join(out_dir, "AfterlifeOS*.zip")
    files = glob.glob(zip_pattern)
    
    if not files:
        bot.send_message(args.chat_id, f"⚠️ Build Success but ZIP not found in `{out_dir}`", topic_id=args.topic_builder)
        return
    
    rom_file = max(files, key=os.path.getctime)
    rom_name = os.path.basename(rom_file)
    
    # Upload GoFile
    gofile_link = upload_to_gofile(rom_file) or "Upload Failed"
    
    # Handle Release JSON
    json_link_md = ""
    is_release = (args.build_type.lower() == 'user') or (os.environ.get('RELEASE_BUILD') == 'true')
    
    if is_release:
        json_file = os.path.join(out_dir, f"{args.device}.json")
        if os.path.exists(json_file):
            resp = bot.send_document(
                args.chat_id, 
                json_file, 
                caption=f"📄 Release JSON - {args.device}", 
                topic_id=args.topic_release_json
            )
            if resp and 'result' in resp:
                msg_id = resp['result']['message_id']
                link = create_telegram_link(args.chat_id, args.topic_release_json, msg_id)
                json_link_md = f"\n📄 **JSON:** [View File]({link})"

    # Final Success Message
    msg = (
        f"✅ **Build Successfully**\n\n"
        f"{info_block}\n"
        f"📦 **File:** `{rom_name}`\n"
        f"🔗 [Download via GoFile]({gofile_link})"
        f"{json_link_md}"
    )
    bot.send_message(args.chat_id, msg, topic_id=args.topic_builder)

if __name__ == "__main__":
    main()
