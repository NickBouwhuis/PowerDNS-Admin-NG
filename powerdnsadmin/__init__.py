import os
import logging
import secrets
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_session import Session
from .lib import utils

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)

# Known insecure defaults that must never be used in production
_INSECURE_SECRETS = {
    'e951e5a1f4b94151b360f47edf596dd2',
}
_INSECURE_SALTS = {
    '$2b$12$yLUMTIfl21FKJQpTkRQXCu',
}


def _ensure_secret_key(app):
    """Ensure SECRET_KEY is set and not an insecure default."""
    key = app.config.get('SECRET_KEY')
    if not key:
        app.config['SECRET_KEY'] = secrets.token_hex(32)
        app.logger.warning(
            'SECRET_KEY not configured -- generated a random key. '
            'Sessions will not persist across restarts. '
            'Set SECRET_KEY in your configuration file.'
        )
    elif key in _INSECURE_SECRETS:
        raise RuntimeError(
            'SECRET_KEY is set to a known insecure default. '
            'Please set a unique SECRET_KEY in your configuration file or '
            'via the SECRET_KEY environment variable.'
        )


def _ensure_salt(app):
    """Ensure SALT is set and not an insecure default."""
    import bcrypt
    salt = app.config.get('SALT')
    if not salt:
        salt = bcrypt.gensalt().decode('utf-8')
        app.config['SALT'] = salt
        app.logger.warning(
            'SALT not configured -- generated a random salt. '
            'Set SALT in your configuration file for consistent password hashing.'
        )
    elif salt in _INSECURE_SALTS:
        raise RuntimeError(
            'SALT is set to a known insecure default. '
            'Please set a unique SALT in your configuration file or '
            'via the SALT environment variable.'
        )


def create_app(config=None):
    from powerdnsadmin.lib.settings import AppSettings
    from . import models, routes, services
    from .assets import assets
    app = Flask(__name__)

    # Read log level from environment variable
    log_level_name = os.environ.get('PDNS_ADMIN_LOG_LEVEL', 'WARNING')
    log_level = logging.getLevelName(log_level_name.upper())
    # Setting logger
    logging.basicConfig(
       level=log_level,
        format=
        "[%(asctime)s] [%(filename)s:%(lineno)d] %(levelname)s - %(message)s")

    # If we use Docker + Gunicorn, adjust the
    # log handler
    if "GUNICORN_LOGLEVEL" in os.environ:
        gunicorn_logger = logging.getLogger("gunicorn.error")
        app.logger.handlers = gunicorn_logger.handlers
        app.logger.setLevel(gunicorn_logger.level)

    # Proxy
    app.wsgi_app = ProxyFix(app.wsgi_app)

    # Load config from env variables if using docker
    if os.path.exists(os.path.join(app.root_path, 'docker_config.py')):
        app.config.from_object('powerdnsadmin.docker_config')
    else:
        # Load default configuration
        app.config.from_object('powerdnsadmin.default_config')

    # Load config file from FLASK_CONF env variable
    if 'FLASK_CONF' in os.environ:
        app.config.from_envvar('FLASK_CONF')

    # Load app specified configuration
    if config is not None:
        if isinstance(config, dict):
            app.config.update(config)
        elif config.endswith('.py'):
            app.config.from_pyfile(config)

    # Load any settings defined with environment variables
    AppSettings.load_environment(app)

    # Ensure SECRET_KEY and SALT are set and secure
    _ensure_secret_key(app)
    _ensure_salt(app)

    # HSTS
    if app.config.get('HSTS_ENABLED'):
        from flask_sslify import SSLify
        _sslify = SSLify(app)  # lgtm [py/unused-local-variable]

    # Load Flask-Session
    app.config['SESSION_TYPE'] = app.config.get('SESSION_TYPE')
    if 'SESSION_TYPE' in os.environ:
        app.config['SESSION_TYPE'] = os.environ.get('SESSION_TYPE')

    sess = Session(app)

    # create sessions table if using sqlalchemy backend
    if os.environ.get('SESSION_TYPE') == 'sqlalchemy':
        sess.app.session_interface.db.create_all()

    # SMTP
    app.mail = Mail(app)

    # Rate limiting
    limiter.init_app(app)

    # Load app's components
    assets.init_app(app)
    models.init_app(app)
    routes.init_app(app)
    services.init_app(app)

    # Register filters
    app.jinja_env.filters['display_record_name'] = utils.display_record_name
    app.jinja_env.filters['display_master_name'] = utils.display_master_name
    app.jinja_env.filters['display_second_to_time'] = utils.display_time
    app.jinja_env.filters['display_setting_state'] = utils.display_setting_state
    app.jinja_env.filters['pretty_domain_name'] = utils.pretty_domain_name
    app.jinja_env.filters['format_datetime_local'] = utils.format_datetime
    app.jinja_env.filters['format_zone_type'] = utils.format_zone_type

    # Register context processors
    from .models.setting import Setting

    @app.context_processor
    def inject_sitename():
        setting = Setting().get('site_name')
        return dict(SITE_NAME=setting)

    @app.context_processor
    def inject_setting():
        setting = Setting()
        return dict(SETTING=setting)

    return app
