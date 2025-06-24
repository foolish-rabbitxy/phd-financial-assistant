# src/utils/mail.py

import smtplib
from email.mime.text import MIMEText
import os

def send_email(subject, html_body):
    from_email = os.getenv("EMAIL_SENDER")
    to_email = os.getenv("EMAIL_RECIPIENT")
    password = os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", 587))

    if not all([from_email, to_email, password]):
        raise RuntimeError("Missing email configuration in environment variables (.env)")

    msg = MIMEText(html_body, "html")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, [to_email], msg.as_string())
    print(f"Email sent to {to_email} with subject: {subject}")      
    