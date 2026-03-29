"""
Server-side callback routes that cannot be handled by the SPA.

These routes handle OAuth/SAML redirects, DynDNS updates, email confirmation,
and health checks. They return JSON, plain text, or HTTP redirects — no HTML
templates.

Migrated from web/routes/auth.py during Phase 6g (SPA conversion).
"""
import base64
import ipaddress
import json
import logging
import os
import re
import traceback

from distutils.util import strtobool

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response
from yaml import Loader, load

from powerdnsadmin.core.config import get_config
from powerdnsadmin.web.deps import get_session, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["callbacks"])

# ---------------------------------------------------------------------------
# OAuth / SAML module singletons — initialised lazily on first use
# ---------------------------------------------------------------------------
_google = None
_github = None
_azure = None
_oidc = None
_saml = None
_oauth_initialised = False


def _ensure_oauth():
    """Lazily initialise OAuth / SAML singletons (once per process)."""
    global _google, _github, _azure, _oidc, _saml, _oauth_initialised
    if _oauth_initialised:
        return
    from powerdnsadmin.services.google import google_oauth
    from powerdnsadmin.services.github import github_oauth
    from powerdnsadmin.services.azure import azure_oauth
    from powerdnsadmin.services.oidc import oidc_oauth
    from powerdnsadmin.services.saml import SAML

    _google = google_oauth()
    _github = github_oauth()
    _azure = azure_oauth()
    _oidc = oidc_oauth()
    try:
        _saml = SAML()
    except Exception:
        _saml = None
    _oauth_initialised = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def signin_history(request: Request, session: dict, username: str,
                   authenticator: str, success: bool):
    """Record a sign-in attempt in the history table."""
    from powerdnsadmin.models.history import History

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        request_ip = forwarded.split(',')[0].strip()
    else:
        request_ip = request.client.host if request.client else "unknown"

    if success:
        logger.info("User %s authenticated successfully via %s from %s",
                    username, authenticator, request_ip)
    else:
        logger.warning("User %s failed to authenticate via %s from %s",
                       username, authenticator, request_ip)

    History(
        msg='User {} authentication {}'.format(
            username, 'succeeded' if success else 'failed'),
        detail=json.dumps({
            'username': username,
            'authenticator': authenticator,
            'ip_address': request_ip,
            'success': 1 if success else 0
        }),
        created_by='System',
    ).add()


def authenticate_user(request: Request, session: dict, user, authenticator):
    """Log in *user* via session, record history, and redirect to SPA."""
    from powerdnsadmin.models.setting import Setting

    session['user_id'] = user.id
    signin_history(request, session, user.username, authenticator, True)

    if (Setting().get('otp_force')
            and Setting().get('otp_field_enabled')
            and not user.otp_secret
            and session.get('authentication_type') not in ['OAuth']):
        user.update_profile(enable_otp=True)
        session.clear()
        session['welcome_user_id'] = user.id
        return RedirectResponse(url="/?otp_setup=required", status_code=302)

    return RedirectResponse(url="/", status_code=302)


def checkForPDAEntries(Entitlements, urn_value):
    """Check whether any LDAP entitlements contain valid powerdns-admin records."""
    urnArguments = [x.lower() for x in urn_value.split(':')]
    for Entitlement in Entitlements:
        entArguments = Entitlement.split(':powerdns-admin')
        entArguments = [x.lower() for x in entArguments[0].split(':')]
        if entArguments == urnArguments:
            return True
    return False


async def get_azure_groups(uri, token):
    """Recursively fetch Azure AD security groups from the Graph API."""
    resp = await _azure.get(uri, token=token)
    azure_info = resp.text
    logger.info('Azure groups returned: %s', azure_info)
    grouplookup = json.loads(azure_info)
    if "value" in grouplookup:
        mygroups = grouplookup["value"]
        if "@odata.nextLink" in grouplookup:
            mygroups.extend(await get_azure_groups(
                grouplookup["@odata.nextLink"], token))
    else:
        mygroups = []
    return mygroups


