from .base import authlib_oauth_client
from ..models.setting import Setting


def google_oauth():
    if not Setting().get('google_oauth_enabled'):
        return None

    authlib_params = {
        'client_id': Setting().get('google_oauth_client_id'),
        'client_secret': Setting().get('google_oauth_client_secret'),
        'api_base_url': Setting().get('google_base_url'),
        'request_token_url': None,
        'client_kwargs': {'scope': Setting().get('google_oauth_scope')},
    }

    auto_configure = Setting().get('google_oauth_auto_configure')
    server_metadata_url = Setting().get('google_oauth_metadata_url')

    if auto_configure and isinstance(server_metadata_url, str) and len(server_metadata_url.strip()) > 0:
        authlib_params['server_metadata_url'] = server_metadata_url
    else:
        authlib_params['access_token_url'] = Setting().get('google_token_url')
        authlib_params['authorize_url'] = Setting().get('google_authorize_url')

    google = authlib_oauth_client.register(
        'google',
        **authlib_params
    )

    return google
