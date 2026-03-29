import logging
import os
import base64
import traceback
import pyotp
from sqlalchemy import orm
import qrcode as qrc
import qrcode.image.svg as qrc_svg
from io import BytesIO

from ..services.auth.local import hash_password, check_password as _check_pw
from ..services.auth.ldap_auth import LDAPAuthService

from sqlalchemy import select, delete, func

from .base import db
from .role import Role
from .setting import Setting
from .domain_user import DomainUser
from .account_user import AccountUser

logger = logging.getLogger(__name__)


class Anonymous:
    """Anonymous user placeholder (replaces Flask-Login's AnonymousUserMixin)."""
    is_authenticated = False
    is_active = False
    is_anonymous = True

    def __init__(self):
        self.username = 'Anonymous'

    def get_id(self):
        return None


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    password = db.Column(db.String(64))
    firstname = db.Column(db.String(64))
    lastname = db.Column(db.String(64))
    email = db.Column(db.String(128))
    otp_secret = db.Column(db.String(16))
    confirmed = db.Column(db.SmallInteger, nullable=False, default=0)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    role = db.relationship('Role', back_populates="users", lazy=True)
    accounts = None

    def __init__(self,
                 id=None,
                 username=None,
                 password=None,
                 plain_text_password=None,
                 firstname=None,
                 lastname=None,
                 role_id=None,
                 email=None,
                 otp_secret=None,
                 confirmed=False,
                 reload_info=True):
        self.id = id
        self.username = username
        self.password = password
        self.plain_text_password = plain_text_password
        self.firstname = firstname
        self.lastname = lastname
        self.role_id = role_id
        self.email = email
        self.otp_secret = otp_secret
        self.confirmed = confirmed

        if reload_info:
            user_info = self.get_user_info_by_id(
            ) if id else self.get_user_info_by_username()

            if user_info:
                self.id = user_info.id
                self.username = user_info.username
                self.firstname = user_info.firstname
                self.lastname = user_info.lastname
                self.email = user_info.email
                self.role_id = user_info.role_id
                self.otp_secret = user_info.otp_secret
                self.confirmed = user_info.confirmed

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return '<User {0}>'.format(self.username)

    def get_totp_uri(self):
        return "otpauth://totp/{0}:{1}?secret={2}&issuer=PowerDNS-AdminNG".format(
            Setting().get('site_name'), self.username, self.otp_secret)

    def verify_totp(self, token):
        totp = pyotp.TOTP(self.otp_secret)
        return totp.verify(token, valid_window = 5)

    def get_hashed_password(self, plain_text_password=None):
        pw = plain_text_password if plain_text_password else getattr(
            self, 'plain_text_password', None)
        return hash_password(pw)

    def check_password(self, hashed_password):
        pw = getattr(self, 'plain_text_password', None)
        return _check_pw(pw, hashed_password)

    def get_user_info_by_id(self):
        user_info = db.session.get(User, int(self.id))
        return user_info

    def get_user_info_by_username(self):
        user_info = db.session.execute(
            select(User).where(User.username == self.username)
        ).scalar_one_or_none()
        return user_info

    def ldap_init_conn(self):
        """Deprecated: use LDAPAuthService.init_conn() instead."""
        return LDAPAuthService().init_conn()

    def ldap_search(self, searchFilter, baseDN, retrieveAttributes=None):
        """Deprecated: use LDAPAuthService.search() instead."""
        svc = LDAPAuthService()
        return svc.search(
            searchFilter, baseDN, self.username,
            getattr(self, 'password', ''), retrieveAttributes)

    def ldap_auth(self, ldap_username, password):
        """Deprecated: use LDAPAuthService.bind() instead."""
        return LDAPAuthService().bind(ldap_username, password)

    def is_validate(self, method, src_ip='', trust_user=False):
        """
        Validate user credential.

        Delegates to LocalAuthService or LDAPAuthService.
        """
        if method == 'LOCAL':
            from ..services.auth.local import LocalAuthService
            svc = LocalAuthService()
            return svc.validate(
                self.username,
                getattr(self, 'plain_text_password', None),
                src_ip=src_ip,
                trust_user=trust_user,
            )

        if method == 'LDAP':
            svc = LDAPAuthService()
            success, _role_name = svc.validate(
                self.username,
                getattr(self, 'password', ''),
                src_ip=src_ip,
                trust_user=trust_user,
            )
            return success

        logger.error('Unsupported authentication method')
        return False

    def create_user(self):
        """
        If user logged in successfully via LDAP in the first time
        We will create a local user (in DB) in order to manage user
        profile such as name, roles,...
        """

        # Set an invalid password hash for non local users
        self.password = '*'

        db.session.add(self)
        db.session.commit()

    def create_local_user(self):
        """
        Create local user witch stores username / password in the DB
        """
        # check if username existed
        user = db.session.execute(
            select(User).where(func.lower(User.username) == self.username.lower())
        ).scalar_one_or_none()
        if user:
            return {'status': False, 'msg': 'Username is already in use'}

        # check if email existed
        user = db.session.execute(
            select(User).where(func.lower(User.email) == self.email.lower())
        ).scalar_one_or_none()
        if user:
            return {'status': False, 'msg': 'Email address is already in use'}

        # first register user will be in Administrator role
        if self.role_id is None:
            self.role_id = db.session.execute(
                select(Role).where(Role.name == 'User')
            ).scalar_one().id
        if db.session.execute(
            select(func.count()).select_from(User)
        ).scalar() == 0:
            self.role_id = db.session.execute(
                select(Role).where(Role.name == 'Administrator')
            ).scalar_one().id

        if hasattr(self, "plain_text_password"):
            if self.plain_text_password != None:
                self.password = self.get_hashed_password(
                    self.plain_text_password)
        else:
            self.password = '*'

        if self.password and self.password != '*':
            self.password = self.password.decode("utf-8")

        db.session.add(self)
        db.session.commit()
        return {'status': True, 'msg': 'Created user successfully'}

    def update_local_user(self):
        """
        Update local user
        """
        # Sanity check - account name
        if self.username == "":
            return {'status': False, 'msg': 'No user name specified'}

        # read user and check that it exists
        user = db.session.execute(
            select(User).where(User.username == self.username)
        ).scalar_one_or_none()
        if not user:
            return {'status': False, 'msg': 'User does not exist'}

        # check if new email exists (only if changed)
        if user.email != self.email:
            checkuser = db.session.execute(
                select(User).where(User.email == self.email)
            ).scalar_one_or_none()
            if checkuser:
                return {
                    'status': False,
                    'msg': 'New email address is already in use'
                }

        user.firstname = self.firstname
        user.lastname = self.lastname
        user.email = self.email

        # store new password hash (only if changed)
        if hasattr(self, "plain_text_password"):
            if self.plain_text_password != None:
                user.password = self.get_hashed_password(
                    self.plain_text_password).decode("utf-8")

        db.session.commit()
        return {'status': True, 'msg': 'User updated successfully'}

    def update_profile(self, enable_otp=None):
        """
        Update user profile
        """
        user = db.session.execute(
            select(User).where(User.username == self.username)
        ).scalar_one_or_none()
        if not user:
            return False

        user.firstname = self.firstname if self.firstname else user.firstname
        user.lastname = self.lastname if self.lastname else user.lastname

        if hasattr(self, "plain_text_password"):
            if self.plain_text_password != None:
                user.password = self.get_hashed_password(
                 self.plain_text_password).decode("utf-8")

        if self.email:
            # Can not update to a new email that
            # already been used.
            existing_email = db.session.execute(
                select(User).where(
                    User.email == self.email,
                    User.username != self.username,
                )
            ).scalar_one_or_none()
            if existing_email:
                return False
            # If need to verify new email,
            # update the "confirmed" status.
            if user.email != self.email:
                user.email = self.email
                if Setting().get('verify_user_email'):
                    user.confirmed = 0

        if enable_otp is not None:
            user.otp_secret = ""

        if enable_otp == True:
            # generate the opt secret key
            user.otp_secret = base64.b32encode(os.urandom(10)).decode('utf-8')

        try:
            db.session.add(user)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    def update_confirmed(self, confirmed):
        """
        Update user email confirmation status
        """
        self.confirmed = confirmed
        db.session.commit()

    def get_domains(self):
        """
        Get list of zones which the user is granted to have
        access.

        Note: This doesn't include the permission granting from Account
        which user belong to
        """
        return self.get_domain_query().all()

    def get_user_domains(self):
        from .account import Account
        from .domain import Domain
        from .account_user import AccountUser
        from .domain_user import DomainUser
        from sqlalchemy import or_

        domains = db.session.execute(
            select(Domain)
            .outerjoin(DomainUser, Domain.id == DomainUser.domain_id)
            .outerjoin(Account, Domain.account_id == Account.id)
            .outerjoin(AccountUser, Account.id == AccountUser.account_id)
            .where(or_(
                DomainUser.user_id == self.id,
                AccountUser.user_id == self.id,
            ))
        ).scalars().all()
        return domains

    def delete(self):
        """
        Delete a user
        """
        # revoke all user privileges first
        self.revoke_privilege()

        try:
            db.session.execute(
                delete(User).where(User.username == self.username)
            )
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logger.error('Cannot delete user {0} from DB. DETAIL: {1}'.format(
                self.username, e))
            return False

    def revoke_privilege(self, update_user=False):
        """
        Revoke all privileges from a user
        """
        user = db.session.execute(
            select(User).where(User.username == self.username)
        ).scalar_one_or_none()

        if user:
            user_id = user.id
            try:
                db.session.execute(
                    delete(DomainUser).where(DomainUser.user_id == user_id)
                )
                if (update_user)==True:
                    db.session.execute(
                        delete(AccountUser).where(AccountUser.user_id == user_id)
                    )
                db.session.commit()
                return True
            except Exception as e:
                db.session.rollback()
                logger.error(
                    'Cannot revoke user {0} privileges. DETAIL: {1}'.format(
                        self.username, e))
                return False
        return False

    def set_role(self, role_name):
        role = db.session.execute(
            select(Role).where(Role.name == role_name)
        ).scalar_one_or_none()
        if role:
            user = db.session.execute(
                select(User).where(User.username == self.username)
            ).scalar_one_or_none()
            user.role_id = role.id
            db.session.commit()
            return {'status': True, 'msg': 'Set user role successfully'}
        else:
            return {'status': False, 'msg': 'Role does not exist'}

    @orm.reconstructor
    def set_account(self):
        self.accounts = self.get_accounts()

    def get_accounts(self):
        """
        Get accounts associated with this user
        """
        from .account import Account
        from .account_user import AccountUser
        accounts = []
        query = db.session.execute(
            select(AccountUser, Account)
            .where(
                self.id == AccountUser.user_id,
                Account.id == AccountUser.account_id,
            )
            .order_by(Account.name)
        ).all()
        for q in query:
            accounts.append(q[1])
        return accounts

    def get_qrcode_value(self):
        img = qrc.make(self.get_totp_uri(),
                    image_factory=qrc_svg.SvgPathImage)
        stream = BytesIO()
        img.save(stream)
        return stream.getvalue()


    def read_entitlements(self, key):
        """
        Get entitlements from ldap server associated with this user
        """
        LDAP_BASE_DN = Setting().get('ldap_base_dn')
        LDAP_FILTER_USERNAME = Setting().get('ldap_filter_username')
        LDAP_FILTER_BASIC = Setting().get('ldap_filter_basic')
        searchFilter = "(&({0}={1}){2})".format(LDAP_FILTER_USERNAME,
                                                        self.username,
                                                        LDAP_FILTER_BASIC)
        logger.debug('Ldap searchFilter {0}'.format(searchFilter))
        ldap_result = self.ldap_search(searchFilter, LDAP_BASE_DN, [key])
        logger.debug('Ldap search result: {0}'.format(ldap_result))
        entitlements=[]
        if ldap_result:
            dict=ldap_result[0][0][1]
            if len(dict)!=0:
                for entitlement in dict[key]:
                    entitlements.append(entitlement.decode("utf-8"))
            else:
                e="Not found value in the autoprovisioning attribute field "
                logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
        return entitlements

    def updateUser(self, Entitlements):
        """
        Update user associations based on ldap attribute
        """
        entitlements= getCorrectEntitlements(Entitlements)
        if len(entitlements)!=0:
            self.revoke_privilege(True)
            for entitlement in entitlements:
                arguments=entitlement.split(':')
                entArgs=arguments[arguments.index('powerdns-admin')+1:]
                role= entArgs[0]
                self.set_role(role)
                if (role=="User") and len(entArgs)>1:
                    current_domains=getUserInfo(self.get_user_domains())
                    current_accounts=getUserInfo(self.get_accounts())
                    domain=entArgs[1]
                    self.addMissingDomain(domain, current_domains)
                    if len(entArgs)>2:
                        account=entArgs[2]
                        self.addMissingAccount(account, current_accounts)

    def addMissingDomain(self, autoprovision_domain, current_domains):
        """
        Add domain gathered by autoprovisioning to the current zones list of a user
        """
        from ..models.domain import Domain
        user = db.session.execute(
            select(User).where(User.username == self.username)
        ).scalar_one_or_none()
        if autoprovision_domain not in current_domains:
            domain = db.session.execute(
                select(Domain).where(Domain.name == autoprovision_domain)
            ).scalar_one_or_none()
            if domain!=None:
                domain.add_user(user)

    def addMissingAccount(self, autoprovision_account, current_accounts):
        """
        Add account gathered by autoprovisioning to the current accounts list of a user
        """
        from ..models.account import Account
        user = db.session.execute(
            select(User).where(User.username == self.username)
        ).scalar_one_or_none()
        if autoprovision_account not in current_accounts:
            account = db.session.execute(
                select(Account).where(Account.name == autoprovision_account)
            ).scalar_one_or_none()
            if account!=None:
                account.add_user(user)