def handle_account(account_name, account_description=""):
    """Find or create an Account by *account_name*."""
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.history import History

    clean_name = Account.sanitize_name(account_name)
    account = Account.query.filter_by(name=clean_name).first()
    if not account:
        account = Account(name=clean_name,
                          description=account_description,
                          contact='',
                          mail='')
        account.create_account()
        history = History(msg='Account {0} created'.format(account.name),
                          created_by='OIDC/SAML Assertion')
        history.add()
    else:
        account.description = account_description
        account.update_account()
    return account


def uplift_to_admin(user):
    """Promote *user* to Administrator if not already."""
    from powerdnsadmin.models.role import Role
    from powerdnsadmin.models.history import History

    if user.role.name != 'Administrator':
        user.role_id = Role.query.filter_by(name='Administrator').first().id
        History(
            msg='Promoting {0} to administrator'.format(user.username),
            created_by='SAML Assertion',
        ).add()


def uplift_to_operator(user):
    """Promote *user* to Operator if not already."""
    from powerdnsadmin.models.role import Role
    from powerdnsadmin.models.history import History

    if user.role.name != 'Operator':
        user.role_id = Role.query.filter_by(name='Operator').first().id
        History(
            msg='Promoting {0} to operator'.format(user.username),
            created_by='SAML Assertion',
        ).add()


def create_group_to_account_mapping():
    """Parse the SAML_GROUP_TO_ACCOUNT_MAPPING config string into a list."""
    group_to_account_mapping_string = get_config().get(
        'SAML_GROUP_TO_ACCOUNT_MAPPING', None)
    if (group_to_account_mapping_string
            and len(group_to_account_mapping_string.strip()) > 0):
        group_to_account_mapping = group_to_account_mapping_string.split(',')
    else:
        group_to_account_mapping = []
    return group_to_account_mapping


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/ping", name="index.ping")
async def ping(request: Request):
    return PlainTextResponse("ok")


# ---------------------------------------------------------------------------
# OAuth initiators
# ---------------------------------------------------------------------------

@router.get("/google/login", name="index.google_login")
async def google_login(request: Request):
    from powerdnsadmin.models.setting import Setting

    _ensure_oauth()

    if not Setting().get('google_oauth_enabled') or _google is None:
        logger.error(
            'Google OAuth is disabled or you have not yet reloaded '
            'the pda application after enabling.')
        return Response(status_code=400)

    use_ssl = get_config().get('SERVER_EXTERNAL_SSL')
    redirect_uri = str(request.url_for('google_authorized'))
    if isinstance(use_ssl, bool):
        if use_ssl:
            redirect_uri = redirect_uri.replace('http://', 'https://')
        else:
            redirect_uri = redirect_uri.replace('https://', 'http://')

    return await _google.authorize_redirect(request, redirect_uri)


@router.get("/github/login", name="index.github_login")
async def github_login(request: Request):
    from powerdnsadmin.models.setting import Setting

    _ensure_oauth()

    if not Setting().get('github_oauth_enabled') or _github is None:
        logger.error(
            'Github OAuth is disabled or you have not yet reloaded '
            'the pda application after enabling.')
        return Response(status_code=400)

    use_ssl = get_config().get('SERVER_EXTERNAL_SSL')
    redirect_uri = str(request.url_for('github_authorized'))
    if isinstance(use_ssl, bool):
        if use_ssl:
            redirect_uri = redirect_uri.replace('http://', 'https://')
        else:
            redirect_uri = redirect_uri.replace('https://', 'http://')

    return await _github.authorize_redirect(request, redirect_uri)


