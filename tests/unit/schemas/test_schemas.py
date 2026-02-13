"""Unit tests for Pydantic schemas.

These tests validate request/response schemas without any Flask or DB dependencies.
"""
import pytest
from pydantic import ValidationError

from powerdnsadmin.schemas.zone import ZoneCreate, ZoneSummary, ZoneDetail
from powerdnsadmin.schemas.user import UserCreate, UserUpdate, UserSummary, UserDetailed
from powerdnsadmin.schemas.account import AccountCreate, AccountUpdate, AccountSummary, AccountDetail
from powerdnsadmin.schemas.api_key import ApiKeyCreate, ApiKeyDetail, ApiKeyPlain
from powerdnsadmin.schemas.record import RRSet, RRSetUpdate, RecordItem
from powerdnsadmin.schemas.setting import SettingUpdate, SettingValue
from powerdnsadmin.schemas.auth import LoginRequest
from powerdnsadmin.schemas.role import RoleSchema


class TestZoneSchemas:
    def test_zone_create_minimal(self):
        z = ZoneCreate(name="example.com")
        assert z.name == "example.com"
        assert z.kind == "Native"
        assert z.nameservers == []
        assert z.masters == []
        assert z.soa_edit_api == "DEFAULT"

    def test_zone_create_full(self):
        z = ZoneCreate(
            name="example.com",
            kind="Master",
            nameservers=["ns1.example.com", "ns2.example.com"],
            masters=[],
            soa_edit_api="INCREASE",
            account="myaccount",
        )
        assert z.kind == "Master"
        assert len(z.nameservers) == 2
        assert z.account == "myaccount"

    def test_zone_create_invalid_kind(self):
        with pytest.raises(ValidationError, match="kind must be one of"):
            ZoneCreate(name="example.com", kind="INVALID")

    def test_zone_create_invalid_soa_edit_api(self):
        with pytest.raises(ValidationError, match="soa_edit_api must be one of"):
            ZoneCreate(name="example.com", soa_edit_api="BADVALUE")

    def test_zone_summary_from_attributes(self):
        class FakeDomain:
            id = 1
            name = "example.com"

        z = ZoneSummary.model_validate(FakeDomain())
        assert z.id == 1
        assert z.name == "example.com"

    def test_zone_detail(self):
        z = ZoneDetail(
            name="example.com.",
            kind="Native",
            dnssec=True,
            serial=2024010101,
            rrsets=[{"name": "example.com.", "type": "SOA", "ttl": 3600, "records": []}],
        )
        assert z.dnssec is True
        assert z.serial == 2024010101
        assert len(z.rrsets) == 1


class TestUserSchemas:
    def test_user_create_minimal(self):
        u = UserCreate(username="testuser")
        assert u.username == "testuser"
        assert u.confirmed is False
        assert u.role_name is None

    def test_user_create_full(self):
        u = UserCreate(
            username="admin",
            plain_text_password="secret123",
            firstname="Admin",
            lastname="User",
            email="admin@example.com",
            role_name="Administrator",
        )
        assert u.plain_text_password == "secret123"
        assert u.role_name == "Administrator"

    def test_user_update_partial(self):
        u = UserUpdate(email="new@example.com")
        assert u.email == "new@example.com"
        assert u.username is None

    def test_user_summary_from_attributes(self):
        class FakeRole:
            id = 1
            name = "Administrator"

        class FakeUser:
            id = 1
            username = "admin"
            firstname = "Admin"
            lastname = "User"
            email = "admin@example.com"
            role = FakeRole()

        u = UserSummary.model_validate(FakeUser())
        assert u.username == "admin"
        assert u.role.name == "Administrator"

    def test_user_detailed(self):
        u = UserDetailed(
            id=1,
            username="admin",
            role={"id": 1, "name": "Administrator"},
            accounts=[{"id": 1, "name": "acct1", "domains": []}],
        )
        assert len(u.accounts) == 1
        assert u.accounts[0].name == "acct1"


