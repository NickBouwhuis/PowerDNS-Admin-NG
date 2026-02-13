"""
Shared OAuth/SSO user provisioning service.

Consolidates the duplicated user-lookup, creation, and group-role
assignment logic used by Google, GitHub, Azure, and OIDC OAuth flows.
"""
from flask import current_app
from sqlalchemy import select

from ...models.base import db
from ...models.setting import Setting


class OAuthUserService:
    """Handles common OAuth user provisioning tasks."""

    def find_or_create_user(self, username, firstname, lastname, email,
                            fallback_email=True):
        """Look up a user by username (optionally email), create if missing.

        Args:
            username: Primary lookup key.
            firstname: First name for new user.
            lastname: Last name for new user.
            email: Email address for new user / fallback lookup.
            fallback_email: If True, also search by email when username
                            doesn't match.

        Returns:
            tuple: (user, created: bool, error: str or None)
                   *user* is the User object (existing or new).
                   *created* is True if a new DB row was inserted.
                   *error* is a message string on failure, else None.
        """
        from ...models.user import User

        user = db.session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if user is None and fallback_email and email:
            user = db.session.execute(
                select(User).where(User.email == email)
            ).scalar_one_or_none()

        if user:
            return user, False, None

        # Create new user
        user = User(
            username=username,
            plain_text_password=None,
            firstname=firstname,
            lastname=lastname,
            email=email,
        )
        result = user.create_local_user()
        if not result['status']:
            current_app.logger.warning(
                'Unable to create OAuth user "{0}": {1}'.format(
                    username, result['msg']))
            return None, False, result['msg']

        current_app.logger.info(
            'Created OAuth user "{0}" in the DB'.format(username))
        return user, True, None

    def update_user_profile(self, user, firstname, lastname, email):
        """Update an existing user's profile from SSO data.

        Args:
            user: The User model instance.
            firstname: New first name.
            lastname: New last name.
            email: New email.

        Returns:
            tuple: (success: bool, error: str or None)
        """
        user.firstname = firstname
        user.lastname = lastname
        user.email = email
        user.plain_text_password = None
        result = user.update_local_user()
        if not result['status']:
            return False, result['msg']
        return True, None

    @staticmethod
    def assign_role_from_groups(user, groups, admin_group, operator_group,
                                user_group):
        """Assign a role based on which security group the user belongs to.

        Args:
            user: The User model instance.
            groups: Iterable of group identifiers the user belongs to.
            admin_group: Group identifier for Administrator role.
            operator_group: Group identifier for Operator role.
            user_group: Group identifier for User role.

        Returns:
            tuple: (authorized: bool, role_name: str or None)
        """
        if admin_group and admin_group in groups:
            current_app.logger.info(
                'Setting role for user "{0}" to Administrator '
                'due to group membership'.format(user.username))
            user.set_role('Administrator')
            return True, 'Administrator'

        if operator_group and operator_group in groups:
            current_app.logger.info(
                'Setting role for user "{0}" to Operator '
                'due to group membership'.format(user.username))
            user.set_role('Operator')
            return True, 'Operator'

        if user_group and user_group in groups:
            current_app.logger.info(
                'Setting role for user "{0}" to User '
                'due to group membership'.format(user.username))
            user.set_role('User')
            return True, 'User'

        current_app.logger.warning(
            'User "{0}" has no relevant group memberships'.format(
                user.username))
        return False, None

    @staticmethod
    def parse_full_name(full_name):
        """Split a full name into (first, last).

        If the name has two or more words, the first word becomes the
        first name and the remaining words become the last name.

        Args:
            full_name: The full name string.

        Returns:
            tuple: (first_name, last_name)
        """
        if not full_name:
            return '', ''
        parts = full_name.split(' ')
        if len(parts) > 1:
            return parts[0], ' '.join(parts[1:])
        return full_name, ''
