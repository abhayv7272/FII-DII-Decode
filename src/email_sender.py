import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

class EmailSender:
    def __init__(self, recipient_email="abhayv7272@gmail.com"):
        self.recipient_email = recipient_email
        self.smtp_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("MAIL_PORT", 587))
        self.smtp_user = os.environ.get("MAIL_USERNAME", "")
        self.smtp_pass = os.environ.get("MAIL_PASSWORD", "")
        self.sender_email = os.environ.get("MAIL_FROM", self.smtp_user or "smart-money-bot@algorithmic.ai")

    def send_report(self, subject, html_content):
        if not self.smtp_user or not self.smtp_pass:
            print("[INFO] No SMTP credentials configured in environment. Saved local HTML report instead.")
            print(f"[INFO] Report is ready for automated dispatch to: {self.recipient_email}")
            return False
            
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Smart Money Intelligence <{self.sender_email}>"
            msg["To"] = self.recipient_email
            
            part = MIMEText(html_content, "html")
            msg.attach(part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.sender_email, self.recipient_email, msg.as_string())
                
            print(f"✅ Successfully dispatched daily report email to: {self.recipient_email}")
            return True
        except Exception as e:
            print(f"⚠️ Email dispatch error: {e}")
            return False