def getCorrectEntitlements(Entitlements):
    """
    Gather a list of valid records from the ldap attribute given
    """
    from ..models.role import Role
    urn_value=Setting().get('urn_value')
    urnArgs=[x.lower() for x in urn_value.split(':')]
    entitlements=[]
    for Entitlement in Entitlements:
        arguments=Entitlement.split(':')

        if ('powerdns-admin' in arguments):
            prefix=arguments[0:arguments.index('powerdns-admin')]
            prefix=[x.lower() for x in prefix]
            if (prefix!=urnArgs):
                e= "Typo in first part of urn value"
                logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
                continue

        else:
            e="Entry not a PowerDNS-AdminNG record"
            logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
            continue

        if len(arguments)<=len(urnArgs)+1: #prefix:powerdns-admin
            e="No value given after the prefix"
            logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
            continue

        entArgs=arguments[arguments.index('powerdns-admin')+1:]
        role=entArgs[0]
        roles = db.session.execute(select(Role)).scalars().all()
        role_names=get_role_names(roles)

        if role not in role_names:
            e="Role given by entry not a role available in PowerDNS-AdminNG. Check for spelling errors"
            logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
            continue

        if len(entArgs)>1:
            if (role!="User"):
                e="Too many arguments for Admin or Operator"
                logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
                continue
            else:
                if len(entArgs)<=3:
                    if entArgs[1] and not checkIfDomainExists(entArgs[1]):
                        continue
                    if len(entArgs)==3:
                        if entArgs[2] and not checkIfAccountExists(entArgs[2]):
                            continue
                else:
                    e="Too many arguments"
                    logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
                    continue

        entitlements.append(Entitlement)

    return entitlements


def checkIfDomainExists(domainName):
    from ..models.domain import Domain
    result = db.session.execute(
        select(Domain).where(Domain.name == domainName)
    ).scalars().all()
    if len(result)==0:
        e= domainName + " is not found in the database"
        logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
        return False
    return True

def checkIfAccountExists(accountName):
    from ..models.account import Account
    result = db.session.execute(
        select(Account).where(Account.name == accountName)
    ).scalars().all()
    if len(result)==0:
        e= accountName + " is not found in the database"
        logger.warning("Cannot apply autoprovisioning on user: {}".format(e))
        return False
    return True

def get_role_names(roles):
    """
    returns all the roles available in database in string format
    """
    roles_list=[]
    for role in roles:
        roles_list.append(role.name)
    return roles_list

def getUserInfo(DomainsOrAccounts):
    current=[]
    for DomainOrAccount in DomainsOrAccounts:
        current.append(DomainOrAccount.name)
    return current