@router.get("/azure/login", name="index.azure_login")
async def azure_login(request: Request):
    from powerdnsadmin.models.setting import Setting

    _ensure_oauth()

    if not Setting().get('azure_oauth_enabled') or _azure is None:
        logger.error(
            'Microsoft OAuth is disabled or you have not yet reloaded '
            'the pda application after enabling.')
        return Response(status_code=400)

    use_ssl = get_config().get('SERVER_EXTERNAL_SSL')
    redirect_uri = str(request.url_for('azure_authorized'))
    if isinstance(use_ssl, bool):
        if use_ssl:
            redirect_uri = redirect_uri.replace('http://', 'https://')
        else:
            redirect_uri = redirect_uri.replace('https://', 'http://')

    return await _azure.authorize_redirect(request, redirect_uri)


@router.get("/oidc/login", name="index.oidc_login")
async def oidc_login(request: Request):
    from powerdnsadmin.models.setting import Setting

    _ensure_oauth()

    if not Setting().get('oidc_oauth_enabled') or _oidc is None:
        logger.error(
            'OIDC OAuth is disabled or you have not yet reloaded '
            'the pda application after enabling.')
        return Response(status_code=400)

    use_ssl = get_config().get('SERVER_EXTERNAL_SSL')
    redirect_uri = str(request.url_for('oidc_authorized'))
    if isinstance(use_ssl, bool):
        if use_ssl:
            redirect_uri = redirect_uri.replace('http://', 'https://')
        else:
            redirect_uri = redirect_uri.replace('https://', 'http://')

    return await _oidc.authorize_redirect(request, redirect_uri)


# ---------------------------------------------------------------------------
# OAuth callbacks — process token, create/find user, set session, redirect
# ---------------------------------------------------------------------------

@router.get("/google/authorized", name="google_authorized")
async def google_authorized(request: Request):
    from powerdnsadmin.services.auth.oauth_handler import OAuthUserService

    _ensure_oauth()
    session = get_session(request)
    token = await _google.authorize_access_token(request)
    if token is None:
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    session['google_token'] = dict(token)

    # Process the token immediately (previously done in /login GET)
    resp = await _google.get('userinfo', token=session['google_token'])
    user_data = resp.json()
    oauth_svc = OAuthUserService()
    user, _created, error = oauth_svc.find_or_create_user(
        username=user_data['email'],
        firstname=user_data['given_name'],
        lastname=user_data['family_name'],
        email=user_data['email'],
    )
    if error:
        session.pop('google_token', None)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    session['authentication_type'] = 'OAuth'
    return authenticate_user(request, session, user, 'Google OAuth')


@router.get("/github/authorized", name="github_authorized")
async def github_authorized(request: Request):
    from powerdnsadmin.services.auth.oauth_handler import OAuthUserService

    _ensure_oauth()
    session = get_session(request)
    token = await _github.authorize_access_token(request)
    if token is None:
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    session['github_token'] = dict(token)

    resp = await _github.get('user', token=session['github_token'])
    user_data = resp.json()
    oauth_svc = OAuthUserService()
    first_name, last_name = oauth_svc.parse_full_name(user_data['name'])
    user, _created, error = oauth_svc.find_or_create_user(
        username=user_data['login'],
        firstname=first_name,
        lastname=last_name,
        email=user_data['email'],
    )
    if error:
        session.pop('github_token', None)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    session['authentication_type'] = 'OAuth'
    return authenticate_user(request, session, user, 'Github OAuth')


