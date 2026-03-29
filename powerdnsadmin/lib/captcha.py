"""Standalone CAPTCHA support for FastAPI/Starlette sessions.

Replaces ``flask_session_captcha.FlaskSessionCaptcha`` with a
framework-agnostic implementation backed by the ``captcha`` package
(Pillow-based image generation).

Usage in routes::

    from powerdnsadmin.lib.captcha import generate_captcha_html, validate_captcha

    # In GET handler — add to template context:
    captcha_html = generate_captcha_html(session)

    # In POST handler — validate user input:
    if not validate_captcha(session, form_data.get("captcha")):
        ...  # invalid

Templates call ``{{ captcha_html | safe }}`` to render the image.
"""
import base64
import logging
import secrets
import string
from io import BytesIO
from markupsafe import Markup

from captcha.image import ImageCaptcha

logger = logging.getLogger(__name__)

_IMAGE_GEN = ImageCaptcha(width=200, height=60)
_SESSION_KEY = "_captcha_answer"
_CAPTCHA_LENGTH = 5
_CHARSET = string.ascii_uppercase + string.digits


def _generate_answer(length: int = _CAPTCHA_LENGTH) -> str:
    """Generate a random CAPTCHA answer string."""
    return "".join(secrets.choice(_CHARSET) for _ in range(length))


def generate_captcha_html(session: dict) -> Markup:
    """Generate a CAPTCHA image and store the answer in *session*.

    Returns an HTML ``<img>`` tag with a base64-encoded PNG suitable for
    embedding directly in a template.
    """
    answer = _generate_answer()
    session[_SESSION_KEY] = answer.upper()

    buf = BytesIO()
    image = _IMAGE_GEN.generate_image(answer)
    image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return Markup(
        f'<img src="data:image/png;base64,{b64}" alt="CAPTCHA" '
        f'class="img-fluid mb-2" style="max-width:200px">'
    )


def validate_captcha(session: dict, user_input: str | None) -> bool:
    """Validate the user's CAPTCHA input against the session answer.

    The stored answer is consumed (removed from session) regardless of
    whether validation succeeds, preventing replay.
    """
    expected = session.pop(_SESSION_KEY, None)
    if not expected or not user_input:
        return False
    return user_input.strip().upper() == expected.upper()
