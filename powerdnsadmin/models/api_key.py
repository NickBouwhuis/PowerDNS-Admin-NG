import logging
import secrets
import string

import bcrypt
from sqlalchemy import select

from .base import db
from ..models.role import Role
from ..models.domain import Domain
from ..models.account import Account

logger = logging.getLogger(__name__)

class ApiKey(db.Model):
    __tablename__ = "apikey"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.String(255))
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'))
    role = db.relationship('Role', back_populates="apikeys", lazy=True)
    domains = db.relationship("Domain",
                              secondary="domain_apikey",
                              back_populates="apikeys")
    accounts = db.relationship("Account",
                               secondary="apikey_account",
                               back_populates="apikeys")

    def __init__(self, key=None, desc=None, description=None, role_name=None, domains=[], accounts=[]):
        self.id = None
        self.description = description or desc
        self.role_name = role_name
        self.domains[:] = domains
        self.accounts[:] = accounts
        if not key:
            rand_key = ''.join(
                secrets.choice(string.ascii_letters + string.digits)
                for _ in range(15))
            self.plain_key = rand_key
            self.key = self.get_hashed_password(rand_key).decode('utf-8')
            logger.debug("Hashed key: {0}".format(self.key))
        else:
            self.key = key

    def create(self):
        try:
            self.role = db.session.execute(
                select(Role).where(Role.name == self.role_name)
            ).scalar_one_or_none()
            db.session.add(self)
            db.session.commit()
        except Exception as e:
            logger.error('Can not update api key table. Error: {0}'.format(e))
            db.session.rollback()
            raise e

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception as e:
            msg_str = 'Can not delete api key template. Error: {0}'
            logger.error(msg_str.format(e))
            db.session.rollback()
            raise e

    def update(self, role_name=None, description=None, domains=None, accounts=None):
        try:
          if role_name:
              role = db.session.execute(
                  select(Role).where(Role.name == role_name)
              ).scalar_one_or_none()
              self.role_id = role.id

          if description:
              self.description = description

          if domains is not None:
              domain_object_list = db.session.execute(
                  select(Domain).where(Domain.name.in_(domains))
              ).scalars().all()
              self.domains[:] = domain_object_list

          if accounts is not None:
              account_object_list = db.session.execute(
                  select(Account).where(Account.name.in_(accounts))
              ).scalars().all()
              self.accounts[:] = account_object_list

          db.session.commit()
        except Exception as e:
          msg_str = 'Update of apikey failed. Error: {0}'
          logger.error(msg_str.format(e))
          db.session.rollback()  # fixed line
          raise e

    def get_hashed_password(self, plain_text_password=None):
        # Hash a password for the first time
        #   (Using bcrypt, the salt is saved into the hash itself)
        if plain_text_password is None:
            return plain_text_password

        if plain_text_password:
            pw = plain_text_password
        else:
            pw = self.plain_text_password

        # The salt value is currently re-used here intentionally because
        # the implementation relies on just the API key's value itself
        # for database lookup: ApiKey.is_validate() would have no way of
        # discerning whether any given key is valid if bcrypt.gensalt()
        # was used. As far as is known, this is fine as long as the
        # value of new API keys is randomly generated in a
        # cryptographically secure fashion, as this then makes
        # expendable as an exception the otherwise vital protection of
        # proper salting as provided by bcrypt.gensalt().
        from powerdnsadmin.core.config import get_config
        return bcrypt.hashpw(pw.encode('utf-8'),
                             get_config()['SALT'].encode('utf-8'))

    def check_password(self, hashed_password):
        # Check hashed password. Using bcrypt,
        # the salt is saved into the hash itself
        if self.plain_text_password:
            return bcrypt.checkpw(self.plain_text_password.encode('utf-8'),
                                  hashed_password.encode('utf-8'))
        return False

    def is_validate(self, method, src_ip=''):
        """
        Validate user credential
        """
        if method == 'LOCAL':
            passw_hash = self.get_hashed_password(self.plain_text_password)
            apikey = db.session.execute(
                select(ApiKey).where(ApiKey.key == passw_hash.decode('utf-8'))
            ).scalar_one_or_none()

            if not apikey:
                raise Exception("Unauthorized")

            return apikey

    def associate_account(self, account):
        return True

    def dissociate_account(self, account):
        return True

    def get_accounts(self):
        return True