@router.get("/azure/authorized", name="azure_authorized")
async def azure_authorized(request: Request):
    from powerdnsadmin.services.auth.oauth_handler import OAuthUserService
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.history import History

    _ensure_oauth()
    session = get_session(request)
    token = await _azure.authorize_access_token(request)
    if token is None:
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    session['azure_token'] = dict(token)

    resp = await _azure.get(
        'me?$select=displayName,givenName,id,mail,surname,userPrincipalName',
        token=session['azure_token'])
    user_data = json.loads(resp.text)

    resp = await _azure.post(
        'me/getMemberGroups',
        json={'securityEnabledOnly': False},
        token=session['azure_token'])
    grouplookup = json.loads(resp.text)
    mygroups = grouplookup.get("value", [])

    azure_username = re.sub(r"#.*$", "", user_data["userPrincipalName"])
    azure_email = re.sub(
        r"#.*$", "",
        user_data.get("mail") or user_data["userPrincipalName"])

    oauth_svc = OAuthUserService()
    user, _created, error = oauth_svc.find_or_create_user(
        username=azure_username,
        firstname=user_data["givenName"],
        lastname=user_data["surname"],
        email=azure_email,
        fallback_email=False,
    )
    if error:
        session.pop('azure_token', None)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    session['authentication_type'] = 'OAuth'

    # Handle group memberships
    if Setting().get('azure_sg_enabled'):
        authorized, _role = OAuthUserService.assign_role_from_groups(
            user, mygroups,
            admin_group=Setting().get('azure_admin_group'),
            operator_group=Setting().get('azure_operator_group'),
            user_group=Setting().get('azure_user_group'),
        )
        if not authorized:
            session.pop('azure_token', None)
            return RedirectResponse(
                url="/login?error=not_authorized", status_code=302)

    # Handle account/group creation
    if Setting().get('azure_group_accounts_enabled') and mygroups:
        logger.info('Azure group account sync enabled')
        name_value = Setting().get('azure_group_accounts_name')
        description_value = Setting().get('azure_group_accounts_description')
        select_values = name_value
        if description_value != '':
            select_values += ',' + description_value

        mygroups = await get_azure_groups(
            'me/memberOf/microsoft.graph.group?$count=false'
            '&$securityEnabled=true&$select={}'.format(select_values),
            token=session['azure_token'])

        description_pattern = Setting().get('azure_group_accounts_description_re')
        pattern = Setting().get('azure_group_accounts_name_re')

        for azure_group in mygroups:
            if name_value in azure_group:
                group_name = azure_group[name_value]
                group_description = ''
                if description_value in azure_group:
                    group_description = azure_group[description_value]

                    if description_pattern != '':
                        matches = re.match(description_pattern, group_description)
                        if matches:
                            group_description = matches.group(1)
                        else:
                            continue

                if pattern != '':
                    matches = re.match(pattern, group_name)
                    if matches:
                        group_name = matches.group(1)
                    else:
                        continue

                account = Account()
                sanitized_group_name = Account.sanitize_name(group_name)
                account_id = account.get_id_by_name(account_name=sanitized_group_name)

                if account_id:
                    account = Account.query.get(account_id)
                    account_users = account.get_user()
                    if user.id not in account_users:
                        account.add_user(user)
                        History(
                            msg='Update account {0}'.format(account.name),
                            created_by='System',
                        ).add()
                else:
                    account = Account(
                        name=sanitized_group_name,
                        description=group_description,
                        contact='',
                        mail='',
                    )
                    account.create_account()
                    History(
                        msg='Create account {0}'.format(account.name),
                        created_by='System',
                    ).add()
                    account.add_user(user)
                    History(
                        msg='Update account {0}'.format(account.name),
                        created_by='System',
                    ).add()

    return authenticate_user(request, session, user, 'Azure OAuth')


