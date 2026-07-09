"""Kraken credential resolution: real keys must be sourceable from the
environment so they never have to live in config.json (or the shipped zip),
while staying backward-compatible with a literal config value. Also: a
malformed secret must fail SAFE (disable private calls), not crash in _sign().
"""
import base64

from data.kraken_feed import KrakenFeed

VALID_SECRET = base64.b64encode(b"kraken-secret").decode()   # valid base64


def test_literal_config_value_is_the_legacy_fallback(monkeypatch):
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    f = KrakenFeed({"api_key": "ck", "api_secret": VALID_SECRET})
    assert f.api_key == "ck" and f.api_secret == VALID_SECRET


def test_conventional_env_overrides_config(monkeypatch):
    monkeypatch.setenv("KRAKEN_API_KEY", "envkey")
    monkeypatch.setenv("KRAKEN_API_SECRET", VALID_SECRET)
    f = KrakenFeed({"api_key": "should_be_ignored", "api_secret": "ignored"})
    assert f.api_key == "envkey" and f.api_secret == VALID_SECRET


def test_named_env_var_takes_precedence(monkeypatch):
    monkeypatch.setenv("MY_KRAKEN_KEY", "namedkey")
    monkeypatch.setenv("MY_KRAKEN_SECRET", VALID_SECRET)
    monkeypatch.setenv("KRAKEN_API_KEY", "conventional")   # lower precedence
    f = KrakenFeed({"api_key_env": "MY_KRAKEN_KEY",
                    "api_secret_env": "MY_KRAKEN_SECRET"})
    assert f.api_key == "namedkey" and f.api_secret == VALID_SECRET


def test_no_credentials_anywhere_resolves_empty(monkeypatch):
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    f = KrakenFeed({})
    assert f.api_key == "" and f.api_secret == ""


def test_malformed_secret_fails_safe_not_crash(monkeypatch):
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    # '!!!' is not valid base64; _sign() would crash on it -> must be disabled
    f = KrakenFeed({"api_key": "ck", "api_secret": "!!!not-base64!!!"})
    assert f.api_secret == ""
    # a private call with no usable secret is blocked, never signed
    assert f.get_account_balance() is None
