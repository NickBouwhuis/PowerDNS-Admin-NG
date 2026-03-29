from .base import authlib_oauth_client
from ..models.setting import Setting


def azure_oauth():
    if not Setting().get('azure_oauth_enabled'):
        return None

    authlib_params = {
        'client_id': Setting().get('azure_oauth_key'),
        'client_secret': Setting().get('azure_oauth_secret'),
        'api_base_url': Setting().get('azure_oauth_api_url'),
        'request_token_url': None,
        'client_kwargs': {'scope': Setting().get('azure_oauth_scope')},
    }

    auto_configure = Setting().get('azure_oauth_auto_configure')
    server_metadata_url = Setting().get('azure_oauth_metadata_url')

    if auto_configure and isinstance(server_metadata_url, str) and len(server_metadata_url.strip()) > 0:
        authlib_params['server_metadata_url'] = server_metadata_url
    else:
        authlib_params['access_token_url'] = Setting().get('azure_oauth_token_url')
        authlib_params['authorize_url'] = Setting().get('azure_oauth_authorize_url')

    azure = authlib_oauth_client.register(
        'azure',
        **authlib_params
    )

    return azure