@router.get("/oidc/authorized", name="oidc_authorized")
async def oidc_authorized(request: Request):
    from powerdnsadmin.services.auth.oauth_handler import OAuthUserService
    from powerdnsadmin.models.setting import Setting
    from powerdnsadmin.models.history import History

    _ensure_oauth()
    session = get_session(request)
    token = await _oidc.authorize_access_token(request)
    if token is None:
        return RedirectResponse(url="/login?error=access_denied", status_code=302)

    session['oidc_token'] = dict(token)

    resp = await _oidc.get('userinfo', token=session['oidc_token'])
    user_data = resp.json()
    oidc_username = user_data[Setting().get('oidc_oauth_username')]
    oidc_first_name = user_data[Setting().get('oidc_oauth_firstname')]
    oidc_last_name = user_data[Setting().get('oidc_oauth_last_name')]
    oidc_email = user_data[Setting().get('oidc_oauth_email')]

    oauth_svc = OAuthUserService()
    user, created, error = oauth_svc.find_or_create_user(
        username=oidc_username,
        firstname=oidc_first_name,
        lastname=oidc_last_name,
        email=oidc_email,
        fallback_email=False,
    )
    if error:
        session.pop('oidc_token', None)
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)
    if not created:
        success, error = oauth_svc.update_user_profile(
            user, oidc_first_name, oidc_last_name, oidc_email)
        if not success:
            session.pop('oidc_token', None)
            return RedirectResponse(url="/login?error=profile_update_failed", status_code=302)

    # OIDC account provisioning
    if (Setting().get('oidc_oauth_account_name_property')
            and Setting().get('oidc_oauth_account_description_property')):
        name_prop = Setting().get('oidc_oauth_account_name_property')
        desc_prop = Setting().get('oidc_oauth_account_description_property')

        account_to_add = []
        if name_prop in user_data and desc_prop in user_data:
            accounts_name_prop = (
                [user_data[name_prop]]
                if type(user_data[name_prop]) is not list
                else user_data[name_prop]
            )
            accounts_desc_prop = (
                [user_data[desc_prop]]
                if type(user_data[desc_prop]) is not list
                else user_data[desc_prop]
            )

            for i in range(len(accounts_name_prop)):
                description = ''
                if i < len(accounts_desc_prop):
                    description = accounts_desc_prop[i]
                account = handle_account(accounts_name_prop[i], description)
                account_to_add.append(account)

            user_accounts = user.get_accounts()

            for account in account_to_add:
                if account not in user_accounts:
                    account.add_user(user)

            if Setting().get('delete_sso_accounts'):
                for account in user_accounts:
                    if account not in account_to_add:
                        account.remove_user(user)

    session['authentication_type'] = 'OAuth'
    return authenticate_user(request, session, user, 'OIDC OAuth')


# ---------------------------------------------------------------------------
# SAML
# ---------------------------------------------------------------------------

@router.get("/saml/login", name="index.saml_login")
async def saml_login(request: Request):
    _ensure_oauth()

    if not get_config().get('SAML_ENABLED', False):
        return Response(status_code=400)

    from onelogin.saml2.utils import OneLogin_Saml2_Utils

    req = await _saml.prepare_starlette_request(request)
    auth = _saml.init_saml_auth(req)
    redirect_url = OneLogin_Saml2_Utils.get_self_url(req) + '/saml/authorized'
    return RedirectResponse(url=auth.login(return_to=redirect_url), status_code=302)


@router.get("/saml/metadata", name="index.saml_metadata")
async def saml_metadata(request: Request):
    _ensure_oauth()

    if not get_config().get('SAML_ENABLED', False):
        return Response(status_code=400)

    req = await _saml.prepare_starlette_request(request)
    auth = _saml.init_saml_auth(req)
    settings = auth.get_settings()
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)

    if len(errors) == 0:
        return Response(content=metadata, status_code=200, media_type="text/xml")
    else:
        return Response(content=', '.join(errors), status_code=500)


