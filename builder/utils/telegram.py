import os
import requests

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"

    def send_message(self, chat_id, text, topic_id=None, parse_mode="Markdown"):
        url = f"{self.api_url}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if topic_id:
            data["message_thread_id"] = topic_id
            
        try:
            response = requests.post(url, data=data)
            if not response.ok:
                print(f"[Telegram Error] Response: {response.text}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[Telegram Error] Failed to send message: {e}")
            return None

    def send_document(self, chat_id, file_path, caption=None, topic_id=None, parse_mode="Markdown"):
        url = f"{self.api_url}/sendDocument"
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": parse_mode
        }
        if topic_id:
            data["message_thread_id"] = topic_id

        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                response = requests.post(url, data=data, files=files)
                if not response.ok:
                    print(f"[Telegram Error] Response: {response.text}")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"[Telegram Error] Failed to send document: {e}")
            return None
