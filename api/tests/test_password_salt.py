"""Passwords are salted by us as well as by bcrypt (M5).

Stored per account in the users table: `password_salt` (16 random bytes, hex) and `password_hash`.
Combining: bcrypt( base64( SHA-256( salt_bytes || password_bytes ) ) ). Accounts made before this change have
no salt; they still log in (plain bcrypt) and are upgraded on that login.
"""
import bcrypt
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app import security
from conftest import DB_URL, HEADERS, login_body, register


def row(email="alice@example.com"):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("SELECT password_salt, password_hash FROM tutor.users WHERE email = %s", (email,))
        return cur.fetchone()


# --- the functions -----------------------------------------------------------------------------------

def test_a_salt_is_16_random_bytes_as_hex_and_never_repeats():
    a, b = security.new_salt(), security.new_salt()
    assert len(a) == 32 and bytes.fromhex(a) and a != b


def test_the_right_password_and_salt_verify():
    salt = security.new_salt()
    stored = security.hash_password("password123", salt, 4)
    assert security.verify_password("password123", stored, salt)


def test_a_wrong_password_or_wrong_salt_fails():
    salt = security.new_salt()
    stored = security.hash_password("password123", salt, 4)
    assert not security.verify_password("password124", stored, salt)
    assert not security.verify_password("password123", stored, security.new_salt())


def test_the_salt_really_is_part_of_what_is_hashed():
    """bcrypt on the bare password must NOT match: the stored hash is of the salted digest."""
    salt = security.new_salt()
    stored = security.hash_password("password123", salt, 4)
    assert not bcrypt.checkpw(b"password123", stored.encode())


def test_the_combination_is_exactly_sha256_of_salt_then_password_base64_then_bcrypt():
    import base64, hashlib
    salt = "00" * 16
    stored = security.hash_password("pw-longer-than-eight", salt, 4)
    digest = base64.b64encode(hashlib.sha256(bytes.fromhex(salt) + b"pw-longer-than-eight").digest())
    assert bcrypt.checkpw(digest, stored.encode())


def test_the_same_password_gives_different_hashes_for_different_salts():
    assert security.hash_password("password123", security.new_salt(), 4) != security.hash_password("password123", security.new_salt(), 4)


def test_a_password_past_72_bytes_is_not_silently_cut_short():
    salt = security.new_salt()
    stored = security.hash_password("a" * 80, salt, 4)
    assert not security.verify_password("a" * 72 + "b" * 8, stored, salt)


def test_a_legacy_hash_without_a_salt_still_verifies():
    legacy = bcrypt.hashpw(b"password123", bcrypt.gensalt(4)).decode()
    assert security.verify_password("password123", legacy, None)
    assert not security.verify_password("nope", legacy, None)


def test_a_malformed_stored_value_is_just_a_failure():
    assert not security.verify_password("x", "not-a-hash", security.new_salt())
    assert not security.verify_password("x", "not-a-hash", "zz")          # not hex


# --- the accounts ------------------------------------------------------------------------------------

def test_registering_stores_a_salt_beside_the_hash(client):
    register(client, "alice")
    salt, stored = row()
    assert salt and len(salt) == 32 and security.verify_password("password123", stored, salt)


def test_two_accounts_with_the_same_password_get_different_salts_and_hashes(make_user):
    make_user("alice"), make_user("bob")
    (sa, ha), (sb, hb) = row(), row("bob@example.com")
    assert sa != sb and ha != hb


def test_logging_in_works_and_a_wrong_password_does_not(client):
    register(client, "alice")
    other = TestClient(client.app, headers=HEADERS)
    assert other.post("/api/auth/login", json=login_body("alice", "wrong-password")).status_code == 401
    assert other.post("/api/auth/login", json=login_body("alice")).status_code == 200


def test_changing_the_password_makes_a_new_salt(client):
    register(client, "alice")
    old_salt, _ = row()
    r = client.post("/api/me/password", json={"current_password": "password123", "new_password": "new-password-9"})
    assert r.status_code == 204
    new_salt, stored = row()
    assert new_salt != old_salt and security.verify_password("new-password-9", stored, new_salt)
    other = TestClient(client.app, headers=HEADERS)
    assert other.post("/api/auth/login", json=login_body("alice", "new-password-9")).status_code == 200


def test_a_legacy_account_logs_in_and_is_upgraded(client):
    register(client, "alice")
    legacy = bcrypt.hashpw(b"password123", bcrypt.gensalt(4)).decode()
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("UPDATE tutor.users SET password_salt = NULL, password_hash = %s", (legacy,))
    other = TestClient(client.app, headers=HEADERS)
    assert other.post("/api/auth/login", json=login_body("alice", "wrong-password")).status_code == 401
    assert row()[0] is None                                                     # a failed login upgrades nothing
    assert other.post("/api/auth/login", json=login_body("alice")).status_code == 200
    salt, stored = row()
    assert salt and security.verify_password("password123", stored, salt)
    assert not bcrypt.checkpw(b"password123", stored.encode())


def test_the_salt_and_hash_are_never_in_the_export_or_the_profile(client):
    register(client, "alice")
    salt, stored = row()
    text = client.get("/api/me/export").text + client.get("/api/me").text
    assert salt not in text and stored not in text and "password_salt" not in text


def test_an_unknown_email_still_costs_one_salted_check(app):
    cred = app.state.dummy_credentials
    assert len(cred[0]) == 32 and cred[1].startswith("$2")
