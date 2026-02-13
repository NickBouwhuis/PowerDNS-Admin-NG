"""
Local password authentication service.

Handles bcrypt password hashing and local user credential validation.
"""
import bcrypt
from flask import current_app
from sqlalchemy import select

from ...models.base import db


def hash_password(plain_text_password):
    """Hash a password using bcrypt.

    Args:
        plain_text_password: The password to hash.

    Returns:
        bytes: The bcrypt-hashed password, or None if input is None.
    """
    if plain_text_password is None:
        return None
    return bcrypt.hashpw(plain_text_password.encode('utf-8'), bcrypt.gensalt())


def check_password(plain_text_password, hashed_password):
    """Check a plain text password against a bcrypt hash.

    Args:
        plain_text_password: The password to verify.
        hashed_password: The bcrypt hash to check against.

    Returns:
        bool: True if the password matches.
    """
    if plain_text_password is None or hashed_password is None:
        return False
    return bcrypt.checkpw(
        plain_text_password.encode('utf-8'),
        hashed_password.encode('utf-8'),
    )


class LocalAuthService:
    """Service for local (database-backed) authentication."""

    def validate(self, username, plain_text_password, src_ip='',
                 trust_user=False):
        """Validate local user credentials.

        Args:
            username: The username to validate.
            plain_text_password: The password to check.
            src_ip: Source IP for logging.
            trust_user: If True, skip password check (for trusted SSO flows).

        Returns:
            bool: True if credentials are valid.
        """
        from ...models.user import User

        user_info = db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if user_info:
            if trust_user or (
                user_info.password
                and check_password(plain_text_password, user_info.password)
            ):
                current_app.logger.info(
                    'User "{0}" logged in successfully. '
                    'Authentication request from {1}'.format(username, src_ip))
                return True
            current_app.logger.error(
                'User "{0}" inputted a wrong password. '
                'Authentication request from {1}'.format(username, src_ip))
            return False

        current_app.logger.warning(
            'User "{0}" does not exist. '
            'Authentication request from {1}'.format(username, src_ip))
        return False
