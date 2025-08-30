
#!/usr/bin/env python3

import imaplib
import email
import re
import time
import json
import os
from datetime import datetime
import requests
import threading
from email.header import decode_header

# Configuration file path
CONFIG_FILE = "bot_config.json"

class GmailOTPBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.gmail_config = {}
        self.is_running = False
        self.last_processed_emails = set()
        
    def load_config(self):
        """Load Gmail configuration from file"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self.gmail_config = json.load(f)
                return True
            except:
                return False
        return False
    
    def save_config(self, email, password, chat_id):
        """Save Gmail configuration to file"""
        self.gmail_config = {
            "email": email,
            "password": password,
            "chat_id": chat_id
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.gmail_config, f)
            return True
        except:
            return False
    
    def delete_config(self):
        """Delete configuration file"""
        try:
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            self.gmail_config = {}
            return True
        except:
            return False
    
    def send_message(self, chat_id, message, parse_mode="HTML"):
        """Send message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, data=data, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error sending message: {e}")
            return None
    
    def get_updates(self, offset=0):
        """Get updates from Telegram"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {"offset": offset, "timeout": 10}
            response = requests.get(url, params=params, timeout=15)
            return response.json()
        except Exception as e:
            print(f"Error getting updates: {e}")
            return None
    
    def extract_otp_from_subject(self, subject):
        """Extract OTP from email subject"""
        patterns = [
            r'\b\d{4,8}\b',  # 4-8 digit numbers
            r'code[:\s-]*(\d{4,8})',  # Code: 123456
            r'verification[:\s-]*(\d{4,8})',  # Verification: 123456
            r'otp[:\s-]*(\d{4,8})',  # OTP: 123456
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                if len(match.groups()) > 0:
                    return match.group(1)
                else:
                    return match.group(0)
        return None
    
    def extract_otp_from_body(self, body):
        """Extract OTP from email body"""
        patterns = [
            r'\b\d{4,8}\b',  # 4-8 digit numbers
            r'code[:\s-]*(\d{4,8})',
            r'verification[:\s-]*(\d{4,8})',
            r'otp[:\s-]*(\d{4,8})',
            r'pin[:\s-]*(\d{4,8})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                # Return the first numeric match that looks like an OTP
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match[0] else match[1]
                    if 4 <= len(match) <= 8:
                        return match
        return None
    
    def check_gmail(self):
        """Check Gmail for new OTP emails"""
        if not self.gmail_config:
            return
        
        try:
            # Connect to Gmail IMAP
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(self.gmail_config["email"], self.gmail_config["password"])
            mail.select("inbox")
            
            # Search for recent emails (last 10 minutes)
            status, messages = mail.search(None, 'UNSEEN')
            
            if status == "OK" and messages[0]:
                email_ids = messages[0].split()
                
                for email_id in email_ids[-10:]:  # Check last 10 emails
                    if email_id.decode() in self.last_processed_emails:
                        continue
                    
                    # Fetch email
                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                    
                    if status == "OK":
                        email_body = msg_data[0][1]
                        email_message = email.message_from_bytes(email_body)
                        
                        # Get sender
                        from_header = email_message["From"]
                        if from_header:
                            sender = from_header.split('<')[0].strip().strip('"')
                            if '<' in from_header:
                                sender_email = from_header.split('<')[1].split('>')[0]
                            else:
                                sender_email = from_header
                        else:
                            sender = "Unknown"
                            sender_email = "Unknown"
                        
                        # Get subject
                        subject = email_message["Subject"]
                        if subject:
                            decoded_subject = decode_header(subject)[0]
                            if decoded_subject[1]:
                                subject = decoded_subject[0].decode(decoded_subject[1])
                            else:
                                subject = str(decoded_subject[0])
                        else:
                            subject = "No Subject"
                        
                        # Get email body
                        body = ""
                        if email_message.is_multipart():
                            for part in email_message.walk():
                                if part.get_content_type() == "text/plain":
                                    try:
                                        body = part.get_payload(decode=True).decode('utf-8')
                                        break
                                    except:
                                        continue
                        else:
                            try:
                                body = email_message.get_payload(decode=True).decode('utf-8')
                            except:
                                body = str(email_message.get_payload())
                        
                        # Extract OTP
                        otp = self.extract_otp_from_subject(subject)
                        if not otp:
                            otp = self.extract_otp_from_body(body)
                        
                        if otp:
                            # Get current time
                            current_time = datetime.now().strftime("%H:%M:%S")
                            
                            # Format message
                            message = f"""🚀 <b>New OTP arrived!</b>

📧 <b>From:</b> {sender}
📝 <b>Subject:</b> {subject}
⏰ <b>Time:</b> {current_time}
🔢 <b>Code:</b> <code>{otp}</code>