@router.api_route(
    "/saml/authorized",
    methods=["GET", "POST"],
    name="index.saml_authorized",
)
async def saml_authorized(request: Request):
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.role import Role
    from powerdnsadmin.models.history import History
    from onelogin.saml2.utils import OneLogin_Saml2_Utils

    config = get_config()
    session = get_session(request)
    _ensure_oauth()

    if not config.get('SAML_ENABLED', False):
        return Response(status_code=400)

    req = await _saml.prepare_starlette_request(request)
    auth = _saml.init_saml_auth(req)
    auth.process_response()
    errors = auth.get_errors()

    if len(errors) != 0:
        return JSONResponse(
            status_code=400,
            content={"detail": "SAML authentication failed", "errors": errors},
        )

    session['samlUserdata'] = auth.get_attributes()
    session['samlNameId'] = auth.get_nameid()
    session['samlSessionIndex'] = auth.get_session_index()
    self_url = OneLogin_Saml2_Utils.get_self_url(req)
    self_url = self_url + req['script_name']

    form = await request.form() if request.method == 'POST' else {}

    if 'RelayState' in form and self_url != form['RelayState']:
        return RedirectResponse(
            url=auth.redirect_to(form['RelayState']),
            status_code=302,
        )

    if config.get('SAML_ATTRIBUTE_USERNAME', False):
        username = session['samlUserdata'][
            config['SAML_ATTRIBUTE_USERNAME']][0].lower()
    else:
        username = session['samlNameId'].lower()

    user = User.query.filter_by(username=username).first()
    if not user:
        user = User(
            username=username,
            plain_text_password=None,
            email=session['samlNameId'],
        )
        user.create_local_user()

    session['user_id'] = user.id

    email_attribute_name = config.get('SAML_ATTRIBUTE_EMAIL', 'email')
    givenname_attribute_name = config.get('SAML_ATTRIBUTE_GIVENNAME', 'givenname')
    surname_attribute_name = config.get('SAML_ATTRIBUTE_SURNAME', 'surname')
    name_attribute_name = config.get('SAML_ATTRIBUTE_NAME', None)
    account_attribute_name = config.get('SAML_ATTRIBUTE_ACCOUNT', None)
    admin_attribute_name = config.get('SAML_ATTRIBUTE_ADMIN', None)
    group_attribute_name = config.get('SAML_ATTRIBUTE_GROUP', None)
    admin_group_name = config.get('SAML_GROUP_ADMIN_NAME', None)
    operator_group_name = config.get('SAML_GROUP_OPERATOR_NAME', None)
    group_to_account_mapping = create_group_to_account_mapping()

    if email_attribute_name in session['samlUserdata']:
        user.email = session['samlUserdata'][email_attribute_name][0].lower()
    if givenname_attribute_name in session['samlUserdata']:
        user.firstname = session['samlUserdata'][givenname_attribute_name][0]
    if surname_attribute_name in session['samlUserdata']:
        user.lastname = session['samlUserdata'][surname_attribute_name][0]
    if name_attribute_name in session['samlUserdata']:
        name = session['samlUserdata'][name_attribute_name][0].split(' ')
        user.firstname = name[0]
        user.lastname = ' '.join(name[1:])

    if group_attribute_name:
        user_groups = session['samlUserdata'].get(group_attribute_name, [])
    else:
        user_groups = []

    if admin_attribute_name or group_attribute_name:
        user_accounts = set(user.get_accounts())
        saml_accounts = []
        for group_mapping in group_to_account_mapping:
            mapping = group_mapping.split('=')
            group = mapping[0]
            account_name = mapping[1]
            if group in user_groups:
                account = handle_account(account_name)
                saml_accounts.append(account)

        for account_name in session['samlUserdata'].get(
                account_attribute_name, []):
            account = handle_account(account_name)
            saml_accounts.append(account)

        saml_accounts = set(saml_accounts)
        for account in saml_accounts - user_accounts:
            account.add_user(user)
            History(
                msg='Adding {0} to account {1}'.format(user.username, account.name),
                created_by='SAML Assertion',
            ).add()
        for account in user_accounts - saml_accounts:
            account.remove_user(user)
            History(
                msg='Removing {0} from account {1}'.format(user.username, account.name),
                created_by='SAML Assertion',
            ).add()

    if (admin_attribute_name
            and 'true' in session['samlUserdata'].get(admin_attribute_name, [])):
        uplift_to_admin(user)
    elif admin_group_name in user_groups:
        uplift_to_admin(user)
    elif operator_group_name in user_groups:
        uplift_to_operator(user)
    elif admin_attribute_name or group_attribute_name:
        if user.role.name != 'User':
            user.role_id = Role.query.filter_by(name='User').first().id
            History(
                msg='Demoting {0} to user'.format(user.username),
                created_by='SAML Assertion',
            ).add()

    user.plain_text_password = None
    user.update_profile()
    session['authentication_type'] = 'SAML'
    return authenticate_user(request, session, user, 'SAML')


