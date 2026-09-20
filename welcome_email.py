import threading
import time
from datetime import datetime, timedelta

from database import SessionLocal
import models
from email_util import send_email

CHECK_INTERVAL_SECONDS = 60
MIN_AGE_MINUTES = 5
MAX_AGE_MINUTES = 30  # don't email accounts that are old and just now getting checked (e.g. after a restart)


def _tips_for_role(role: str) -> str:
    if role == "freelancer":
        return (
            "- Post your first gig so buyers can find and hire you\n"
            "- Add a clear bio and pick the categories that match your skills\n"
            "- Reply quickly to messages — fast responses win more work\n"
            "- Check the \"For you\" feed on your home tab for open requests you can bid on"
        )
    if role == "vendor":
        return (
            "- List your first product with clear photos and pricing\n"
            "- Fill in your business name and store details on your profile\n"
            "- Keep your stock counts up to date so buyers know what's available\n"
            "- Check the Requests tab for buyers looking for what you sell"
        )
    return (
        "- Browse Freelancers or Products from the Home tab to see what's available\n"
        "- Post a request describing exactly what you need — sellers will come to you\n"
        "- Message anyone directly to ask questions before you commit\n"
        "- Save your favorite categories in your profile so your feed gets more relevant"
    )


def _send_welcome_email(user):
    tips = _tips_for_role(user.role)
    first_name = (user.full_name or "").split(" ")[0] or "there"

    text_body = (
        f"Hi {first_name},\n\n"
        f"Congratulations on joining CREET! We're glad to have you here.\n\n"
        f"A few tips to get the most out of it:\n{tips}\n\n"
        f"If you ever have questions or run into an issue, just reply to this email — a real person reads it.\n\n"
        f"Welcome aboard,\nThe CREET Team"
    )

    html_body = f"""
    <div style="font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #111;">
      <h2 style="margin-bottom: 4px;">Welcome to CREET, {first_name} 🎉</h2>
      <p style="color: #444; line-height: 1.5;">
        Congratulations on joining! We're glad to have you here.
      </p>
      <p style="color: #444; line-height: 1.5; margin-top: 20px;">
        <strong>A few tips to get started:</strong>
      </p>
      <ul style="color: #444; line-height: 1.7; padding-left: 20px;">
        {''.join(f"<li>{line.lstrip('- ')}</li>" for line in tips.split(chr(10)))}
      </ul>
      <p style="color: #444; line-height: 1.5; margin-top: 20px;">
        If you ever have questions or run into an issue, just reply to this email — a real person reads it.
      </p>
      <p style="margin-top: 24px; color: #111;">Welcome aboard,<br/>The CREET Team</p>
    </div>
    """

    send_email(user.email, "Welcome to CREET 🎉", text_body, html=html_body)


def _run_loop():
    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                candidates = (
                    db.query(models.User)
                    .filter(
                        models.User.welcome_email_sent.is_(False),
                        models.User.created_at <= now - timedelta(minutes=MIN_AGE_MINUTES),
                        models.User.created_at >= now - timedelta(minutes=MAX_AGE_MINUTES),
                    )
                    .all()
                )
                for user in candidates:
                    stayed = (
                        user.last_active
                        and user.last_active >= user.created_at + timedelta(minutes=MIN_AGE_MINUTES)
                    )
                    if not stayed:
                        continue
                    try:
                        _send_welcome_email(user)
                    except Exception as e:
                        print(f"[WELCOME EMAIL ERROR] user {user.id}: {e}")
                        continue
                    user.welcome_email_sent = True
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            print(f"[WELCOME EMAIL LOOP ERROR] {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


def start_welcome_email_scheduler():
    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()
