import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

HITL_NOTIFY_CHANNEL = os.getenv("HITL_NOTIFY_CHANNEL", "email")  # email | slack | none

# Email (Resend SMTP)
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
# Sender address for review emails; set it to an address on a domain you own.
HITL_EMAIL_FROM = os.getenv("HITL_EMAIL_FROM", "noreply@example.com")
HITL_EMAIL_TO = os.getenv("HITL_EMAIL_TO", "")
# Base URL of the dashboard, used to build the review link in notifications.
DOMAIN = os.getenv("DOMAIN", "http://localhost:3000")

# Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "agentapprovals")


async def notify_review_requested(investigation_id: str, risk_score: float, workflow_id: str) -> None:
    """Send HITL notification via configured channel."""
    if HITL_NOTIFY_CHANNEL == "none":
        return

    url = f"{DOMAIN}/investigations/{investigation_id}"
    subject = f"Chronicle — Manual Review Required ({risk_score:.0%} risk)"
    body = (
        f"An investigation requires your review.\n\n"
        f"Investigation ID: {investigation_id}\n"
        f"Risk Score: {risk_score:.2f}\n"
        f"Workflow: {workflow_id}\n\n"
        f"Review and approve/deny here:\n{url}\n"
    )

    if HITL_NOTIFY_CHANNEL == "email":
        await _send_email(subject, body, url, investigation_id, risk_score)
    elif HITL_NOTIFY_CHANNEL == "slack":
        await _send_slack(investigation_id, risk_score, url)


async def _send_email(subject: str, body: str, url: str, investigation_id: str, risk_score: float) -> None:
    if not RESEND_API_KEY or not HITL_EMAIL_TO:
        logger.warning("Email notification skipped — RESEND_API_KEY or HITL_EMAIL_TO not set")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = HITL_EMAIL_FROM
        msg["To"] = HITL_EMAIL_TO

        text_part = MIMEText(body, "plain")
        html_part = MIMEText(f"""
<html><body style="font-family: sans-serif; color: #1e293b; padding: 24px;">
  <div style="max-width: 520px;">
    <div style="background: #fef3c7; border: 1px solid #fbbf24; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
      <strong style="color: #92400e;">⏸ Manual Review Required</strong>
    </div>
    <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
      <tr><td style="padding: 6px 0; color: #64748b; font-size: 13px;">Investigation</td>
          <td style="padding: 6px 0; font-family: monospace; font-size: 13px;">{investigation_id[:8]}…</td></tr>
      <tr><td style="padding: 6px 0; color: #64748b; font-size: 13px;">Risk Score</td>
          <td style="padding: 6px 0; font-size: 13px; font-weight: 600; color: {'#dc2626' if risk_score >= 0.6 else '#d97706'};">{risk_score:.2f}</td></tr>
    </table>
    <a href="{url}" style="display: inline-block; background: #2563eb; color: white; padding: 10px 20px;
       border-radius: 6px; text-decoration: none; font-size: 14px; font-weight: 500;">
      Review Investigation →
    </a>
    <p style="margin-top: 20px; font-size: 12px; color: #94a3b8;">
      Chronicle · {url}
    </p>
  </div>
</body></html>""", "html")

        msg.attach(text_part)
        msg.attach(html_part)

        with smtplib.SMTP("smtp.resend.com", 587) as server:
            server.starttls()
            server.login("resend", RESEND_API_KEY)
            server.send_message(msg)

        logger.info("HITL email sent to %s for investigation %s", HITL_EMAIL_TO, investigation_id)
    except Exception as e:
        logger.error("Failed to send HITL email: %s", e)


async def _send_slack(investigation_id: str, risk_score: float, url: str) -> None:
    if not SLACK_BOT_TOKEN:
        logger.warning("Slack notification skipped — SLACK_BOT_TOKEN not set")
        return
    try:
        import httpx
        risk_emoji = "🔴" if risk_score >= 0.6 else "🟡"
        payload = {
            "channel": SLACK_CHANNEL,
            "text": f"{risk_emoji} *Manual Review Required* — Investigation `{investigation_id[:8]}` (risk: {risk_score:.2f})\n<{url}|Review in Chronicle →>",
            "unfurl_links": False,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json=payload,
            )
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack API error: %s", data.get("error"))
            else:
                logger.info("HITL Slack message sent for investigation %s", investigation_id)
    except Exception as e:
        logger.error("Failed to send HITL Slack message: %s", e)