@router.get("/saml/sls", name="index.saml_logout")
async def saml_logout(request: Request):
    config = get_config()
    session = get_session(request)
    _ensure_oauth()

    req = await _saml.prepare_starlette_request(request)
    auth = _saml.init_saml_auth(req)
    url = auth.process_slo()
    errors = auth.get_errors()

    if len(errors) == 0:
        session.clear()
        if url is not None:
            return RedirectResponse(url=url, status_code=302)
        elif config.get('SAML_LOGOUT_URL') is not None:
            return RedirectResponse(
                url=config.get('SAML_LOGOUT_URL'), status_code=302)
        else:
            return RedirectResponse(url="/login", status_code=302)
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": "SAML logout failed", "errors": errors},
        )


# ---------------------------------------------------------------------------
# DynDNS
# ---------------------------------------------------------------------------

@router.api_route(
    "/nic/checkip.html",
    methods=["GET", "POST"],
    name="index.dyndns_checkip",
)
async def dyndns_checkip(request: Request):
    """DynDNS check-IP endpoint (ddclient default 'web' checkip service)."""
    forwarded = request.headers.get("x-real-ip")
    if not forwarded:
        forwarded = request.client.host if request.client else "unknown"
    return PlainTextResponse(forwarded)


@router.api_route(
    "/nic/update",
    methods=["GET", "POST"],
    name="index.dyndns_update",
)
async def dyndns_update(request: Request):
    """DynDNS record update endpoint.

    Response codes (plain text):
        good    — update successful
        nochg   — IP already matches
        nohost  — hostname not found / no access
        911     — server error
    """
    from powerdnsadmin.models.user import User
    from powerdnsadmin.models.domain import Domain
    from powerdnsadmin.models.domain_user import DomainUser
    from powerdnsadmin.models.domain_setting import DomainSetting
    from powerdnsadmin.models.account import Account
    from powerdnsadmin.models.account_user import AccountUser
    from powerdnsadmin.models.record import Record
    from powerdnsadmin.models.history import History
    from powerdnsadmin.models.base import db
    from powerdnsadmin.lib import utils

    session = get_session(request)
    user = get_current_user(request)
    if user is None:
        return Response(
            status_code=401,
            headers={'WWW-Authenticate': 'Basic'},
        )

    hostname = request.query_params.get('hostname')
    myip = request.query_params.get('myip')

    if not hostname:
        History(
            msg="DynDNS update: missing hostname parameter",
            created_by=user.username,
        ).add()
        return PlainTextResponse("nohost")

    try:
        if user.role.name in ['Administrator', 'Operator']:
            domains = Domain.query.all()
        else:
            domains = (
                db.session.query(Domain)
                .outerjoin(DomainUser, Domain.id == DomainUser.domain_id)
                .outerjoin(Account, Domain.account_id == Account.id)
                .outerjoin(AccountUser, Account.id == AccountUser.account_id)
                .filter(
                    db.or_(
                        DomainUser.user_id == user.id,
                        AccountUser.user_id == user.id,
                    )
                ).all()
            )
    except Exception as e:
        logger.error('DynDNS Error: %s', e)
        logger.debug(traceback.format_exc())
        return PlainTextResponse("911")

    domain = None
    domain_segments = hostname.split('.')
    for _idx in range(len(domain_segments)):
        full_domain = '.'.join(domain_segments)
        potential_domain = Domain.query.filter(
            Domain.name == full_domain).first()
        if potential_domain in domains:
            domain = potential_domain
            break
        domain_segments.pop(0)

    if not domain:
        History(
            msg="DynDNS update: attempted update of {0} but it does not exist for this user".format(hostname),
            created_by=user.username,
        ).add()
        return PlainTextResponse("nohost")

    myip_addr = []
    if myip:
        for address in myip.split(','):
            myip_addr += utils.validate_ipaddress(address)

    forwarded_for = request.headers.get(
        'x-forwarded-for',
        request.client.host if request.client else "unknown")
    remote_addr = utils.validate_ipaddress(forwarded_for.split(', ')[0])

    response = 'nochg'
    for ip in myip_addr or remote_addr:
        if isinstance(ip, ipaddress.IPv4Address):
            rtype = 'A'
        else:
            rtype = 'AAAA'

        r = Record(name=hostname, type=rtype)
        if r.exists(domain.name) and r.is_allowed_edit():
            if r.data == str(ip):
                History(
                    msg="DynDNS update: attempted update of {0} but record already up-to-date".format(hostname),
                    created_by=user.username,
                    domain_id=domain.id,
                ).add()
            else:
                oldip = r.data
                result = r.update(domain.name, str(ip))
                if result['status'] == 'ok':
                    History(
                        msg='DynDNS update: updated {} successfully'.format(hostname),
                        detail=json.dumps({
                            'domain': domain.name,
                            'record': hostname,
                            'type': rtype,
                            'old_value': oldip,
                            'new_value': str(ip),
                        }),
                        created_by=user.username,
                        domain_id=domain.id,
                    ).add()
                    response = 'good'
                else:
                    response = '911'
                    break
        elif r.is_allowed_edit():
            ondemand_creation = DomainSetting.query.filter(
                DomainSetting.domain == domain).filter(
                DomainSetting.setting == 'create_via_dyndns').first()
            if (ondemand_creation is not None
                    and strtobool(ondemand_creation.value)):
                rrset_data = [{
                    "changetype": "REPLACE",
                    "name": hostname + '.',
                    "ttl": 3600,
                    "type": rtype,
                    "records": [{
                        "content": str(ip),
                        "disabled": False,
                    }],
                    "comments": [],
                }]
                rrset = {"rrsets": rrset_data}
                result = Record().add(domain.name, rrset)
                if result['status'] == 'ok':
                    History(
                        msg='DynDNS update: created record {0} in zone {1} successfully'.format(
                            hostname, domain.name),
                        detail=json.dumps({
                            'domain': domain.name,
                            'record': hostname,
                            'value': str(ip),
                        }),
                        created_by=user.username,
                        domain_id=domain.id,
                    ).add()
                    response = 'good'
        else:
            History(
                msg='DynDNS update: attempted update of {0} but it does not exist for this user'.format(hostname),
                created_by=user.username,
            ).add()

    return PlainTextResponse(response)


