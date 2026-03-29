"""
PowerDNS API client service.

Centralizes all HTTP communication with the PowerDNS Authoritative Server API.
Models should use this service instead of making direct HTTP calls.
"""
import json
import logging
import traceback
import urllib.parse

import requests
from urllib.parse import urljoin

from ..models.setting import Setting
from ..lib.utils import pdns_api_extended_uri

logger = logging.getLogger(__name__)


class PowerDNSClient:
    """Client for the PowerDNS Authoritative Server API."""

    def __init__(self, api_url=None, api_key=None, version=None,
                 timeout=None, verify_ssl=None):
        """
        Initialize with explicit values or fall back to Settings.

        Args:
            api_url: PowerDNS API base URL
            api_key: PowerDNS API key
            version: PowerDNS server version string
            timeout: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        setting = Setting()
        self.api_url = api_url or setting.get('pdns_api_url')
        self.api_key = api_key or setting.get('pdns_api_key')
        self.version = version or setting.get('pdns_version')
        self.timeout = timeout or int(setting.get('pdns_api_timeout'))
        self.verify_ssl = verify_ssl if verify_ssl is not None else setting.get('verify_ssl_connections')
        self.api_extended_url = pdns_api_extended_uri(self.version)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _headers(self, content_type=None):
        """Build standard headers for PowerDNS API requests."""
        headers = {
            'X-API-Key': self.api_key,
            'user-agent': 'powerdns-admin/api',
            'pragma': 'no-cache',
            'cache-control': 'no-cache',
            'accept': 'application/json; q=1',
        }
        if content_type:
            headers['Content-Type'] = content_type
        return headers

    def _url(self, path):
        """Build full URL for a PowerDNS API endpoint path."""
        base = self.api_url
        if base and '://' not in base:
            base = 'http://' + base
        return urljoin(base, self.api_extended_url + path)

    def _request(self, method, path, data=None):
        """
        Make an HTTP request to the PowerDNS API.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            path: API path (e.g., '/servers/localhost/zones')
            data: Optional dict to send as JSON body

        Returns:
            Parsed JSON response, True for DELETE/204, or raises RuntimeError.
        """
        url = self._url(path)
        headers = self._headers(
            content_type='application/json' if data is not None else None
        )

        body = json.dumps(data) if data is not None else None

        logger.debug("PowerDNS API %s %s", method, url)

        r = requests.request(
            method,
            url,
            headers=headers,
            verify=bool(self.verify_ssl),
            timeout=self.timeout,
            data=body,
        )

        logger.debug(
            "PowerDNS API %s %s -> %d (%.3fs)",
            method, url, r.status_code, r.elapsed.total_seconds()
        )

        if r.status_code not in (200, 201, 204, 400, 409, 422):
            try:
                r.raise_for_status()
            except Exception:
                msg = "Returned status {} and content {}".format(
                    r.status_code, r.text)
                raise RuntimeError(
                    'Error while fetching {}. {}'.format(url, msg))

        if method == 'DELETE':
            return True

        if r.status_code == 204:
            return {}

        if r.status_code == 409:
            return {
                'error': 'Resource already exists or conflict',
                'http_code': r.status_code
            }

        try:
            assert 'json' in r.headers.get('content-type', '')
        except (AssertionError, KeyError):
            raise RuntimeError('Error while fetching {}'.format(url))

        try:
            return json.loads(r.content.decode('utf-8'))
        except UnicodeDecodeError:
            logger.warning("UTF-8 decode failed, falling back to .json()")
            return r.json()
        except Exception:
            raise RuntimeError(
                'Error while loading JSON from {}'.format(url))

    # ── Zone Operations ──────────────────────────────────────────────────

    def list_zones(self):
        """
        List all zones on the PowerDNS server.

        Returns:
            list: Zone data dicts from PowerDNS API
        """
        return self._request('GET', '/servers/localhost/zones')

    def get_zone(self, zone_name):
        """
        Get detailed zone information including rrsets.

        Args:
            zone_name: The zone name (with or without trailing dot)

        Returns:
            dict: Zone data from PowerDNS API
        """
        return self._request(
            'GET',
            '/servers/localhost/zones/{}'.format(zone_name)
        )

    def create_zone(self, name, kind, nameservers=None, masters=None,
                    soa_edit_api='DEFAULT', account=None):
        """
        Create a new zone in PowerDNS.

        Args:
            name: Zone name (trailing dot will be added if missing)
            kind: Zone type (Native, Master, Slave)
            nameservers: List of nameserver hostnames
            masters: List of master IP addresses (for Slave zones)
            soa_edit_api: SOA-EDIT-API setting
            account: Account name to associate

        Returns:
            dict: Created zone data or error dict
        """
        if not name.endswith('.'):
            name += '.'
        if nameservers:
            nameservers = [ns + '.' if not ns.endswith('.') else ns
                           for ns in nameservers]

        if soa_edit_api not in ('DEFAULT', 'INCREASE', 'EPOCH', 'OFF'):
            soa_edit_api = 'DEFAULT'
        elif soa_edit_api == 'OFF':
            soa_edit_api = ''

        post_data = {
            'name': name,
            'kind': kind,
            'masters': masters or [],
            'nameservers': nameservers or [],
            'soa_edit_api': soa_edit_api,
            'account': account,
        }

        return self._request('POST', '/servers/localhost/zones', data=post_data)

    def delete_zone(self, zone_name):
        """
        Delete a zone from PowerDNS.

        Args:
            zone_name: The zone name

        Returns:
            True on success
        """
        return self._request(
            'DELETE',
            '/servers/localhost/zones/{}'.format(zone_name)
        )

    def update_zone(self, zone_name, data):
        """
        Update zone metadata (kind, masters, soa_edit_api, account, etc.).

        Args:
            zone_name: The zone name
            data: Dict of fields to update

        Returns:
            dict: Response from PowerDNS API
        """
        return self._request(
            'PUT',
            '/servers/localhost/zones/{}'.format(zone_name),
            data=data,
        )

    def notify_zone(self, zone_name):
        """
        Send a DNS NOTIFY to all slaves for this zone.

        Args:
            zone_name: The zone name

        Returns:
            dict: Response from PowerDNS API
        """
        return self._request(
            'PUT',
            '/servers/localhost/zones/{}/notify'.format(zone_name)
        )

    def axfr_retrieve(self, zone_name):
        """
        Trigger an AXFR retrieval for a slave zone.

        Args:
            zone_name: The zone name

        Returns:
            dict: Response with 'result' key
        """
        encoded_name = urllib.parse.quote_plus(zone_name)
        return self._request(
            'PUT',
            '/servers/localhost/zones/{}/axfr-retrieve'.format(encoded_name)
        )

    # ── Record Operations ────────────────────────────────────────────────

    def get_zone_rrsets(self, zone_name):
        """
        Get all rrsets for a zone (same as get_zone but focuses on rrsets).

        Args:
            zone_name: The zone name

        Returns:
            dict: Full zone data including 'rrsets' key
        """
        return self.get_zone(zone_name)

    def patch_zone_rrsets(self, zone_name, rrsets_data):
        """
        Modify rrsets (add/replace/delete records) in a zone.

        Args:
            zone_name: The zone name
            rrsets_data: Dict with 'rrsets' key containing changetype entries

        Returns:
            dict: Response from PowerDNS API (empty on success)
        """
        return self._request(
            'PATCH',
            '/servers/localhost/zones/{}'.format(zone_name),
            data=rrsets_data,
        )

    # ── DNSSEC Operations ────────────────────────────────────────────────

    def get_cryptokeys(self, zone_name):
        """
        Get DNSSEC cryptokeys for a zone.

        Args:
            zone_name: The zone name

        Returns:
            list: Cryptokey data dicts
        """
        encoded_name = urllib.parse.quote_plus(zone_name)
        return self._request(
            'GET',
            '/servers/localhost/zones/{}/cryptokeys'.format(encoded_name)
        )

    def create_cryptokey(self, zone_name, keytype='ksk', active=True):
        """
        Create a new DNSSEC cryptokey for a zone.

        Args:
            zone_name: The zone name
            keytype: Key type ('ksk', 'zsk', 'csk')
            active: Whether the key should be active

        Returns:
            dict: Created key data
        """
        encoded_name = urllib.parse.quote_plus(zone_name)
        return self._request(
            'POST',
            '/servers/localhost/zones/{}/cryptokeys'.format(encoded_name),
            data={'keytype': keytype, 'active': active},
        )

    def delete_cryptokey(self, zone_name, key_id):
        """
        Delete a DNSSEC cryptokey.

        Args:
            zone_name: The zone name
            key_id: The key ID to delete

        Returns:
            True on success
        """
        encoded_name = urllib.parse.quote_plus(zone_name)
        return self._request(
            'DELETE',
            '/servers/localhost/zones/{}/cryptokeys/{}'.format(
                encoded_name, key_id)
        )

    # ── Server Operations ────────────────────────────────────────────────

    def get_server_config(self, server_id='localhost'):
        """
        Get PowerDNS server configuration.

        Args:
            server_id: Server identifier (default: 'localhost')

        Returns:
            list: Configuration items
        """
        return self._request(
            'GET',
            '/servers/{}/config'.format(server_id)
        )

    def get_server_statistics(self, server_id='localhost'):
        """
        Get PowerDNS server statistics.

        Args:
            server_id: Server identifier (default: 'localhost')

        Returns:
            list: Statistics items
        """
        return self._request(
            'GET',
            '/servers/{}/statistics'.format(server_id)
        )

    def global_search(self, query, object_type='all', server_id='localhost'):
        """
        Search zones/records/comments via PowerDNS API.

        Args:
            query: Search query string
            object_type: Type to search ('all', 'zone', 'record', 'comment')
            server_id: Server identifier (default: 'localhost')

        Returns:
            list: Search result items
        """
        return self._request(
            'GET',
            '/servers/{}/search-data?object_type={}&q={}'.format(
                server_id, object_type, query)
        )

    # ── Pass-through Proxy ───────────────────────────────────────────────

    def forward_request(self, method, full_path, json_body=None):
        """
        Forward a request to the PowerDNS API.
        Used for API pass-through endpoints.

        Args:
            method: HTTP method (GET, POST, PUT, PATCH, DELETE)
            full_path: Full URL path including query string
            json_body: Optional parsed JSON body (for POST/PUT/PATCH)

        Returns:
            requests.Response: Raw response from PowerDNS
        """
        headers = self._headers()
        data = None

        if method not in ('GET', 'DELETE') and json_body is not None:
            data = json_body
            logger.debug("Forwarding request to PowerDNS API: %s", data)

        url = urljoin(self.api_url, full_path)

        return requests.request(
            method,
            url,
            headers=headers,
            verify=bool(self.verify_ssl),
            json=data,
        )
