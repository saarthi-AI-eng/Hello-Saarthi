"""Email sending utility — SMTP with HTML template for classroom invites.

If SMTP_HOST is not configured the invite is logged to console (dry-run).
Uses Python stdlib smtplib so no extra dependency is required.
"""

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from saarthi_backend.utils.config import get_settings

logger = logging.getLogger(__name__)


def _build_invite_html(
    inviter_name: str,
    course_title: str,
    invite_link: str,
    expires_hours: int = 72,
) -> tuple[str, str]:
    """Return (plain_text, html) for the invite email."""
    plain = (
        f"Hi,\n\n"
        f"{inviter_name} has invited you to join {course_title} on Saarthi.ai.\n\n"
        f"Click the link below to accept and get enrolled automatically:\n"
        f"{invite_link}\n\n"
        f"This link expires in {expires_hours} hours.\n\n"
        f"— The Saarthi Team"
    )
    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 520px; margin: 40px auto; background: #1a1d27; border-radius: 12px; overflow: hidden; border: 1px solid #2d3148; }}
    .header {{ background: #1FA89A; padding: 28px 32px; }}
    .header h1 {{ margin: 0; font-size: 22px; color: #fff; font-weight: 800; letter-spacing: -0.3px; }}
    .header p {{ margin: 4px 0 0; font-size: 13px; color: rgba(255,255,255,0.8); }}
    .body {{ padding: 28px 32px; }}
    .body p {{ font-size: 15px; line-height: 1.6; color: #cbd5e1; margin: 0 0 16px; }}
    .course-chip {{ display: inline-block; background: rgba(31,168,154,0.12); border: 1px solid rgba(31,168,154,0.3); border-radius: 8px; padding: 8px 16px; font-size: 15px; font-weight: 700; color: #1FA89A; margin: 4px 0 20px; }}
    .btn {{ display: inline-block; background: #1FA89A; color: #fff !important; text-decoration: none; padding: 13px 28px; border-radius: 8px; font-size: 15px; font-weight: 700; letter-spacing: 0.2px; }}
    .btn:hover {{ background: #178f83; }}
    .footer {{ padding: 16px 32px 24px; font-size: 12px; color: #64748b; border-top: 1px solid #2d3148; }}
    .footer a {{ color: #1FA89A; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>You've been invited to join a class</h1>
      <p>Saarthi.ai · AI-powered learning</p>
    </div>
    <div class="body">
      <p><strong>{inviter_name}</strong> has invited you to join:</p>
      <div class="course-chip">📚 {course_title}</div>
      <p>Click the button below to accept the invite and get enrolled automatically — no sign-up code needed.</p>
      <a href="{invite_link}" class="btn">Accept Invite &amp; Join Class →</a>
      <p style="margin-top:20px; font-size:13px; color:#64748b;">
        This link expires in {expires_hours} hours.<br/>
        If you weren't expecting this, you can safely ignore it.
      </p>
    </div>
    <div class="footer">
      You received this because {inviter_name} invited you to {course_title} on
      <a href="https://saarthi.app">saarthi.app</a>.
    </div>
  </div>
</body>
</html>"""
    return plain, html


async def send_invite_email(
    to_email: str,
    inviter_name: str,
    course_title: str,
    invite_code: str,
) -> None:
    """Send classroom invite email. Falls back to console log if SMTP not configured."""
    settings = get_settings()
    frontend_url = settings.app_frontend_url.rstrip("/")
    invite_link = f"{frontend_url}/join?code={invite_code}"

    plain, html = _build_invite_html(inviter_name, course_title, invite_link)

    if not settings.smtp_host:
        logger.info(
            "SMTP not configured — dry-run invite for %s | link: %s",
            to_email,
            invite_link,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"You're invited to join {course_title} on Saarthi.ai"
    msg["From"] = f"Saarthi.ai <{settings.smtp_from}>"
    msg["To"] = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, to_email, msg.as_string())
        logger.info("Invite email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send invite email to %s: %s", to_email, exc)
        # Don't raise — invite code was already created; teacher can share manually