# ---------------------------------------------------------------------------
# Email confirmation
# ---------------------------------------------------------------------------

@router.get("/confirm/{token}", name="index.confirm_email")
async def confirm_email(token: str, request: Request):
    from powerdnsadmin.models.user import User
    from powerdnsadmin.services.token import confirm_token as do_confirm_token

    email = do_confirm_token(token)
    if not email:
        return RedirectResponse(url="/login?confirmed=invalid", status_code=302)

    user = User.query.filter_by(email=email).first()
    if not user:
        return RedirectResponse(url="/login?confirmed=invalid", status_code=302)

    if user.confirmed:
        return RedirectResponse(url="/login?confirmed=already", status_code=302)
    else:
        user.update_confirmed(confirmed=1)
        logger.info("User email %s confirmed successfully", email)
        return RedirectResponse(url="/login?confirmed=success", status_code=302)


# ---------------------------------------------------------------------------
# Swagger spec
# ---------------------------------------------------------------------------

@router.get("/swagger", name="index.swagger_spec")
async def swagger_spec(request: Request):
    try:
        pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        spec_path = os.path.join(pkg_root, "swagger-spec.yaml")
        with open(spec_path, 'r') as spec_file:
            loaded_spec = load(spec_file.read(), Loader)
    except Exception as e:
        logger.error('Cannot view swagger spec. Error: %s', e)
        logger.debug(traceback.format_exc())
        return Response(status_code=500)

    return JSONResponse(content=loaded_spec, status_code=200)
