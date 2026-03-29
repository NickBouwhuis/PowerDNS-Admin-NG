"""
Server-side session middleware for FastAPI.

Uses the existing SQLAlchemy `sessions` table (same schema as Flask-Session)
with signed cookie IDs via itsdangerous.URLSafeTimedSerializer.

Sessions are stored as JSON BLOBs in the database keyed by a random session ID.
The session ID is stored in a signed cookie. OAuth tokens and SAML data can
exceed 4KB cookie limits, so server-side storage is required.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "session"
# Default session timeout in minutes (overridden by session_timeout setting)
DEFAULT_SESSION_TIMEOUT = 10


class SessionData(dict):
    """Dict subclass that tracks modification."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False

    def __setitem__(self, key, value):
        self.modified = True
        super().__setitem__(key, value)

    def __delitem__(self, key):
        self.modified = True
        super().__delitem__(key)

    def pop(self, *args):
        self.modified = True
        return super().pop(*args)

    def update(self, *args, **kwargs):
        self.modified = True
        super().update(*args, **kwargs)

    def clear(self):
        self.modified = True
        super().clear()


class ServerSideSessionMiddleware(BaseHTTPMiddleware):
    """Starlette middleware providing server-side sessions.

    Session data is stored in the `sessions` table using the existing
    Flask-Session schema (session_id, data as JSON blob, expiry datetime).

    The session ID is signed using itsdangerous and stored in a cookie.
    """

    def __init__(
        self,
        app,
        secret_key: str,
        session_timeout_minutes: int = DEFAULT_SESSION_TIMEOUT,
        cookie_name: str = SESSION_COOKIE_NAME,
        cookie_httponly: bool = True,
        cookie_samesite: str = "lax",
        cookie_secure: bool = False,
    ):
        super().__init__(app)
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.session_timeout = session_timeout_minutes
        self.cookie_name = cookie_name
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite
        self.cookie_secure = cookie_secure

    def _get_session_id(self, request: Request) -> str | None:
        """Extract and verify the session ID from the cookie."""
        cookie = request.cookies.get(self.cookie_name)
        if not cookie:
            return None
        try:
            # Max age in seconds = timeout in minutes * 60
            max_age = self.session_timeout * 60
            session_id = self.serializer.loads(cookie, max_age=max_age)
            return session_id
        except (BadSignature, SignatureExpired):
            return None

    def _sign_session_id(self, session_id: str) -> str:
        """Sign a session ID for cookie storage."""
        return self.serializer.dumps(session_id)

    def _load_session(self, session_id: str) -> SessionData:
        """Load session data from the database."""
        from powerdnsadmin.models.base import db
        from powerdnsadmin.models.sessions import Sessions

        record = db.session.query(Sessions).filter_by(
            session_id=session_id
        ).first()

        if record is None:
            return SessionData()

        # Check expiry
        if record.expiry and record.expiry < datetime.utcnow():
            db.session.delete(record)
            db.session.commit()
            return SessionData()

        try:
            data = json.loads(record.data) if record.data else {}
        except (json.JSONDecodeError, TypeError):
            data = {}

        return SessionData(data)

    def _save_session(self, session_id: str, session: SessionData) -> None:
        """Save session data to the database."""
        from powerdnsadmin.models.base import db
        from powerdnsadmin.models.sessions import Sessions

        expiry = datetime.utcnow() + timedelta(minutes=self.session_timeout)
        data_blob = json.dumps(dict(session)).encode('utf-8')

        record = db.session.query(Sessions).filter_by(
            session_id=session_id
        ).first()

        if record:
            record.data = data_blob
            record.expiry = expiry
        else:
            record = Sessions(
                session_id=session_id,
                data=data_blob,
                expiry=expiry,
            )
            db.session.add(record)

        db.session.commit()

    def _delete_session(self, session_id: str) -> None:
        """Delete a session from the database."""
        from powerdnsadmin.models.base import db
        from powerdnsadmin.models.sessions import Sessions

        db.session.query(Sessions).filter_by(session_id=session_id).delete()
        db.session.commit()

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Load or create session
        session_id = self._get_session_id(request)
        is_new = session_id is None

        if is_new:
            session_id = str(uuid.uuid4())
            session = SessionData()
        else:
            session = self._load_session(session_id)

        # Attach session to request state
        request.state.session = session

        response = await call_next(request)

        # Save session if modified or new
        if session.modified or is_new:
            if session:
                self._save_session(session_id, session)
            elif not is_new:
                self._delete_session(session_id)

            # Set cookie
            if session:
                signed_id = self._sign_session_id(session_id)
                response.set_cookie(
                    self.cookie_name,
                    signed_id,
                    httponly=self.cookie_httponly,
                    samesite=self.cookie_samesite,
                    secure=self.cookie_secure,
                    max_age=self.session_timeout * 60,
                )
            else:
                response.delete_cookie(self.cookie_name)

        return response
