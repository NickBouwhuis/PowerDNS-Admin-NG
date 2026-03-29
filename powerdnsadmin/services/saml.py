"""
SAML authentication service.

Framework-agnostic: uses get_config() instead of Flask's current_app.config.
"""
import json
import logging
import os
from datetime import datetime, timedelta
from threading import Thread

from ..lib.certutil import KEY_FILE, CERT_FILE, create_self_signed_cert
from ..lib.utils import urlparse
from powerdnsadmin.core.config import get_config

logger = logging.getLogger(__name__)


class SAML(object):
    def __init__(self):
        config = get_config()
        if config.get('SAML_ENABLED'):
            from onelogin.saml2.auth import OneLogin_Saml2_Auth
            from onelogin.saml2.idp_metadata_parser import OneLogin_Saml2_IdPMetadataParser

            self.idp_timestamp = datetime.now()
            self.OneLogin_Saml2_Auth = OneLogin_Saml2_Auth
            self.OneLogin_Saml2_IdPMetadataParser = OneLogin_Saml2_IdPMetadataParser
            self.idp_data = None

            if 'SAML_IDP_ENTITY_ID' in config:
                self.idp_data = OneLogin_Saml2_IdPMetadataParser.parse_remote(
                    config['SAML_METADATA_URL'],
                    entity_id=config.get('SAML_IDP_ENTITY_ID', None),
                    required_sso_binding=config['SAML_IDP_SSO_BINDING'])
            else:
                self.idp_data = OneLogin_Saml2_IdPMetadataParser.parse_remote(
                    config['SAML_METADATA_URL'],
                    entity_id=config.get('SAML_IDP_ENTITY_ID', None))
            if self.idp_data is None:
                logger.error('SAML: IDP Metadata initial load failed')
                exit(-1)

    def get_idp_data(self):
        config = get_config()
        lifetime = timedelta(
            minutes=config['SAML_METADATA_CACHE_LIFETIME'])

        if self.idp_timestamp + lifetime < datetime.now():
            background_thread = Thread(target=self.retrieve_idp_data())
            background_thread.start()

        return self.idp_data

    def retrieve_idp_data(self):
        config = get_config()

        if 'SAML_IDP_SSO_BINDING' in config:
            new_idp_data = self.OneLogin_Saml2_IdPMetadataParser.parse_remote(
                config['SAML_METADATA_URL'],
                entity_id=config.get('SAML_IDP_ENTITY_ID', None),
                required_sso_binding=config['SAML_IDP_SSO_BINDING']
            )
        else:
            new_idp_data = self.OneLogin_Saml2_IdPMetadataParser.parse_remote(
                config['SAML_METADATA_URL'],
                entity_id=config.get('SAML_IDP_ENTITY_ID', None))
        if new_idp_data is not None:
            self.idp_data = new_idp_data
            self.idp_timestamp = datetime.now()
            logger.info(
                "SAML: IDP Metadata successfully retrieved from: %s",
                config['SAML_METADATA_URL'])
        else:
            logger.info("SAML: IDP Metadata could not be retrieved")

    def prepare_flask_request(self, request):
        """Prepare a request dict for python3-saml from a Flask request.

        .. deprecated::
            This method is kept for backward compatibility with Flask routes.
            New code should use ``prepare_starlette_request`` instead.
        """
        # If server is behind proxys or balancers use the HTTP_X_FORWARDED fields
        url_data = urlparse(request.url)
        proto = request.headers.get('HTTP_X_FORWARDED_PROTO', request.scheme)
        return {
            'https': 'on' if proto == 'https' else 'off',
            'http_host': request.host,
            'server_port': url_data.port,
            'script_name': request.path,
            'get_data': request.args.copy(),
            'post_data': request.form.copy(),
            # Uncomment if using ADFS as IdP, https://github.com/onelogin/python-saml/pull/144
            'lowercase_urlencoding': True,
            'query_string': request.query_string
        }

    async def prepare_starlette_request(self, request):
        """Prepare a request dict for python3-saml from a Starlette/FastAPI request.

        python3-saml just needs a plain dict -- framework-agnostic.
        """
        url_data = urlparse(str(request.url))
        proto = request.headers.get('x-forwarded-proto', request.url.scheme)
        # Get form data for POST requests
        form_data = {}
        if request.method == 'POST':
            form_data = dict(await request.form())
        return {
            'https': 'on' if proto == 'https' else 'off',
            'http_host': request.headers.get('host', request.url.hostname),
            'server_port': url_data.port,
            'script_name': request.url.path,
            'get_data': dict(request.query_params),
            'post_data': form_data,
            'lowercase_urlencoding': True,
            'query_string': str(request.url.query) if request.url.query else '',
        }

    def init_saml_auth(self, req):
        config = get_config()

        own_url = ''
        if req['https'] == 'on':
            own_url = 'https://'
        else:
            own_url = 'http://'
        own_url += req['http_host']
        metadata = self.get_idp_data()
        settings = {}
        settings['sp'] = {}
        if 'SAML_NAMEID_FORMAT' in config:
            settings['sp']['NameIDFormat'] = config['SAML_NAMEID_FORMAT']
        else:
            settings['sp']['NameIDFormat'] = self.idp_data.get('sp', {}).get(
                'NameIDFormat',
                'urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified')
        settings['sp']['entityId'] = config['SAML_SP_ENTITY_ID']


        if ('SAML_CERT' in config) and ('SAML_KEY' in config):

             saml_cert_file = config['SAML_CERT']
             saml_key_file = config['SAML_KEY']

             if os.path.isfile(saml_cert_file):
                 cert = open(saml_cert_file, "r").readlines()
                 settings['sp']['x509cert'] = "".join(cert)
             if os.path.isfile(saml_key_file):
                 key = open(saml_key_file, "r").readlines()
                 settings['sp']['privateKey'] = "".join(key)

        else:

            if (os.path.isfile(CERT_FILE)) and (os.path.isfile(KEY_FILE)):
                 cert = open(CERT_FILE, "r").readlines()
                 key = open(KEY_FILE, "r").readlines()
            else:
                 create_self_signed_cert()
                 cert = open(CERT_FILE, "r").readlines()
                 key = open(KEY_FILE, "r").readlines()

            settings['sp']['x509cert'] = "".join(cert)
            settings['sp']['privateKey'] = "".join(key)


        if 'SAML_SP_REQUESTED_ATTRIBUTES' in config:
             saml_req_attr = json.loads(config['SAML_SP_REQUESTED_ATTRIBUTES'])
             settings['sp']['attributeConsumingService'] = {
                "serviceName": "PowerDNSAdmin",
                "serviceDescription": "PowerDNS-AdminNG - PowerDNS administration utility",
                "requestedAttributes": saml_req_attr
             }
        else:
             settings['sp']['attributeConsumingService'] = {}


        settings['sp']['assertionConsumerService'] = {}
        settings['sp']['assertionConsumerService'][
            'binding'] = 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
        settings['sp']['assertionConsumerService'][
            'url'] = own_url + '/saml/authorized'
        settings['sp']['singleLogoutService'] = {}
        settings['sp']['singleLogoutService'][
            'binding'] = 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
        settings['sp']['singleLogoutService']['url'] = own_url + '/saml/sls'
        settings['idp'] = metadata['idp']
        settings['strict'] = True
        settings['debug'] = config['SAML_DEBUG']
        settings['security'] = {}
        settings['security'][
            'digestAlgorithm'] = 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
        settings['security']['metadataCacheDuration'] = None
        settings['security']['metadataValidUntil'] = None
        settings['security']['requestedAuthnContext'] = True
        settings['security'][
            'signatureAlgorithm'] = 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
        settings['security']['wantAssertionsEncrypted'] = config.get(
            'SAML_ASSERTION_ENCRYPTED', True)
        settings['security']['wantAttributeStatement'] = config.get(
            'SAML_WANT_ATTRIBUTE_STATEMENT', True)
        settings['security']['wantNameId'] = True
        settings['security']['authnRequestsSigned'] = config[
            'SAML_SIGN_REQUEST']
        settings['security']['logoutRequestSigned'] = config[
            'SAML_SIGN_REQUEST']
        settings['security']['logoutResponseSigned'] = config[
            'SAML_SIGN_REQUEST']
        settings['security']['nameIdEncrypted'] = False
        settings['security']['signMetadata'] = True
        settings['security']['wantAssertionsSigned'] = True
        settings['security']['wantMessagesSigned'] = config.get(
            'SAML_WANT_MESSAGE_SIGNED', True)
        settings['security']['wantNameIdEncrypted'] = False
        settings['contactPerson'] = {}
        settings['contactPerson']['support'] = {}
        settings['contactPerson']['support'][
            'emailAddress'] = config['SAML_SP_CONTACT_NAME']
        settings['contactPerson']['support']['givenName'] = config[
            'SAML_SP_CONTACT_MAIL']
        settings['contactPerson']['technical'] = {}
        settings['contactPerson']['technical'][
            'emailAddress'] = config['SAML_SP_CONTACT_MAIL']
        settings['contactPerson']['technical'][
            'givenName'] = config['SAML_SP_CONTACT_NAME']
        settings['organization'] = {}
        settings['organization']['en-US'] = {}
        settings['organization']['en-US']['displayname'] = 'PowerDNS-AdminNG'
        settings['organization']['en-US']['name'] = 'PowerDNS-AdminNG'
        settings['organization']['en-US']['url'] = own_url
        auth = self.OneLogin_Saml2_Auth(req, settings)
        return auth
