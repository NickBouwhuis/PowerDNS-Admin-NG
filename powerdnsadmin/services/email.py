"""
Email sending service.

Framework-agnostic: uses smtplib + email.mime instead of Flask-Mail,
and Jinja2 directly for template rendering.
"""
import logging
import os
import smtplib
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, FileSystemLoader

from powerdnsadmin.core.config import get_config
from .token import generate_confirmation_token
from ..models.setting import Setting

logger = logging.getLogger(__name__)

# Template directory for email templates
_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "templates"
)

_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=True,
)


def _send_email(subject, recipients, body_text, body_html=None):
    """Send an email using smtplib.

    Args:
        subject: Email subject line.
        recipients: List of recipient email addresses.
        body_text: Plain text body.
        body_html: Optional HTML body.
    """
    config = get_config()

    mail_server = config.get('MAIL_SERVER', 'localhost')
    mail_port = config.get('MAIL_PORT', 25)
    mail_use_tls = config.get('MAIL_USE_TLS', False)
    mail_use_ssl = config.get('MAIL_USE_SSL', False)
    mail_username = config.get('MAIL_USERNAME')
    mail_password = config.get('MAIL_PASSWORD')
    mail_default_sender = config.get('MAIL_DEFAULT_SENDER', 'noreply@localhost')

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = mail_default_sender
    msg['To'] = ', '.join(recipients)

    msg.attach(MIMEText(body_text, 'plain'))
    if body_html:
        msg.attach(MIMEText(body_html, 'html'))

    if mail_use_ssl:
        smtp = smtplib.SMTP_SSL(mail_server, mail_port)
    else:
        smtp = smtplib.SMTP(mail_server, mail_port)

    try:
        if mail_use_tls:
            smtp.starttls()
        if mail_username and mail_password:
            smtp.login(mail_username, mail_password)
        smtp.sendmail(mail_default_sender, recipients, msg.as_string())
    finally:
        smtp.quit()


def send_account_verification(user_email):
    """Send welcome message for the new registration."""
    try:
        token = generate_confirmation_token(user_email)
        verification_link = '/confirm/{}'.format(token)

        setting = Setting()
        site_name = setting.get('site_name')
        subject = "Welcome to {}".format(site_name)

        body_text = (
            "Please access the following link to verify your email address. {}"
            .format(verification_link)
        )

        template = _jinja_env.get_template('emails/account_verification.html')
        body_html = template.render(
            verification_link=verification_link,
            SITE_NAME=site_name,
            SETTING=setting,
        )

        _send_email(subject, [user_email], body_text, body_html)
    except Exception as e:
        logger.error("Cannot send account verification email. Error: %s", e)
        logger.debug(traceback.format_exc())
