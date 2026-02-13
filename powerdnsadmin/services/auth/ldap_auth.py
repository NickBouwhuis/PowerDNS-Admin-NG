"""
LDAP/Active Directory authentication service.

Handles LDAP connection, user lookup, credential validation,
and group-based role assignment.
"""
import traceback
from collections import OrderedDict

import ldap
import ldap.filter
from flask import current_app
from sqlalchemy import select, func

from ...models.base import db
from ...models.setting import Setting


class LDAPAuthService:
    """Service for LDAP and Active Directory authentication."""

    def __init__(self):
        self._setting = Setting()

    def _get(self, key):
        return self._setting.get(key)

    # ── Connection ────────────────────────────────────────────────────

    def init_conn(self):
        """Initialize and return an LDAP connection."""
        tls_verify = self._get('ldap_tls_verify')
        if tls_verify:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
        else:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

        conn = ldap.initialize(self._get('ldap_uri'))
        conn.set_option(ldap.OPT_REFERRALS, ldap.OPT_OFF)
        conn.set_option(ldap.OPT_PROTOCOL_VERSION, 3)
        conn.set_option(ldap.OPT_X_TLS_DEMAND, True)
        conn.set_option(ldap.OPT_DEBUG_LEVEL, 255)
        conn.protocol_version = ldap.VERSION3
        return conn

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def escape_filter_chars(filter_str):
        """Escape special characters for LDAP search filters."""
        escape_chars = ['\\', '*', '(', ')', '\x00']
        replace_chars = ['\\5c', '\\2a', '\\28', '\\29', '\\00']
        for esc, rep in zip(escape_chars, replace_chars):
            filter_str = filter_str.replace(esc, rep)
        return filter_str

    def search(self, search_filter, base_dn, username, password,
               retrieve_attributes=None):
        """Execute an LDAP search.

        Args:
            search_filter: LDAP search filter string.
            base_dn: Base DN for the search.
            username: Username for LDAP bind.
            password: Password for LDAP bind.
            retrieve_attributes: List of attributes to retrieve.

        Returns:
            list: Search result entries, or None on error.
        """
        try:
            conn = self.init_conn()
            if self._get('ldap_type') == 'ad':
                conn.simple_bind_s(
                    "{0}@{1}".format(username, self._get('ldap_domain')),
                    password)
            else:
                conn.simple_bind_s(
                    self._get('ldap_admin_username'),
                    self._get('ldap_admin_password'))

            ldap_result_id = conn.search(
                base_dn, ldap.SCOPE_SUBTREE,
                search_filter, retrieve_attributes)
            result_set = []

            while True:
                result_type, result_data = conn.result(ldap_result_id, 0)
                if result_data == []:
                    break
                if result_type == ldap.RES_SEARCH_ENTRY:
                    result_set.append(result_data)
            return result_set

        except ldap.LDAPError as e:
            current_app.logger.error(e)
            current_app.logger.debug('baseDN: {0}'.format(base_dn))
            current_app.logger.debug(traceback.format_exc())
            return None

    def bind(self, ldap_username, password):
        """Attempt LDAP bind with the given credentials.

        Returns:
            bool: True if bind succeeds.
        """
        try:
            conn = self.init_conn()
            conn.simple_bind_s(ldap_username, password)
            return True
        except ldap.LDAPError as e:
            current_app.logger.error(e)
            return False

    # ── Group Role Resolution ─────────────────────────────────────────

    def _resolve_role_ldap(self, username, password, ldap_username,
                           filter_group, filter_groupname,
                           admin_group, operator_group, user_group):
        """Resolve role from LDAP group membership (OpenLDAP style)."""
        group_filter = "(&({0}={1}){2})".format(
            filter_groupname, ldap_username, filter_group)
        current_app.logger.debug(
            'Ldap groupSearchFilter {0}'.format(group_filter))

        if admin_group and self.search(group_filter, admin_group,
                                       username, password):
            current_app.logger.info(
                'User {0} is part of the "{1}" group (admin access)'.format(
                    username, admin_group))
            return 'Administrator'

        if operator_group and self.search(group_filter, operator_group,
                                          username, password):
            current_app.logger.info(
                'User {0} is part of the "{1}" group (operator access)'.format(
                    username, operator_group))
            return 'Operator'

        if user_group and self.search(group_filter, user_group,
                                      username, password):
            current_app.logger.info(
                'User {0} is part of the "{1}" group (user access)'.format(
                    username, user_group))
            return 'User'

        current_app.logger.error(
            'User {0} is not part of any security groups '
            'that allow access to PowerDNS-Admin'.format(username))
        return None

    def _resolve_role_ad(self, username, password, user_dn, base_dn,
                         admin_group, operator_group, user_group):
        """Resolve role from AD group membership (recursive nested groups)."""
        roles = OrderedDict(
            Administrator=admin_group,
            Operator=operator_group,
            User=user_group,
        )

        escaped_dn = self.escape_filter_chars(user_dn)
        sf_groups = ""
        for group in roles.values():
            if group:
                sf_groups += f"(distinguishedName={group})"

        sf_member = f"(member:1.2.840.113556.1.4.1941:={escaped_dn})"
        search_filter = f"(&(|{sf_groups}){sf_member})"
        current_app.logger.debug(
            f"LDAP groupSearchFilter '{search_filter}'")

        ldap_user_groups = [
            group[0][0]
            for group in (self.search(search_filter, base_dn,
                                      username, password) or [])
        ]

        if not ldap_user_groups:
            current_app.logger.error(
                f"User '{username}' does not belong to any group "
                "while LDAP_GROUP_SECURITY_ENABLED is ON")
            return None

        current_app.logger.debug(
            f"LDAP User security groups for user '{username}': "
            + " ".join(ldap_user_groups))

        for role, ldap_group in roles.items():
            if ldap_group and ldap_group in ldap_user_groups:
                current_app.logger.info(
                    f"User '{username}' member of the '{ldap_group}' group "
                    f"('{role}' access)")
                return role

        return 'User'

    # ── Main Validation ───────────────────────────────────────────────

    def validate(self, username, password, src_ip='', trust_user=False):
        """Validate LDAP user credentials and resolve role.

        Args:
            username: The username to validate.
            password: The user's password.
            src_ip: Source IP for logging.
            trust_user: If True, skip password verification.

        Returns:
            tuple: (success: bool, role_name: str or None)
        """
        from ...models.user import User
        from ...models.role import Role

        ldap_type = self._get('ldap_type')
        base_dn = self._get('ldap_base_dn')
        filter_basic = self._get('ldap_filter_basic')
        filter_username = self._get('ldap_filter_username')
        filter_group = self._get('ldap_filter_group')
        filter_groupname = self._get('ldap_filter_groupname')
        admin_group = self._get('ldap_admin_group')
        operator_group = self._get('ldap_operator_group')
        user_group = self._get('ldap_user_group')
        group_security_enabled = self._get('ldap_sg_enabled')

        role_name = 'User'

        # Step 1: Validate AD password first (AD binds with user creds)
        if ldap_type == 'ad' and not trust_user:
            ldap_username = "{0}@{1}".format(
                username, self._get('ldap_domain'))
            if not self.bind(ldap_username, password):
                current_app.logger.error(
                    'User "{0}" input a wrong LDAP password. '
                    'Authentication request from {1}'.format(username, src_ip))
                return False, None

        # Step 2: Search for user in LDAP
        search_filter = "(&({0}={1}){2})".format(
            filter_username, username, filter_basic)
        current_app.logger.debug(
            'Ldap searchFilter {0}'.format(search_filter))

        ldap_result = self.search(search_filter, base_dn, username, password)
        current_app.logger.debug(
            'Ldap search result: {0}'.format(ldap_result))

        if not ldap_result:
            current_app.logger.warning(
                'LDAP User "{0}" does not exist. '
                'Authentication request from {1}'.format(username, src_ip))
            return False, None

        try:
            ldap_user_dn = ldap.filter.escape_filter_chars(
                ldap_result[0][0][0])

            # Step 3: Validate OpenLDAP password (binds with user DN)
            if ldap_type != 'ad' and not trust_user:
                if not self.bind(ldap_user_dn, password):
                    current_app.logger.error(
                        'User "{0}" input a wrong LDAP password. '
                        'Authentication request from {1}'.format(
                            username, src_ip))
                    return False, None

            # Step 4: Resolve role from group membership
            if group_security_enabled:
                try:
                    if ldap_type == 'ldap':
                        role_name = self._resolve_role_ldap(
                            username, password, ldap_user_dn,
                            filter_group, filter_groupname,
                            admin_group, operator_group, user_group)
                    elif ldap_type == 'ad':
                        role_name = self._resolve_role_ad(
                            username, password, ldap_result[0][0][0],
                            base_dn, admin_group, operator_group, user_group)
                    else:
                        current_app.logger.error('Invalid LDAP type')
                        return False, None

                    if role_name is None:
                        return False, None

                except Exception as e:
                    current_app.logger.error(
                        'LDAP group lookup for user "{0}" has failed. '
                        'Authentication request from {1}'.format(
                            username, src_ip))
                    current_app.logger.debug(traceback.format_exc())
                    return False, None

        except Exception as e:
            current_app.logger.error(
                'Wrong LDAP configuration. {0}'.format(e))
            current_app.logger.debug(traceback.format_exc())
            return False, None

        # Step 5: Create user in DB if not exists
        if not db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none():
            self._create_ldap_user(
                username, ldap_type, ldap_result, role_name)

        # Step 6: Update role if group security is enabled
        if group_security_enabled:
            user = db.session.execute(
                select(User).where(User.username == username)
            ).scalar_one_or_none()
            if user:
                user.set_role(role_name)

        return True, role_name

    def _create_ldap_user(self, username, ldap_type, ldap_result, role_name):
        """Create a new user in the DB from LDAP data."""
        from ...models.user import User
        from ...models.role import Role

        user = User(username=username)
        user.firstname = username
        user.lastname = ''

        try:
            if ldap_type == 'ldap':
                user.firstname = ldap_result[0][0][1]['givenName'][0].decode(
                    "utf-8")
                user.lastname = ldap_result[0][0][1]['sn'][0].decode("utf-8")
                user.email = ldap_result[0][0][1]['mail'][0].decode("utf-8")
            elif ldap_type == 'ad':
                user.firstname = ldap_result[0][0][1]['name'][0].decode(
                    "utf-8")
                user.email = ldap_result[0][0][1]['userPrincipalName'][
                    0].decode("utf-8")
        except Exception as e:
            current_app.logger.warning(
                "Reading ldap data threw an exception {0}".format(e))
            current_app.logger.debug(traceback.format_exc())

        # First user gets Administrator role
        if db.session.execute(
            select(func.count()).select_from(User)
        ).scalar() == 0:
            user.role_id = db.session.execute(
                select(Role).where(Role.name == 'Administrator')
            ).scalar_one().id
        else:
            user.role_id = db.session.execute(
                select(Role).where(Role.name == role_name)
            ).scalar_one().id

        user.create_user()
        current_app.logger.info(
            'Created user "{0}" in the DB'.format(username))
