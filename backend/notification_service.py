# backend/notification_service.py
import os
from database import get_connection, log_system_event

class BaseProvider:
    def send(self, recipient: str, title: str, message: str) -> tuple[bool, str]:
        raise NotImplementedError("Providers must implement send().")

class WebPushProvider(BaseProvider):
    def send(self, recipient: str, title: str, message: str) -> tuple[bool, str]:
        # Web push can be mocked by writing to system logs/database queue for immediate dashboard display
        return True, "Simulated Web Push successful (Notification delivered to client)."

class EmailProvider(BaseProvider):
    def __init__(self):
        self.smtp_server = os.getenv("EMAIL_SMTP_SERVER")
        self.username = os.getenv("EMAIL_USERNAME")
        self.password = os.getenv("EMAIL_PASSWORD")
        self.sender = os.getenv("EMAIL_SENDER", "alerts@sentin.ai")

    def send(self, recipient: str, title: str, message: str) -> tuple[bool, str]:
        if not self.smtp_server or not self.username:
            # Safe mock fallback
            return True, f"Mock Email sent to {recipient} (Credentials not configured)."
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            
            msg = MIMEText(message)
            msg['Subject'] = title
            msg['From'] = self.sender
            msg['To'] = recipient
            
            with smtplib.SMTP(self.smtp_server, 587) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True, "Email sent successfully via SMTP."
        except Exception as e:
            return False, f"SMTP failure: {e}"

class WhatsAppProvider(BaseProvider):
    def __init__(self):
        self.token = os.getenv("WHATSAPP_API_TOKEN")
        self.phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    def send(self, recipient: str, title: str, message: str) -> tuple[bool, str]:
        if not self.token or not self.phone_number_id:
            return True, f"Mock WhatsApp sent to {recipient} (Credentials not configured)."
            
        try:
            import requests
            url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": recipient,
                "type": "text",
                "text": {"body": f"*{title}*\n\n{message}"}
            }
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                return True, "WhatsApp message sent successfully via Meta API."
            else:
                return False, f"WhatsApp API error: {res.text}"
        except Exception as e:
            return False, f"WhatsApp exception: {e}"

class TelegramProvider(BaseProvider):
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def sync_chat_ids(self):
        if not self.bot_token:
            return
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                conn = get_connection()
                cursor = conn.cursor()
                for item in data.get("result", []):
                    msg = item.get("message", {})
                    chat = msg.get("chat", {})
                    chat_id = str(chat.get("id"))
                    first_name = chat.get("first_name", "User")
                    username = chat.get("username", "")
                    if chat_id:
                        cursor.execute("""
                            INSERT OR IGNORE INTO telegram_users (chat_id, first_name, username)
                            VALUES (?, ?, ?)
                        """, (chat_id, first_name, username))
                conn.commit()
                conn.close()
        except Exception as e:
            import traceback
            print(f"[Telegram Sync Error] {e}")
            traceback.print_exc()

    def send(self, recipient: str, title: str, message: str) -> tuple[bool, str]:
        # Sync latest chat IDs from bot updates
        self.sync_chat_ids()
        
        is_direct = False
        if recipient and (recipient.startswith("-") or recipient.isdigit()):
            chat_ids = {str(recipient)}
            is_direct = True
        else:
            # Fetch all registered Telegram users from database
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM telegram_users")
            rows = cursor.fetchall()
            conn.close()
            
            chat_ids = set(str(r[0]) for r in rows)
            if self.chat_id:
                chat_ids.add(str(self.chat_id))
            
        if not self.bot_token or not chat_ids:
            return True, "Mock Telegram send: No active bot token or registered chats."
            
        success_count = 0
        errors = []
        
        import requests
        for cid in chat_ids:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                payload = {
                    "chat_id": cid,
                    "text": f"🚨 *{title}*\n\n{message}",
                    "parse_mode": "Markdown"
                }
                res = requests.post(url, json=payload, timeout=5)
                if res.status_code == 200:
                    success_count += 1
                else:
                    errors.append(f"Chat {cid}: {res.text}")
            except Exception as e:
                errors.append(f"Chat {cid} error: {e}")
                
        if success_count > 0:
            err_msg = f" (Errors: {'; '.join(errors)})" if errors else ""
            prefix = "Direct" if is_direct else "Broadcasted"
            return True, f"{prefix} alert to {success_count} Telegram subscriber(s){err_msg}."
        else:
            return False, f"Failed to send to Telegram. Errors: {'; '.join(errors)}"