class TestAccountSchemas:
    def test_account_create(self):
        a = AccountCreate(name="myaccount", description="Test account")
        assert a.name == "myaccount"
        assert a.contact is None

    def test_account_update_partial(self):
        a = AccountUpdate(description="Updated description")
        assert a.description == "Updated description"
        assert a.name is None

    def test_account_detail_from_attributes(self):
        a = AccountDetail(
            id=1,
            name="prod",
            description="Production",
            domains=[{"id": 1, "name": "example.com"}],
            apikeys=[{"id": 1, "description": "key1"}],
        )
        assert len(a.domains) == 1
        assert len(a.apikeys) == 1


class TestApiKeySchemas:
    def test_apikey_create_with_role_string(self):
        k = ApiKeyCreate(role="Administrator", description="admin key")
        assert k.role == "Administrator"

    def test_apikey_create_with_role_dict(self):
        k = ApiKeyCreate(role={"name": "User"}, domains=["example.com"])
        assert k.role == {"name": "User"}

    def test_apikey_detail(self):
        k = ApiKeyDetail(
            id=1,
            role={"id": 1, "name": "Administrator"},
            domains=[],
            accounts=[],
            description="test key",
            key="hashed_value",
        )
        assert k.key == "hashed_value"

    def test_apikey_plain(self):
        k = ApiKeyPlain(
            id=1,
            role={"id": 1, "name": "User"},
            domains=[{"id": 1, "name": "example.com"}],
            accounts=[],
            plain_key="base64encodedkey",
        )
        assert k.plain_key == "base64encodedkey"
        assert len(k.domains) == 1


class TestRecordSchemas:
    def test_record_item(self):
        r = RecordItem(content="1.2.3.4")
        assert r.disabled is False
        assert r.set_ptr is False

    def test_rrset_replace(self):
        rr = RRSet(
            name="test.example.com.",
            type="A",
            ttl=3600,
            changetype="REPLACE",
            records=[RecordItem(content="1.2.3.4")],
        )
        assert rr.changetype == "REPLACE"
        assert len(rr.records) == 1

    def test_rrset_delete(self):
        rr = RRSet(name="old.example.com.", type="CNAME", changetype="DELETE")
        assert rr.changetype == "DELETE"
        assert rr.records == []

    def test_rrset_invalid_changetype(self):
        with pytest.raises(ValidationError, match="changetype must be one of"):
            RRSet(name="x", type="A", changetype="BADCHANGE")

    def test_rrset_changetype_case_insensitive(self):
        rr = RRSet(name="x", type="A", changetype="replace")
        assert rr.changetype == "REPLACE"

    def test_rrset_update(self):
        update = RRSetUpdate(
            rrsets=[
                {
                    "name": "test.example.com.",
                    "type": "A",
                    "ttl": 3600,
                    "changetype": "REPLACE",
                    "records": [{"content": "1.2.3.4"}, {"content": "5.6.7.8"}],
                },
                {
                    "name": "old.example.com.",
                    "type": "CNAME",
                    "changetype": "DELETE",
                },
            ]
        )
        assert len(update.rrsets) == 2
        assert len(update.rrsets[0].records) == 2


class TestSettingSchemas:
    def test_setting_value(self):
        s = SettingValue(name="site_name", value="My DNS Admin")
        assert s.name == "site_name"
        assert s.value == "My DNS Admin"

    def test_setting_value_bool(self):
        s = SettingValue(name="maintenance", value=False)
        assert s.value is False

    def test_setting_update(self):
        s = SettingUpdate(value=True)
        assert s.value is True


class TestAuthSchemas:
    def test_login_request_minimal(self):
        r = LoginRequest(username="admin", password="secret")
        assert r.auth_method == "LOCAL"
        assert r.otp_token is None

    def test_login_request_with_otp(self):
        r = LoginRequest(
            username="admin",
            password="secret",
            otp_token="123456",
            auth_method="LDAP",
        )
        assert r.otp_token == "123456"
        assert r.auth_method == "LDAP"


class TestRoleSchema:
    def test_role_from_attributes(self):
        class FakeRole:
            id = 2
            name = "Operator"

        r = RoleSchema.model_validate(FakeRole())
        assert r.id == 2
        assert r.name == "Operator"
