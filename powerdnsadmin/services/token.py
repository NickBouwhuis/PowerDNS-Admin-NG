import logging

from itsdangerous import URLSafeTimedSerializer

from powerdnsadmin.core.config import get_config

logger = logging.getLogger(__name__)


def generate_confirmation_token(email):
    config = get_config()
    serializer = URLSafeTimedSerializer(config['SECRET_KEY'])
    return serializer.dumps(email, salt=config['SALT'])


def confirm_token(token, expiration=86400):
    config = get_config()
    serializer = URLSafeTimedSerializer(config['SECRET_KEY'])
    try:
        email = serializer.loads(token,
                                 salt=config['SALT'],
                                 max_age=expiration)
    except Exception as e:
        logger.debug(e)
        return False
    return email
