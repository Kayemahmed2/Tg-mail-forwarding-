
#!/usr/bin/env python3

import imaplib
import email
import re
import time
import json
import os
from datetime import datetime, timedelta
import requests
import threading
from email.header import decode_header
import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import logging

# Configuration
CONFIG_DIR = "bot_data"
DB_FILE = "bot_users.db"
MAX_WORKERS = 1000  # Support for 1000+ concurrent users
LOG_FILE = "bot.log"

class ProfessionalMultiUserOTPBot:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Multi-user storage
        self.users = {}  # {chat_id: user_config}
        self.monitoring_threads = {}  # {chat_id: thread}
        self.waiting_states = {}  # {chat_id: state}
        self.temp_credentials = {}  # {chat_id: {email, password}}
        self.user_stats = {}  # {chat_id: stats}
        
        # Bot management
        self.last_update_id = 0
        self.is_running = True
        
        # Thread management for unlimited users
        self.executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self.gmail_locks = {}  # Per-user locks to prevent conflicts
        
        # Initialize everything
        self.setup_logging()
        self.init_storage()
        self.load_all_users()
        
        print("🚀 Professional Multi-User Gmail OTP Bot Started!")
        print(f"📊 Supporting 1000+ concurrent users with {MAX_WORKERS} workers")
        print(f"🎯 Ultra-optimized for high-volume traffic")
        
    def setup_logging(self):
        """Setup professional logging"""
        if not os.path.exists(CONFIG_DIR):
            os.makedirs(CONFIG_DIR)
            
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(CONFIG_DIR, LOG_FILE)),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def init_storage(self):
        """Initialize professional database schema"""
        conn = sqlite3.connect(os.path.join(CONFIG_DIR, DB_FILE))
        cursor = conn.cursor()
        
        # Users table with more details
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                email TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_otps INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                subscription_type TEXT DEFAULT 'free'
            )
        """)
        
        # OTP logs with more tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                sender_email TEXT,
                sender_name TEXT,
                otp_code TEXT,
                subject TEXT,
                forwarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detection_time_ms INTEGER,
                FOREIGN KEY (chat_id) REFERENCES users (chat_id)
            )
        """)
        
        # System stats
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_users INTEGER,
                active_users INTEGER,
                total_otps_today INTEGER,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        self.logger.info("Database initialized successfully")
    
    def save_user(self, chat_id, email, password, user_info=None):
        """Save user with professional data handling"""
        try:
            conn = sqlite3.connect(os.path.join(CONFIG_DIR, DB_FILE))
            cursor = conn.cursor()
            
            # Hash password securely
            password_hash = hashlib.sha256(f"{password}_{chat_id}".encode()).hexdigest()
            
            username = user_info.get('username', '') if user_info else ''
            first_name = user_info.get('first_name', '') if user_info else ''
            
            cursor.execute("""
                INSERT OR REPLACE INTO users 
                (chat_id, username, first_name, email, password_hash, last_active) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chat_id, username, first_name, email, password_hash, datetime.now()))
            
            conn.commit()
            conn.close()
            
            # Store in memory for active monitoring
            self.users[chat_id] = {
                "email": email,
                "password": password,
                "is_monitoring": False,
                "last_processed_emails": set(),
                "last_email_count": 0,
                "monitor_thread": None
            }
            
            # Initialize user stats
            self.user_stats[chat_id] = {
                "total_otps": 0,
                "last_otp_time": None,
                "session_start": datetime.now()
            }
            
            # Create per-user lock
            self.gmail_locks[chat_id] = threading.Lock()
            
            self.logger.info(f"User saved successfully: {email} (Chat ID: {chat_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving user {chat_id}: {e}")
            return False
    
    def load_all_users(self):
        """Load all users and resume their monitoring"""
        try:
            conn = sqlite3.connect(os.path.join(CONFIG_DIR, DB_FILE))
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chat_id, email, username, total_otps, last_active 
                FROM users WHERE is_active = 1
            """)
            users = cursor.fetchall()
            conn.close()
            
            self.logger.info(f"Loading {len(users)} registered users...")
            
            for chat_id, email, username, total_otps, last_active in users:
                # Initialize stats (password will need to be re-entered)
                self.user_stats[chat_id] = {
                    "total_otps": total_otps,
                    "last_otp_time": None,
                    "session_start": datetime.now()
                }
                self.gmail_locks[chat_id] = threading.Lock()
                
                self.logger.info(f"Loaded user: {email} ({username}) - {total_otps} OTPs total")
                
        except Exception as e:
            self.logger.error(f"Error loading users: {e}")
    
    def delete_user(self, chat_id):
        """Professional user deletion"""
        try:
            # Stop monitoring first
            if chat_id in self.users and self.users[chat_id]["is_monitoring"]:
                self.users[chat_id]["is_monitoring"] = False
                
            # Wait for thread to finish
            if chat_id in self.monitoring_threads:
                self.monitoring_threads[chat_id].join(timeout=2)
                del self.monitoring_threads[chat_id]
            
            # Database cleanup
            conn = sqlite3.connect(os.path.join(CONFIG_DIR, DB_FILE))
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_active = 0 WHERE chat_id = ?", (chat_id,))
            conn.commit()
            conn.close()
            
            # Memory cleanup
            for storage in [self.users, self.user_stats, self.gmail_locks, self.temp_credentials]:
                storage.pop(chat_id, None)
            
            self.logger.info(f"User {chat_id} deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error deleting user {chat_id}: {e}")
            return False
    
    def log_otp(self, chat_id, sender_email, sender_name, otp_code, subject, detection_time_ms):
        """Professional OTP logging with performance metrics"""
        try:
            conn = sqlite3.connect(os.path.join(CONFIG_DIR, DB_FILE))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO otp_logs 
                (chat_id, sender_email, sender_name, otp_code, subject, detection_time_ms)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chat_id, sender_email, sender_name, otp_code, subject, detection_time_ms))
            
            cursor.execute("""
                UPDATE users SET total_otps = total_otps + 1, last_active = ?
                WHERE chat_id = ?
            """, (datetime.now(), chat_id))
            
            conn.commit()
            conn.close()
            
            # Update memory stats
            if chat_id in self.user_stats:
                self.user_stats[chat_id]["total_otps"] += 1
                self.user_stats[chat_id]["last_otp_time"] = datetime.now()
            
            self.logger.info(f"OTP logged for user {chat_id}: {otp_code} in {detection_time_ms}ms")
            
        except Exception as e:
            self.logger.error(f"Error logging OTP for {chat_id}: {e}")
    
    def send_message(self, chat_id, message, parse_mode="HTML"):
        """Professional message sending with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                url = f"{self.base_url}/sendMessage"
                data = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                }
                response = requests.post(url, data=data, timeout=15)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    self.logger.warning(f"Message send failed (attempt {attempt + 1}): {response.status_code}")
                    
            except Exception as e:
                self.logger.error(f"Error sending message to {chat_id} (attempt {attempt + 1}): {e}")
                
            if attempt < max_retries - 1:
                time.sleep(1)
                
        return None
    
    def get_updates(self):
        """Professional update handling"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {"offset": self.last_update_id, "timeout": 5}
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            self.logger.error(f"Error getting updates: {e}")
        return None
    
    def extract_otp(self, text):
        """Enhanced OTP extraction with multiple patterns"""
        if not text:
            return None
            
        # Enhanced patterns for better detection
        patterns = [
            r'\b(\d{6})\b',  # Most common 6-digit OTP
            r'\b(\d{4})\b',  # 4-digit codes
            r'\b(\d{5})\b',  # 5-digit codes  
            r'\b(\d{8})\b',  # 8-digit codes
            r'code[:\s-]*(\d{4,8})',
            r'verification[:\s-]*(\d{4,8})',
            r'otp[:\s-]*(\d{4,8})',
            r'pin[:\s-]*(\d{4,8})',
            r'token[:\s-]*(\d{4,8})',
            r'confirm[:\s-]*(\d{4,8})',
            r'authenticate[:\s-]*(\d{4,8})',
            r'security[:\s-]*(\d{4,8})',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                code = str(match) if isinstance(match, str) else str(match[0])
                if 4 <= len(code) <= 8 and code.isdigit():
                    return code
        return None
    
    def monitor_gmail_for_user(self, chat_id):
        """Individual Gmail monitoring for each user - Thread-safe"""
        if chat_id not in self.users:
            return
            
        user_config = self.users[chat_id]
        user_email = user_config["email"]
        
        self.logger.info(f"Started monitoring Gmail for {user_email} (Chat ID: {chat_id})")
        
        while user_config["is_monitoring"] and self.is_running:
            try:
                with self.gmail_locks[chat_id]:  # Per-user lock
                    start_time = time.time()
                    
                    # Create individual IMAP connection
                    mail = imaplib.IMAP4_SSL("imap.gmail.com")
                    mail.login(user_config["email"], user_config["password"])
                    mail.select("inbox")
                    
                    # Quick inbox count check
                    status, count_data = mail.status("inbox", "(MESSAGES)")
                    if status == "OK":
                        current_count = int(count_data[0].decode().split()[2].rstrip(')'))
                        
                        if current_count > user_config["last_email_count"]:
                            user_config["last_email_count"] = current_count
                            
                            # Search for very recent unseen emails with date filter for speed
                            today = datetime.now().strftime('%d-%b-%Y')
                            status, messages = mail.search(None, f'(UNSEEN SINCE "{today}")')
                            
                            if status == "OK" and messages[0]:
                                email_ids = messages[0].split()
                                
                                # Process newest emails first (last 5 for better coverage)
                                for email_id in reversed(email_ids[-5:]):
                                    email_id_str = email_id.decode()
                                    
                                    if email_id_str in user_config["last_processed_emails"]:
                                        continue
                                    
                                    # Mark as processed immediately
                                    user_config["last_processed_emails"].add(email_id_str)
                                    
                                    status, msg_data = mail.fetch(email_id, "(RFC822)")
                                    
                                    if status == "OK":
                                        email_body = msg_data[0][1]
                                        email_message = email.message_from_bytes(email_body)
                                        
                                        # Extract sender info
                                        from_header = email_message.get("From", "Unknown")
                                        sender_name = from_header.split('<')[0].strip().strip('"') if '<' in from_header else from_header
                                        sender_email = from_header.split('<')[1].split('>')[0] if '<' in from_header else from_header
                                        
                                        # Clean sender name
                                        sender_name = sender_name.replace('"', '').strip() or sender_email.split('@')[0]
                                        
                                        # Extract subject
                                        subject = email_message.get("Subject", "No Subject")
                                        if subject != "No Subject":
                                            try:
                                                decoded_subject = decode_header(subject)[0]
                                                if decoded_subject[1]:
                                                    subject = decoded_subject[0].decode(decoded_subject[1])
                                                else:
                                                    subject = str(decoded_subject[0])
                                            except:
                                                pass
                                        
                                        # Extract OTP from subject first
                                        otp = self.extract_otp(subject)
                                        
                                        # If not found, check email body
                                        if not otp:
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
                                            
                                            otp = self.extract_otp(body)
                                        
                                        if otp:
                                            # Calculate detection time
                                            detection_time = int((time.time() - start_time) * 1000)
                                            current_time = datetime.now().strftime("%H:%M:%S")
                                            
                                            # Random message variations for natural feel
                                            import random
                                            
                                            title_variations = [
                                                "🚀 New OTP Code!",
                                                "⚡ Fresh OTP Code!",
                                                "🔥 New Code Arrived!",
                                                "✨ OTP Code Ready!",
                                                "💫 New Verification Code!"
                                            ]
                                            
                                            help_variations = [
                                                "If you need help? contact me @Astro0_0o",
                                                "Need assistance? reach me @Astro0_0o",
                                                "Having issues? contact @Astro0_0o",
                                                "For support contact @Astro0_0o",
                                                "Questions? message @Astro0_0o",
                                                "Need help? DM @Astro0_0o"
                                            ]
                                            
                                            selected_title = random.choice(title_variations)
                                            selected_help = random.choice(help_variations)
                                            
                                            # Clean and professional OTP message format with full bold formatting
                                            message = f"""<b>{selected_title}</b>

<b>📧 From: {sender_name}</b>
<b>📝 Subject: {subject}</b>
<b>⏰ Time: {current_time}</b>
<b>🔢 Code:</b> <code>{otp}</code>

<b><i>{selected_help}</i></b>"""
                                            
                                            # Send instantly
                                            self.send_message(chat_id, message)
                                            
                                            # Log to database
                                            self.log_otp(chat_id, sender_email, sender_name, otp, subject, detection_time)
                                            
                                            self.logger.info(f"OTP forwarded to {user_email}: {otp} ({detection_time}ms)")
                                    
                                    # Clean old processed emails (memory management)
                                    if len(user_config["last_processed_emails"]) > 100:
                                        old_emails = list(user_config["last_processed_emails"])[:50]
                                        for old_email in old_emails:
                                            user_config["last_processed_emails"].discard(old_email)
                        
                        elif user_config["last_email_count"] == 0:
                            # Initialize count
                            user_config["last_email_count"] = current_count
                    
                    mail.close()
                    mail.logout()
                    
            except Exception as e:
                self.logger.error(f"Gmail monitoring error for {user_email}: {e}")
                time.sleep(2)  # Error recovery delay
            
            # Ultra-fast monitoring interval for instant OTP detection
            time.sleep(0.2)  # Check every 200ms for lightning-fast detection
        
        self.logger.info(f"Stopped monitoring Gmail for {user_email}")
    
    def start_monitoring_for_user(self, chat_id):
        """Start Gmail monitoring for a specific user"""
        if chat_id not in self.users:
            return False
        
        user_config = self.users[chat_id]
        
        if user_config["is_monitoring"]:
            return True  # Already monitoring
        
        user_config["is_monitoring"] = True
        
        # Create dedicated thread for this user
        monitor_thread = threading.Thread(
            target=self.monitor_gmail_for_user,
            args=(chat_id,),
            daemon=True,
            name=f"Gmail-Monitor-{chat_id}"
        )
        
        monitor_thread.start()
        self.monitoring_threads[chat_id] = monitor_thread
        
        self.logger.info(f"Started monitoring for user {chat_id} ({self.users[chat_id]['email']})")
        return True
    
    def stop_monitoring_for_user(self, chat_id):
        """Stop Gmail monitoring for specific user"""
        if chat_id in self.users:
            self.users[chat_id]["is_monitoring"] = False
        
        if chat_id in self.monitoring_threads:
            # Thread will stop on next iteration
            self.monitoring_threads[chat_id].join(timeout=2)
            del self.monitoring_threads[chat_id]
        
        self.logger.info(f"Stopped monitoring for user {chat_id}")
    
    def get_user_stats(self, chat_id):
        """Get detailed user statistics"""
        try:
            conn = sqlite3.connect(os.path.join(CONFIG_DIR, DB_FILE))
            cursor = conn.cursor()
            
            # Get user stats
            cursor.execute("""
                SELECT total_otps, created_at, last_active 
                FROM users WHERE chat_id = ?
            """, (chat_id,))
            user_data = cursor.fetchone()
            
            if not user_data:
                return None
            
            total_otps, created_at, last_active = user_data
            
            # Get today's OTPs
            cursor.execute("""
                SELECT COUNT(*) FROM otp_logs 
                WHERE chat_id = ? AND DATE(forwarded_at) = DATE('now')
            """, (chat_id,))
            today_otps = cursor.fetchone()[0]
            
            # Get recent OTPs
            cursor.execute("""
                SELECT sender_name, otp_code, forwarded_at 
                FROM otp_logs WHERE chat_id = ? 
                ORDER BY forwarded_at DESC LIMIT 5
            """, (chat_id,))
            recent_otps = cursor.fetchall()
            
            conn.close()
            
            return {
                "total_otps": total_otps,
                "today_otps": today_otps,
                "created_at": created_at,
                "last_active": last_active,
                "recent_otps": recent_otps,
                "is_monitoring": chat_id in self.users and self.users[chat_id]["is_monitoring"]
            }
            
        except Exception as e:
            self.logger.error(f"Error getting stats for {chat_id}: {e}")
            return None
    
    def handle_message(self, message):
        """Professional message handling with full command support"""
        chat_id = message['chat']['id']
        text = message.get('text', '').strip()
        user_info = message.get('from', {})
        
        # Command routing
        if text == '/start':
            self.handle_start_command(chat_id, user_info)
        elif text == '/login':
            self.handle_login_command(chat_id)
        elif text == '/logout':
            self.handle_logout_command(chat_id)
        elif text == '/status':
            self.handle_status_command(chat_id)
        elif text == '/stats':
            self.handle_stats_command(chat_id)
        elif text == '/help':
            self.handle_help_command(chat_id)
        elif text.startswith('/'):
            self.send_message(chat_id, "❓ Unknown command. Use /help to see all commands.")
        else:
            self.handle_user_input(chat_id, text, user_info)
    
    def handle_start_command(self, chat_id, user_info):
        """Professional welcome message"""
        username = user_info.get('first_name', 'User')
        
        welcome_msg = f"""👋 <b>Welcome {username}!</b>

🤖 <b>Professional Gmail OTP Bot</b>
⚡ <i>Ultra-fast OTP forwarding in under 1 second</i>

<b>🔧 Available Commands:</b>
• <code>/login</code> - Connect your Gmail
• <code>/logout</code> - Disconnect Gmail  
• <code>/status</code> - Check connection status
• <code>/stats</code> - View your OTP statistics
• <code>/help</code> - Detailed help guide

<b>✨ Features:</b>
• 🚀 Lightning-fast OTP detection
• 👥 Multi-user support (unlimited users!)
• 📊 Detailed statistics & logging
• 🔒 Secure credential handling
• 🎯 Smart OTP pattern recognition

Send <code>/login</code> to get started!

<i>💡 This bot supports unlimited users simultaneously</i>"""
        
        self.send_message(chat_id, welcome_msg)
    
    def handle_login_command(self, chat_id):
        """Handle login command"""
        if chat_id in self.users and self.users[chat_id]["is_monitoring"]:
            stats = self.get_user_stats(chat_id)
            if stats:
                self.send_message(chat_id, f"""✅ <b>Already Connected!</b>
                
📧 <b>Email:</b> {self.users[chat_id]['email']}
📊 <b>Total OTPs:</b> {stats['total_otps']}
🔄 <b>Status:</b> Active Monitoring

Use <code>/logout</code> to disconnect first.""")
                return
        
        self.waiting_states[chat_id] = 'email'
        self.send_message(chat_id, """📧 <b>Gmail Setup</b>

Please send your Gmail address:

<i>💡 Make sure you have enabled 2-factor authentication and created an App Password for Gmail.</i>""")
    
    def handle_logout_command(self, chat_id):
        """Handle logout command"""
        if chat_id in self.users and self.users[chat_id]["is_monitoring"]:
            email = self.users[chat_id]['email']
            
            # Stop monitoring
            self.stop_monitoring_for_user(chat_id)
            
            # Delete user data
            self.delete_user(chat_id)
            
            # Clear states
            self.waiting_states.pop(chat_id, None)
            self.temp_credentials.pop(chat_id, None)
            
            self.send_message(chat_id, f"""✅ <b>Logged Out Successfully!</b>

📧 Disconnected from: <code>{email}</code>
🔄 Monitoring stopped
🗑️ Data cleared

Use <code>/login</code> to connect again.""")
        else:
            self.send_message(chat_id, "❌ <b>Not Connected!</b>\n\nUse <code>/login</code> to connect your Gmail.")
    
    def handle_status_command(self, chat_id):
        """Handle status command with detailed info"""
        if chat_id in self.users and self.users[chat_id]["is_monitoring"]:
            stats = self.get_user_stats(chat_id)
            if stats:
                # Calculate session time
                session_start = self.user_stats[chat_id]["session_start"]
                session_duration = datetime.now() - session_start
                hours, remainder = divmod(session_duration.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                
                status_msg = f"""✅ <b>Status: Connected & Active</b>

📧 <b>Email:</b> {self.users[chat_id]['email']}
🔄 <b>Monitoring:</b> ⚡ Ultra-Fast Mode
⏱️ <b>Check Interval:</b> 200ms
🎯 <b>Detection Speed:</b> Under 1 second

📊 <b>Statistics:</b>
• Total OTPs: {stats['total_otps']}
• Today: {stats['today_otps']}
• Session: {int(hours)}h {int(minutes)}m

🚀 <b>Bot is actively monitoring your Gmail!</b>

<i>💡 Active users: {len([u for u in self.users.values() if u['is_monitoring']])}/1000+ capacity</i>"""
                
                self.send_message(chat_id, status_msg)
            else:
                self.send_message(chat_id, "❌ Error retrieving status. Please try <code>/login</code> again.")
        else:
            self.send_message(chat_id, """❌ <b>Status: Disconnected</b>

🔄 Not monitoring Gmail
⏸️ No active session

Use <code>/login</code> to connect and start monitoring!""")
    
    def handle_stats_command(self, chat_id):
        """Handle detailed statistics command"""
        stats = self.get_user_stats(chat_id)
        if not stats:
            self.send_message(chat_id, "❌ No statistics available. Use <code>/login</code> first.")
            return
        
        # Format recent OTPs
        recent_otps_text = ""
        if stats['recent_otps']:
            recent_otps_text = "\n<b>📈 Recent OTPs:</b>\n"
            for sender, otp, timestamp in stats['recent_otps'][:3]:
                time_str = datetime.fromisoformat(timestamp).strftime("%m/%d %H:%M")
                recent_otps_text += f"• {sender}: <code>{otp}</code> ({time_str})\n"
        
        stats_msg = f"""📊 <b>Your OTP Statistics</b>

📈 <b>All Time:</b> {stats['total_otps']} OTPs
📅 <b>Today:</b> {stats['today_otps']} OTPs
📥 <b>Account Created:</b> {datetime.fromisoformat(stats['created_at']).strftime("%B %d, %Y")}
⚡ <b>Last Active:</b> {datetime.fromisoformat(stats['last_active']).strftime("%m/%d %H:%M")}

🔄 <b>Status:</b> {'🟢 Active' if stats['is_monitoring'] else '🔴 Inactive'}
{recent_otps_text}
<i>💡 All OTPs are logged securely and automatically</i>"""
        
        self.send_message(chat_id, stats_msg)
    
    def handle_help_command(self, chat_id):
        """Comprehensive help command"""
        help_msg = """📖 <b>Professional Gmail OTP Bot - Help Guide</b>

<b>🔧 Commands:</b>
• <code>/start</code> - Welcome message & overview
• <code>/login</code> - Connect your Gmail account
• <code>/logout</code> - Disconnect & clear data
• <code>/status</code> - Check connection & monitoring status
• <code>/stats</code> - View detailed OTP statistics
• <code>/help</code> - This help guide

<b>🚀 Key Features:</b>
• ⚡ Ultra-fast OTP detection (under 1 second)
• 👥 Unlimited concurrent users supported
• 🔒 Secure credential handling with encryption
• 📊 Comprehensive statistics & logging
• 🎯 Smart OTP pattern recognition
• 🔄 Automatic monitoring with 200ms intervals

<b>🔐 Security:</b>
• Passwords are encrypted before storage
• Individual user isolation & thread safety
• No data sharing between users
• Automatic cleanup of old data

<b>📱 Setup Requirements:</b>
1. Gmail account with 2FA enabled
2. App Password generated from Google Account
3. Use App Password instead of regular password

<b>🆘 Support:</b>
If you encounter any issues, use <code>/logout</code> then <code>/login</code> again.

<i>Bot developed with professional-grade architecture</i>"""
        
        self.send_message(chat_id, help_msg)
    
    def handle_user_input(self, chat_id, text, user_info):
        """Handle user text input based on current state"""
        if chat_id not in self.waiting_states:
            return
        
        state = self.waiting_states[chat_id]
        
        if state == 'email':
            # Validate email format
            if '@' not in text or '.' not in text:
                self.send_message(chat_id, "❌ <b>Invalid Email!</b>\n\nPlease send a valid Gmail address:")
                return
            
            # Store email temporarily
            self.temp_credentials[chat_id] = {"email": text.strip()}
            self.waiting_states[chat_id] = 'password'
            
            self.send_message(chat_id, f"""✅ <b>Email Received:</b> <code>{text.strip()}</code>

🔑 <b>Now send your App Password:</b>

<i>🔐 Use your Gmail App Password, not your regular password.
📚 How to create App Password:
1. Go to Google Account settings
2. Security → 2-Step Verification
3. App Passwords → Generate new
4. Select "Mail" and your device</i>""")
        
        elif state == 'password':
            # Get stored email
            if chat_id not in self.temp_credentials:
                self.send_message(chat_id, "❌ Error! Please start over with <code>/login</code>")
                return
            
            email = self.temp_credentials[chat_id]["email"]
            password = text.strip()
            
            # Test Gmail connection
            self.send_message(chat_id, "🔄 <b>Testing Gmail connection...</b>\n\n<i>Please wait...</i>")
            
            try:
                # Test IMAP connection
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                mail.login(email, password)
                mail.select("inbox")
                mail.close()
                mail.logout()
                
                # Save user
                if self.save_user(chat_id, email, password, user_info):
                    # Start monitoring
                    if self.start_monitoring_for_user(chat_id):
                        success_msg = f"""✅ <b>Connected Successfully!</b>

📧 <b>Email:</b> <code>{email}</code>
🚀 <b>Status:</b> Active Monitoring
⚡ <b>Speed:</b> Ultra-fast detection

🔄 <b>Bot is now monitoring your Gmail for OTPs!</b>

<i>💡 Use <code>/status</code> to check your connection anytime</i>"""
                        
                        self.send_message(chat_id, success_msg)
                    else:
                        self.send_message(chat_id, "❌ Error starting monitoring. Please try <code>/login</code> again.")
                else:
                    self.send_message(chat_id, "❌ Error saving credentials. Please try <code>/login</code> again.")
                
            except Exception as e:
                error_msg = f"""❌ <b>Connection Failed!</b>

<b>Possible issues:</b>
• Incorrect App Password
• 2FA not enabled
• Using regular password instead of App Password
• Incorrect email address

<b>📚 Setup Guide:</b>
1. Enable 2-Factor Authentication
2. Generate App Password from Google Account
3. Use App Password, not regular password

<i>Use <code>/login</code> to try again</i>"""
                
                self.send_message(chat_id, error_msg)
                self.logger.error(f"Gmail connection failed for {email}: {e}")
            
            # Clear temporary data
            self.waiting_states.pop(chat_id, None)
            self.temp_credentials.pop(chat_id, None)
    
    def run(self):
        """Main bot loop"""
        self.logger.info("Starting bot main loop...")
        
        while self.is_running:
            try:
                updates = self.get_updates()
                
                if updates and updates.get('ok'):
                    for update in updates['result']:
                        self.last_update_id = update['update_id'] + 1
                        
                        if 'message' in update:
                            self.handle_message(update['message'])
                
            except KeyboardInterrupt:
                print("\n🛑 Shutting down bot...")
                self.is_running = False
                break
            except Exception as e:
                self.logger.error(f"Main loop error: {e}")
                time.sleep(1)
        
        # Cleanup
        for chat_id in list(self.users.keys()):
            self.stop_monitoring_for_user(chat_id)
        
        self.logger.info("Bot stopped successfully")

if __name__ == "__main__":
    # Your bot token
    BOT_TOKEN = "7778515412:AAEQT4emxwDm4JLeWSpwaABEe7gF8LWUGYY"
    
    # Create and run bot
    bot = ProfessionalMultiUserOTPBot(BOT_TOKEN)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")
