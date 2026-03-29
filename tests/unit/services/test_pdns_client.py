"""Unit tests for PowerDNSClient service.

Tests HTTP interactions with mocked responses -- no live PowerDNS needed.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from powerdnsadmin.services.pdns_client import PowerDNSClient


@pytest.fixture
def client():
    """Create a PowerDNSClient with explicit config (no Flask app needed)."""
    return PowerDNSClient(
        api_url="http://pdns.test:8081",
        api_key="test-api-key",
        version="4.7.0",
        timeout=10,
        verify_ssl=False,
    )


class TestPowerDNSClientInit:
    def test_explicit_config(self, client):
        assert client.api_url == "http://pdns.test:8081"
        assert client.api_key == "test-api-key"
        assert client.timeout == 10
        assert client.verify_ssl is False

    def test_headers(self, client):
        headers = client._headers()
        assert headers["X-API-Key"] == "test-api-key"
        assert "Content-Type" not in headers

    def test_headers_with_content_type(self, client):
        headers = client._headers(content_type="application/json")
        assert headers["Content-Type"] == "application/json"


class TestZoneOperations:
    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_list_zones(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps([
            {"name": "example.com.", "kind": "Native", "serial": 1},
            {"name": "test.org.", "kind": "Master", "serial": 2},
        ]).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.list_zones()
        assert len(result) == 2
        assert result[0]["name"] == "example.com."

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "GET"
        assert "/servers/localhost/zones" in call_args[0][1]
        assert call_args[1]["headers"]["X-API-Key"] == "test-api-key"

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_get_zone(self, mock_request, client):
        zone_data = {
            "name": "example.com.",
            "kind": "Native",
            "rrsets": [{"name": "example.com.", "type": "SOA", "ttl": 3600}],
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps(zone_data).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.get_zone("example.com.")
        assert result["name"] == "example.com."
        assert "rrsets" in result

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_create_zone(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps(
            {"name": "new.com.", "kind": "Native"}
        ).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        result = client.create_zone(
            name="new.com",
            kind="Native",
            nameservers=["ns1.new.com"],
        )
        assert result["name"] == "new.com."

        # Verify request body
        call_args = mock_request.call_args
        sent_data = json.loads(call_args[1]["data"])
        assert sent_data["name"] == "new.com."
        assert sent_data["nameservers"] == ["ns1.new.com."]

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_create_zone_adds_trailing_dots(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps({"name": "new.com."}).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        client.create_zone(
            name="new.com",
            kind="Native",
            nameservers=["ns1.new.com", "ns2.new.com."],
        )

        call_args = mock_request.call_args
        sent_data = json.loads(call_args[1]["data"])
        assert sent_data["name"] == "new.com."
        assert sent_data["nameservers"] == ["ns1.new.com.", "ns2.new.com."]

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_delete_zone(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.delete_zone("example.com.")
        assert result is True

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_update_zone(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.update_zone("example.com.", {"kind": "Master"})
        assert result == {}

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_notify_zone(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps({"result": "Notification queued"}).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.notify_zone("example.com.")
        assert result["result"] == "Notification queued"

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_conflict_returns_error_dict(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.create_zone(name="existing.com", kind="Native")
        assert result["http_code"] == 409
        assert "error" in result


class TestRecordOperations:
    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_patch_zone_rrsets(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {"content-type": "application/json"}
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        rrsets_data = {
            "rrsets": [
                {
                    "name": "test.example.com.",
                    "type": "A",
                    "ttl": 3600,
                    "changetype": "REPLACE",
                    "records": [{"content": "1.2.3.4", "disabled": False}],
                }
            ]
        }
        result = client.patch_zone_rrsets("example.com.", rrsets_data)
        assert result == {}

        call_args = mock_request.call_args
        assert call_args[0][0] == "PATCH"


class TestDNSSECOperations:
    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_get_cryptokeys(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps([
            {"type": "Cryptokey", "id": 1, "keytype": "csk", "active": True}
        ]).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.get_cryptokeys("example.com.")
        assert len(result) == 1
        assert result[0]["keytype"] == "csk"

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_create_cryptokey(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps(
            {"type": "Cryptokey", "id": 1, "keytype": "ksk", "active": True}
        ).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_request.return_value = mock_response

        result = client.create_cryptokey("example.com.", keytype="ksk")
        assert result["keytype"] == "ksk"

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_delete_cryptokey(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.delete_cryptokey("example.com.", 1)
        assert result is True


class TestServerOperations:
    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_get_server_config(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps([
            {"name": "version", "type": "StatisticItem", "value": "4.7.0"}
        ]).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.get_server_config()
        assert result[0]["name"] == "version"

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_global_search(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = json.dumps([
            {"object_type": "record", "name": "test.example.com.", "type": "A"}
        ]).encode("utf-8")
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        result = client.global_search("test", object_type="record")
        assert len(result) == 1
        assert result[0]["object_type"] == "record"


class TestErrorHandling:
    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_server_error_raises_runtime(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")
        mock_request.return_value = mock_response

        with pytest.raises(RuntimeError, match="Error while fetching"):
            client.list_zones()

    @patch("powerdnsadmin.services.pdns_client.requests.request")
    def test_non_json_response_raises_runtime(self, mock_request, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.elapsed.total_seconds.return_value = 0.05
        mock_request.return_value = mock_response

        with pytest.raises(RuntimeError, match="Error while fetching"):
            client.list_zones()
