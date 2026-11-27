from pathlib import Path

import pytest
from pydantic import ValidationError

from ytmcp.config import DEFAULT_CONFIG_PATH, ConfigError, load_settings


@pytest.mark.unit
def test_default_file() -> None:
    assert DEFAULT_CONFIG_PATH.is_file()
    assert DEFAULT_CONFIG_PATH.name == "default.toml"
    assert DEFAULT_CONFIG_PATH.parent.name == "config"


@pytest.mark.unit
def test_default_values() -> None:
    settings = load_settings(env={})
    assert settings.quota.daily_budget == 10000
    assert settings.quota.safety_reserve_pct == 5
    assert settings.quota.machine_daily_budget == 2000
    assert settings.quota.reset_tz == "America/Los_Angeles"
    assert settings.quota.costs.search_list == 100
    assert settings.quota.costs.videos_list == 1
    assert settings.similarity.default_limit == 10
    assert settings.similarity.video.text == 0.50
    assert settings.similarity.channel.text == 0.55
    assert settings.taste.likes == 0.5
    assert settings.taste.mmr_lambda == 0.7
    assert settings.playlist.tolerance_pct == 5
    assert settings.playlist.default_visibility == "private"
    assert settings.cache.ttl_video_channel_h == 24
    assert settings.limits.rate_limit_per_min == 30
    assert settings.approval.mode == "auto"
    assert settings.provider == "fixture"
    assert settings.data_dir == Path.home() / ".local" / "share" / "ytmcp"


@pytest.mark.unit
def test_frozen() -> None:
    settings = load_settings(env={})
    with pytest.raises((ValidationError, TypeError)):
        settings.provider = "live"  # type: ignore[misc]
    with pytest.raises((ValidationError, TypeError)):
        settings.quota.daily_budget = 5000  # type: ignore[misc]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("env_key", "env_val", "accessor", "expected"),
    [
        (
            "YTMCP_QUOTA__MACHINE_DAILY_BUDGET",
            "500",
            lambda s: s.quota.machine_daily_budget,
            500,
        ),
        (
            "YTMCP_QUOTA__COSTS__SEARCH_LIST",
            "50",
            lambda s: s.quota.costs.search_list,
            50,
        ),
        (
            "YTMCP_TASTE__MMR_LAMBDA",
            "0.85",
            lambda s: s.taste.mmr_lambda,
            0.85,
        ),
        (
            "YTMCP_APPROVAL__MODE",
            "elicitation",
            lambda s: s.approval.mode,
            "elicitation",
        ),
        (
            "YTMCP_PLAYLIST__DEFAULT_VISIBILITY",
            "unlisted",
            lambda s: s.playlist.default_visibility,
            "unlisted",
        ),
        (
            "YTMCP_QUOTA__RESET_TZ",
            "UTC",
            lambda s: s.quota.reset_tz,
            "UTC",
        ),
    ],
)
def test_valid_overrides(env_key, env_val, accessor, expected) -> None:
    settings = load_settings(env={env_key: env_val})
    assert accessor(settings) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("env_dict", "should_check_var_name", "var_name"),
    [
        ({"YTMCP_QUOTA__NONEXISTENT": "1"}, True, "YTMCP_QUOTA__NONEXISTENT"),
        ({"YTMCP_NOSECTION__FOO": "1"}, True, "YTMCP_NOSECTION__FOO"),
        ({"YTMCP_QUOTA__COSTS": "1"}, True, "YTMCP_QUOTA__COSTS"),
        (
            {"YTMCP_QUOTA__DAILY_BUDGET__DEEP": "1"},
            True,
            "YTMCP_QUOTA__DAILY_BUDGET__DEEP",
        ),
        ({"YTMCP_QUOTA____BUDGET": "1"}, True, "YTMCP_QUOTA____BUDGET"),
        (
            {"YTMCP_QUOTA__DAILY_BUDGET": "not-an-int"},
            True,
            "YTMCP_QUOTA__DAILY_BUDGET",
        ),
        ({"YTMCP_QUOTA__SAFETY_RESERVE_PCT": "99"}, False, ""),
        ({"YTMCP_APPROVAL__MODE": "yolo"}, False, ""),
        ({"YTMCP_QUOTA__RESET_TZ": "Atlantis/City"}, False, ""),
    ],
)
def test_invalid_overrides(env_dict, should_check_var_name, var_name) -> None:
    with pytest.raises(ConfigError) as exc_info:
        load_settings(env=env_dict)
    if should_check_var_name:
        assert var_name in str(exc_info.value)


@pytest.mark.unit
def test_ignored_variables() -> None:
    env = {
        "YTMCP_TOKEN_PASSPHRASE": "secret",
        "YTMCP_PROVIDERX": "val",
        "HOME": "/tmp",
        "PATH": "/usr/bin",
    }
    assert load_settings(env=env) == load_settings(env={})


@pytest.mark.unit
def test_provider_and_data_dir() -> None:
    s1 = load_settings(env={"YTMCP_PROVIDER": "live"})
    assert s1.provider == "live"

    with pytest.raises(ConfigError):
        load_settings(env={"YTMCP_PROVIDER": "bogus"})

    s2 = load_settings(env={"YTMCP_DATA_DIR": "/var/tmp/ytmcp"})
    assert s2.data_dir == Path("/var/tmp/ytmcp")

    s3 = load_settings(env={"YTMCP_DATA_DIR": "~/custom_ytmcp"})
    assert s3.data_dir == Path.home() / "custom_ytmcp"

    s4 = load_settings(env={"YTMCP_DATA_DIR": ""})
    assert s4.data_dir == Path.home() / ".local" / "share" / "ytmcp"


@pytest.mark.unit
def test_file_variants(tmp_path: Path) -> None:
    valid_toml = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8")

    # (a) unknown key in TOML file
    f_a = tmp_path / "unknown_key.toml"
    bad_key_toml = valid_toml.replace("[quota]\n", "[quota]\nunknown_key = 123\n")
    f_a.write_text(bad_key_toml, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(path=f_a, env={})

    # (b) sum of similarity.video weights not equal to 1.0 (e.g. 0.9)
    f_b = tmp_path / "bad_weights.toml"
    bad_weights_toml = valid_toml.replace("text = 0.50", "text = 0.40")
    f_b.write_text(bad_weights_toml, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(path=f_b, env={})

    # (c) invalid timezone
    f_c = tmp_path / "bad_tz.toml"
    bad_tz_toml = valid_toml.replace('"America/Los_Angeles"', '"Atlantis/City"')
    f_c.write_text(bad_tz_toml, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(path=f_c, env={})

    # (d) missing section (e.g. no [approval])
    f_d = tmp_path / "missing_section.toml"
    missing_sec_toml = valid_toml.split("[approval]")[0]
    f_d.write_text(missing_sec_toml, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(path=f_d, env={})

    # (e) invalid TOML syntax
    f_e = tmp_path / "invalid_syntax.toml"
    f_e.write_text("invalid = [toml", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_settings(path=f_e, env={})

    # (f) nonexistent path
    f_f = tmp_path / "nonexistent.toml"
    with pytest.raises(ConfigError):
        load_settings(path=f_f, env={})


@pytest.mark.unit
def test_os_environ_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YTMCP_APPROVAL__MODE", "elicitation")
    settings = load_settings()
    assert settings.approval.mode == "elicitation"


@pytest.mark.unit
def test_config_error_type() -> None:
    assert issubclass(ConfigError, ValueError)
