import sys
import traceback
import pytimeparse
from ast import literal_eval
from flask import current_app, g
from sqlalchemy import select, delete
from .base import db
from powerdnsadmin.lib.settings import AppSettings


def _get_settings_cache():
    """Get or create the per-request settings cache on Flask g."""
    if not hasattr(g, '_settings_cache'):
        g._settings_cache = {}
    return g._settings_cache


def _invalidate_settings_cache(setting_name=None):
    """Invalidate the per-request settings cache (single key or all)."""
    if hasattr(g, '_settings_cache'):
        if setting_name:
            g._settings_cache.pop(setting_name, None)
        else:
            g._settings_cache.clear()


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, index=True)
    value = db.Column(db.Text())

    ZONE_TYPE_FORWARD = 'forward'
    ZONE_TYPE_REVERSE = 'reverse'

    def __init__(self, id=None, name=None, value=None):
        self.id = id
        self.name = name
        self.value = value

    # allow database autoincrement to do its own ID assignments
    def __init__(self, name=None, value=None):
        self.id = None
        self.name = name
        self.value = value

    def set_maintenance(self, mode):
        maintenance = db.session.execute(
            select(Setting).where(Setting.name == 'maintenance')
        ).scalar_one_or_none()

        if maintenance is None:
            value = AppSettings.defaults['maintenance']
            maintenance = Setting(name='maintenance', value=str(value))
            db.session.add(maintenance)

        mode = str(mode)

        try:
            if maintenance.value != mode:
                maintenance.value = mode
                db.session.commit()
            _invalidate_settings_cache('maintenance')
            return True
        except Exception as e:
            current_app.logger.error('Cannot set maintenance to {0}. DETAIL: {1}'.format(
                mode, e))
            current_app.logger.debug(traceback.format_exc())
            db.session.rollback()
            return False

    def toggle(self, setting):
        current_setting = db.session.execute(
            select(Setting).where(Setting.name == setting)
        ).scalar_one_or_none()

        if current_setting is None:
            value = AppSettings.defaults[setting]
            current_setting = Setting(name=setting, value=str(value))
            db.session.add(current_setting)

        try:
            if current_setting.value == "True":
                current_setting.value = "False"
            else:
                current_setting.value = "True"
            db.session.commit()
            _invalidate_settings_cache(setting)
            return True
        except Exception as e:
            current_app.logger.error('Cannot toggle setting {0}. DETAIL: {1}'.format(
                setting, e))
            current_app.logger.debug(traceback.format_exc())
            db.session.rollback()
            return False

    def set(self, setting, value):
        import json
        current_setting = db.session.execute(
            select(Setting).where(Setting.name == setting)
        ).scalar_one_or_none()

        if current_setting is None:
            current_setting = Setting(name=setting, value=None)
            db.session.add(current_setting)

        value = AppSettings.convert_type(setting, value)

        if isinstance(value, dict) or isinstance(value, list):
            value = json.dumps(value)

        try:
            current_setting.value = value
            db.session.commit()
            _invalidate_settings_cache(setting)
            return True
        except Exception as e:
            current_app.logger.error('Cannot edit setting {0}. DETAIL: {1}'.format(setting, e))
            current_app.logger.debug(traceback.format_exc())
            db.session.rollback()
            return False

    def get(self, setting):
        if setting not in AppSettings.defaults:
            current_app.logger.error('Unknown setting queried: {0}'.format(setting))
            return None

        # Check per-request cache first
        cache = _get_settings_cache()
        if setting in cache:
            return cache[setting]

        if setting.upper() in current_app.config:
            result = current_app.config[setting.upper()]
        else:
            result = db.session.execute(
                select(Setting).where(Setting.name == setting)
            ).scalar_one_or_none()

        if result is not None:
            if hasattr(result, 'value'):
                result = result.value
            value = AppSettings.convert_type(setting, result)
        else:
            value = AppSettings.defaults[setting]

        cache[setting] = value
        return value

    def get_group(self, group):
        if not isinstance(group, list):
            group = AppSettings.groups[group]

        result = {}

        for var_name, default_value in AppSettings.defaults.items():
            if var_name in group:
                result[var_name] = self.get(var_name)

        return result

    def get_records_allow_to_edit(self):
        return list(
            set(self.get_supported_record_types(self.ZONE_TYPE_FORWARD) +
                self.get_supported_record_types(self.ZONE_TYPE_REVERSE)))

    def get_supported_record_types(self, zone_type):
        setting_value = []

        if zone_type == self.ZONE_TYPE_FORWARD:
            setting_value = self.get('forward_records_allow_edit')
        elif zone_type == self.ZONE_TYPE_REVERSE:
            setting_value = self.get('reverse_records_allow_edit')

        records = literal_eval(setting_value) if isinstance(setting_value, str) else setting_value
        types = [r for r in records if records[r]]

        # Sort alphabetically if python version is smaller than 3.6
        if sys.version_info[0] < 3 or (sys.version_info[0] == 3 and sys.version_info[1] < 6):
            types.sort()

        return types

    def get_ttl_options(self):
        return [(pytimeparse.parse(ttl), ttl)
                for ttl in self.get('ttl_options').split(',')]
