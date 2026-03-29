"""Password policy validation.

Framework-agnostic password policy checker used by both the registration
and profile-update routes.
"""
import string

from zxcvbn import zxcvbn


def password_policy_check(user, password):
    """Validate *password* against configurable policy rules.

    Args:
        user: An object with ``username``, ``firstname``, ``lastname``,
              and ``email`` attributes.
        password: The plain-text password to validate.

    Returns:
        A tuple ``(passed: bool, detail: dict)`` where *detail* has a
        ``"password"`` key describing which rules failed.
    """
    from powerdnsadmin.models.setting import Setting

    def check_policy(chars, user_password, setting):
        setting_as_int = int(Setting().get(setting))
        test_string = user_password
        for c in chars:
            test_string = test_string.replace(c, '')
        return (setting_as_int, len(user_password) - len(test_string))

    def matches_policy(item, policy_fails):
        return "*" if item in policy_fails else ""

    policy = []
    policy_fails = {}

    if Setting().get('pwd_enforce_characters') or Setting().get('pwd_enforce_complexity'):
        if user.username in password:
            policy_fails["username"] = True
        policy.append(f"{matches_policy('username', policy_fails)}cannot contain username")

        if user.firstname in password:
            policy_fails["firstname"] = True
        policy.append(f"{matches_policy('firstname', policy_fails)}cannot contain firstname")

        if user.lastname in password:
            policy_fails["lastname"] = True
        policy.append(f"{matches_policy('lastname', policy_fails)}cannot contain lastname")

        if user.email in password:
            policy_fails["email"] = True
        policy.append(f"{matches_policy('email', policy_fails)}cannot contain email")

    if Setting().get('pwd_enforce_characters'):
        pwd_min_len_setting = int(Setting().get('pwd_min_len'))
        pwd_len = len(password)
        if pwd_len < pwd_min_len_setting:
            policy_fails["length"] = True
        policy.append(f"{matches_policy('length', policy_fails)}length={pwd_len}/{pwd_min_len_setting}")

        (pwd_min_digits_setting, pwd_digits) = check_policy(string.digits, password, 'pwd_min_digits')
        if pwd_digits < pwd_min_digits_setting:
            policy_fails["digits"] = True
        policy.append(f"{matches_policy('digits', policy_fails)}digits={pwd_digits}/{pwd_min_digits_setting}")

        (pwd_min_lowercase_setting, pwd_lowercase) = check_policy(string.ascii_lowercase, password, 'pwd_min_lowercase')
        if pwd_lowercase < pwd_min_lowercase_setting:
            policy_fails["lowercase"] = True
        policy.append(
            f"{matches_policy('lowercase', policy_fails)}lowercase={pwd_lowercase}/{pwd_min_lowercase_setting}")

        (pwd_min_uppercase_setting, pwd_uppercase) = check_policy(string.ascii_uppercase, password, 'pwd_min_uppercase')
        if pwd_uppercase < pwd_min_uppercase_setting:
            policy_fails["uppercase"] = True
        policy.append(
            f"{matches_policy('uppercase', policy_fails)}uppercase={pwd_uppercase}/{pwd_min_uppercase_setting}")

        pwd_min_special_setting = int(Setting().get('pwd_min_special'))
        pwd_special = sum(1 for c in password if not c.isalnum())
        if pwd_special < pwd_min_special_setting:
            policy_fails["special"] = True
        policy.append(f"{matches_policy('special', policy_fails)}special={pwd_special}/{pwd_min_special_setting}")

    if Setting().get('pwd_enforce_complexity'):
        zxcvbn_inputs = []
        for inp in (user.firstname, user.lastname, user.username, user.email):
            if len(inp):
                zxcvbn_inputs.append(inp)

        result = zxcvbn(password, user_inputs=zxcvbn_inputs)
        pwd_min_complexity_setting = int(Setting().get('pwd_min_complexity'))
        pwd_complexity = result['guesses_log10']
        if pwd_complexity < pwd_min_complexity_setting:
            policy_fails["complexity"] = True
        policy.append(
            f"{matches_policy('complexity', policy_fails)}complexity={pwd_complexity:.0f}/{pwd_min_complexity_setting}")

    policy_str = {"password": f"Fails policy: {', '.join(policy)}. Items prefixed with '*' failed."}

    return (not any(policy_fails.values()), policy_str)