📬 <b>Sender Email:</b> {sender_email}"""
                            
                            # Send to Telegram
                            self.send_message(self.gmail_config["chat_id"], message)
                            print(f"OTP sent: {otp} from {sender}")
                        
                        # Mark as processed
                        self.last_processed_emails.add(email_id.decode())
            
            mail.close()
            mail.logout()
            
        except Exception as e:
            print(f"Error checking Gmail: {e}")
            if self.gmail_config.get("chat_id"):
                self.send_message(self.gmail_config["chat_id"], f"❌ Gmail check error: {str(e)}")
    
    def monitor_gmail(self):
        """Monitor Gmail continuously"""
        print("Starting Gmail monitoring...")
        while self.is_running:
            try:
                self.check_gmail()
                time.sleep(5)  # Check every 5 seconds
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(10)
    
    def handle_message(self, message):
        """Handle incoming Telegram messages"""
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        
        if text == '/start':
            welcome_msg = """🤖 <b>Gmail OTP Bot</b>

Available commands:
• <code>/login</code> - Login to Gmail
• <code>/logout</code> - Logout from Gmail
• <code>/status</code> - Check login status
• <code>/start</code> - Show this menu

Send /login to start monitoring your Gmail for OTP codes!"""
            self.send_message(chat_id, welcome_msg)
            
        elif text == '/login':
            if self.gmail_config and self.is_running:
                self.send_message(chat_id, "✅ Already logged in! Use /logout to logout first.")
                return
            
            self.send_message(chat_id, "📧 Please send your Gmail address:")
            # Wait for email
            self.waiting_for_email = chat_id
            
        elif text == '/logout':
            if self.gmail_config:
                self.is_running = False
                self.delete_config()
                self.send_message(chat_id, "✅ Logged out successfully!")
            else:
                self.send_message(chat_id, "❌ Not logged in!")
                
        elif text == '/status':
            if self.gmail_config and self.is_running:
                status_msg = f"""✅ <b>Status: Active</b>

📧 <b>Email:</b> {self.gmail_config.get('email', 'Unknown')}
🔄 <b>Monitoring:</b> Running
⏰ <b>Check Interval:</b> 5 seconds

Bot is monitoring your Gmail for OTP codes!"""
                self.send_message(chat_id, status_msg)
            else:
                self.send_message(chat_id, "❌ <b>Status: Inactive</b>\n\nUse /login to start monitoring!")
        
        elif hasattr(self, 'waiting_for_email') and self.waiting_for_email == chat_id:
            # Received email
            if '@gmail.com' in text:
                self.temp_email = text
                self.send_message(chat_id, "🔑 Please send your Gmail app password:")
                self.waiting_for_password = chat_id
                delattr(self, 'waiting_for_email')
            else:
                self.send_message(chat_id, "❌ Please send a valid Gmail address!")
                
        elif hasattr(self, 'waiting_for_password') and self.waiting_for_password == chat_id:
            # Received password
            password = text.replace(' ', '')  # Remove spaces
            
            # Test login
            try:
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(self.temp_email, password)
                mail.logout()
                
                # Save config and start monitoring
                self.save_config(self.temp_email, password, chat_id)
                self.is_running = True
                
                # Start monitoring thread
                monitor_thread = threading.Thread(target=self.monitor_gmail, daemon=True)
                monitor_thread.start()
                
                success_msg = f"""✅ <b>Login Successful!</b>

📧 <b>Email:</b> {self.temp_email}
🔄 <b>Status:</b> Monitoring started
⏰ <b>Check Interval:</b> 5 seconds

Bot will now forward all OTP codes from your Gmail instantly!"""
                self.send_message(chat_id, success_msg)
                
                delattr(self, 'waiting_for_password')
                delattr(self, 'temp_email')
                
            except Exception as e:
                self.send_message(chat_id, f"❌ Login failed! Error: {str(e)}\n\nPlease check your credentials and try again with /login")
                delattr(self, 'waiting_for_password')
                delattr(self, 'temp_email')
        
        else:
            self.send_message(chat_id, "❓ Unknown command! Use /start to see available commands.")
    
    def run(self):
        """Run the bot"""
        print("Starting Telegram OTP Bot...")
        
        # Load existing config
        if self.load_config():
            self.is_running = True
            monitor_thread = threading.Thread(target=self.monitor_gmail, daemon=True)
            monitor_thread.start()
            print(f"Resumed monitoring for: {self.gmail_config['email']}")
        
        offset = 0
        
        while True:
            try:
                updates = self.get_updates(offset)
                
                if updates and updates.get("ok"):
                    for update in updates["result"]:
                        offset = update["update_id"] + 1
                        
                        if "message" in update:
                            self.handle_message(update["message"])
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nBot stopped by user")
                self.is_running = False
                break
            except Exception as e:
                print(f"Bot error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    # Your bot token
    BOT_TOKEN = "7778515412:AAEQT4emxwDm4JLeWSpwaABEe7gF8LWUGYY"
    
    # Create and run bot
    bot = GmailOTPBot(BOT_TOKEN)
    bot.run()
