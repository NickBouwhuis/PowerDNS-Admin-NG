from .base import authlib_oauth_client


def init_app(app):
    """No-op: Starlette OAuth client does not require Flask init_app."""
    pass
