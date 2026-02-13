import traceback
from flask import current_app

from ..services.pdns_client import PowerDNSClient


class Server(object):
    """
    This is not a model, it's just an object
    which be assigned data from PowerDNS API
    """
    def __init__(self, server_id=None, server_config=None):
        self.server_id = server_id
        self.server_config = server_config

    def get_config(self):
        """
        Get server config
        """
        try:
            client = PowerDNSClient()
            return client.get_server_config(self.server_id)
        except Exception as e:
            current_app.logger.error(
                "Can not get server configuration. DETAIL: {0}".format(e))
            current_app.logger.debug(traceback.format_exc())
            return []

    def get_statistic(self):
        """
        Get server statistics
        """
        try:
            client = PowerDNSClient()
            return client.get_server_statistics(self.server_id)
        except Exception as e:
            current_app.logger.error(
                "Can not get server statistics. DETAIL: {0}".format(e))
            current_app.logger.debug(traceback.format_exc())
            return []

    def global_search(self, object_type='all', query=''):
        """
        Search zone/record/comment directly from PDNS API
        """
        try:
            client = PowerDNSClient()
            return client.global_search(query, object_type, self.server_id)
        except Exception as e:
            current_app.logger.error(
                "Can not make global search. DETAIL: {0}".format(e))
            current_app.logger.debug(traceback.format_exc())
            return []
