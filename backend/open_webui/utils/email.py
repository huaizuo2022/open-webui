import smtplib
import random
import string
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from open_webui.env import (
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    SMTP_USE_TLS,
    SMTP_FROM_EMAIL,
    SMTP_FROM_NAME,
)

log = logging.getLogger(__name__)

# Store verification codes in memory (key: email, value: {code, expires_at})
_verification_codes = {}

def generate_verification_code(length=6):
    """Generate a numeric verification code."""
    return ''.join(random.choices(string.digits, k=length))


def store_verification_code(email, code, expiry_minutes=10):
    """Store verification code with expiry time."""
    expires_at = datetime.now() + timedelta(minutes=expiry_minutes)
    _verification_codes[email] = {
        'code': code,
        'expires_at': expires_at
    }
    cleanup_expired_codes()


def verify_code(email, code):
    """Verify if the code is valid for the given email."""
    if email not in _verification_codes:
        return False
    
    stored = _verification_codes[email]
    if datetime.now() > stored['expires_at']:
        del _verification_codes[email]
        return False
    
    if stored['code'] != code:
        return False
    
    del _verification_codes[email]
    return True


def cleanup_expired_codes():
    """Remove expired verification codes."""
    now = datetime.now()
    expired_emails = [
        email for email, data in _verification_codes.items()
        if now > data['expires_at']
    ]
    for email in expired_emails:
        del _verification_codes[email]


async def send_verification_email(email, code):
    """Send verification code to email address."""
    if not all([SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL]):
        log.warning("SMTP not configured properly. Cannot send verification email.")
        return False
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Your Verification Code'
        msg['From'] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg['To'] = email
        
        html_body = f"""
        <html>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #333;">Verification Code</h2>
                    <p>Your verification code is:</p>
                    <div style="background-color: #f4f4f4; padding: 20px; text-align: center; margin: 20px 0;">
                        <span style="font-size: 32px; font-weight: bold; color: #4F46E5; letter-spacing: 5px;">{code}</span>
                    </div>
                    <p>This code will expire in 10 minutes.</p>
                    <p>If you didn't request this code, please ignore this email.</p>
                </div>
            </body>
        </html>
        """
        
        text_body = f"Your verification code is: {code}\nThis code will expire in 10 minutes."
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            if SMTP_USE_TLS:
                server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        log.info(f"Verification email sent to {email}")
        return True
        
    except Exception as e:
        log.error(f"Failed to send verification email to {email}: {e}")
        return False
