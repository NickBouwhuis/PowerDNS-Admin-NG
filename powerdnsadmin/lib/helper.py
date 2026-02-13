from ..services.pdns_client import PowerDNSClient


def forward_request():
    """Forward the current Flask request to the PowerDNS API."""
    client = PowerDNSClient()
    return client.forward_request()
