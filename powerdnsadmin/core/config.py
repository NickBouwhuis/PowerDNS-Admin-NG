"""
Framework-agnostic configuration loading.

Reads config from default_config.py, docker_config.py, PDA_CONF env var
(or legacy FLASK_CONF), and environment variable overrides.
Returns a plain dict.
"""
import logging
import os
import secrets

import bcrypt

logger = logging.getLogger(__name__)

# Known insecure defaults that must never be used in production
_INSECURE_SECRETS = {
    'e951e5a1f4b94151b360f47edf596dd2',
}
_INSECURE_SALTS: set[str] = set()


def _load_module_config(module_path: str) -> dict:
    """Load config values from a Python module by dotted path."""
    import importlib
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        return {}
    return {
        k: getattr(mod, k)
        for k in dir(mod)
        if k.isupper()
    }


def _load_pyfile_config(filepath: str) -> dict:
    """Load config from a .py file path (like Flask's from_pyfile)."""
    d = {}
    with open(filepath, mode='rb') as f:
        code = compile(f.read(), filepath, 'exec')
    exec(code, d)
    return {k: v for k, v in d.items() if k.isupper()}


def _ensure_secret_key(config: dict) -> None:
    """Ensure SECRET_KEY is set and not an insecure default."""
    key = config.get('SECRET_KEY')
    if not key:
        config['SECRET_KEY'] = secrets.token_hex(32)
        logger.warning(
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


def _ensure_salt(config: dict) -> None:
    """Ensure SALT is set and not an insecure default."""
    salt = config.get('SALT')
    if not salt:
        salt = bcrypt.gensalt().decode('utf-8')
        config['SALT'] = salt
        logger.warning(
            'SALT not configured -- generated a random salt. '
            'Set SALT in your configuration file for consistent password hashing.'
        )
    elif salt in _INSECURE_SALTS:
        raise RuntimeError(
            'SALT is set to a known insecure default. '
            'Please set a unique SALT in your configuration file or '
            'via the SALT environment variable.'
        )


def load_config(config_override=None) -> dict:
    """Load configuration from all sources.

    Priority (last wins):
      1. default_config.py
      2. docker_config.py (if exists)
      3. PDA_CONF / FLASK_CONF env var (file path)
      4. config_override (dict or .py file path)
      5. Environment variable overrides (via AppSettings)

    Returns a plain dict of uppercase config keys.
    """
    from powerdnsadmin.lib.settings import AppSettings

    # Determine the package root directory
    pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    # 1. Load default config
    config = _load_module_config('powerdnsadmin.default_config')

    # 2. Docker config if present
    docker_config_path = os.path.join(pkg_root, 'docker_config.py')
    if os.path.exists(docker_config_path):
        config.update(_load_module_config('powerdnsadmin.docker_config'))

    # 3. PDA_CONF env var (or legacy FLASK_CONF for backwards compat)
    pda_conf = os.environ.get('PDA_CONF') or os.environ.get('FLASK_CONF')
    if pda_conf:
        config.update(_load_pyfile_config(pda_conf))

    # 4. Explicit override
    if config_override is not None:
        if isinstance(config_override, dict):
            config.update(config_override)
        elif isinstance(config_override, str) and config_override.endswith('.py'):
            config.update(_load_pyfile_config(config_override))

    # 5. Environment variable overrides
    for var_name in AppSettings.defaults:
        env_name = var_name.upper()
        current_value = None

        if env_name + '_FILE' in os.environ:
            if env_name in os.environ:
                raise AttributeError(
                    "Both {} and {} are set but are exclusive.".format(
                        env_name, env_name + '_FILE'))
            with open(os.environ[env_name + '_FILE']) as f:
                current_value = f.read()

        elif env_name in os.environ:
            current_value = os.environ[env_name]

        if current_value is not None:
            config[env_name] = AppSettings.convert_type(var_name, current_value)

    # Security checks
    _ensure_secret_key(config)
    _ensure_salt(config)

    return config


# Singleton config dict, populated on first call to get_config()
_app_config: dict | None = None


def get_config(config_override=None) -> dict:
    """Return the application config singleton.

    First call loads and caches; subsequent calls return cached config.
    Pass config_override only on first call (app startup).
    """
    global _app_config
    if _app_config is None:
        _app_config = load_config(config_override)
    return _app_config


def reset_config() -> None:
    """Reset config singleton (for testing)."""
    global _app_config
    _app_config = None