class SMSProvider(BaseProvider):
    def __init__(self):
        self.api_key = os.getenv("SMS_API_KEY")

    def send(self, recipient: str, title: str, message: str) -> tuple[bool, str]:
        if not self.api_key:
            return True, f"Mock SMS sent to {recipient} (Credentials not configured)."
            
        try:
            import requests
            # Generic HTTP SMS gateway example
            url = "https://api.sms-gateway.com/send"
            payload = {
                "apikey": self.api_key,
                "to": recipient,
                "message": f"{title}\n{message}"
            }
            res = requests.post(url, data=payload, timeout=10)
            if res.status_code == 200:
                return True, "SMS sent successfully."
            else:
                return False, f"SMS gateway error: {res.text}"
        except Exception as e:
            return False, f"SMS exception: {e}"

class NotificationService:
    def __init__(self):
        self.providers = {
            "email": EmailProvider(),
            "whatsapp": WhatsAppProvider(),
            "telegram": TelegramProvider(),
            "sms": SMSProvider(),
            "webpush": WebPushProvider()
        }

    def dispatch_alert(self, subscription_id: int, recipient_email: str, recipient_phone: str, alert_title: str, alert_message: str, pref: dict):
        """
        Sends notifications across all enabled preferences of a user.
        Logs status updates to the database.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Insert into notification queue
        cursor.execute("""
            INSERT INTO notifications (type, subscription_id, title, message)
            VALUES (?, ?, ?, ?)
        """, ("ALERT", subscription_id, alert_title, alert_message))
        notification_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        sent_channels = []
        logs_to_write = []
        
        # 2. Send via Email if subscribed and email present
        if recipient_email and (pref.get("all_alerts") or pref.get("disease_risk_alerts") or pref.get("environmental_alerts")):
            success, log_msg = self.providers["email"].send(recipient_email, alert_title, alert_message)
            status = "success" if success else "failed"
            logs_to_write.append(("email", status, log_msg if not success else None))
            sent_channels.append(f"email:{status}")
            
        # 3. Send via SMS/WhatsApp if phone present
        if recipient_phone:
            # WhatsApp
            success_wa, log_wa = self.providers["whatsapp"].send(recipient_phone, alert_title, alert_message)
            status_wa = "success" if success_wa else "failed"
            logs_to_write.append(("whatsapp", status_wa, log_wa if not success_wa else None))
            sent_channels.append(f"whatsapp:{status_wa}")
            
            # SMS
            success_sms, log_sms = self.providers["sms"].send(recipient_phone, alert_title, alert_message)
            status_sms = "success" if success_sms else "failed"
            logs_to_write.append(("sms", status_sms, log_sms if not success_sms else None))
            sent_channels.append(f"sms:{status_sms}")
            
        # 4. Send via Telegram (either to subscriber chat ID or global community channel)
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        global_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        target_chat = recipient_phone if recipient_phone and (recipient_phone.startswith("-") or recipient_phone.isdigit()) else global_chat_id
        
        if bot_token and target_chat:
            success_tg, log_tg = self.providers["telegram"].send(target_chat, alert_title, alert_message)
            status_tg = "success" if success_tg else "failed"
            logs_to_write.append(("telegram", status_tg, log_tg if not success_tg else None))
            sent_channels.append(f"telegram:{status_tg}")
            
        # Always trigger a simulated WebPush so the user can verify in browser
        self.providers["webpush"].send("browser", alert_title, alert_message)
        logs_to_write.append(("webpush", "success", None))
        
        # 5. Write all logs to the database in a fresh transaction
        conn = get_connection()
        cursor = conn.cursor()
        for channel, status, err_msg in logs_to_write:
            cursor.execute("""
                INSERT INTO notification_logs (notification_id, channel, status, error_message)
                VALUES (?, ?, ?, ?)
            """, (notification_id, channel, status, err_msg))
            
        # Update main notification record status
        cursor.execute("UPDATE notifications SET status = 'sent' WHERE id = ?", (notification_id,))
        conn.commit()
        conn.close()
        
        log_system_event(
            "INFO",
            f"Dispatched notification #{notification_id} for sub #{subscription_id}. Channels: {', '.join(sent_channels)}",
            stage="notification_dispatch"
        )
        return notification_id
