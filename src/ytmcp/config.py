"""Configuration models and loader for YouTube Video Intelligence MCP Server."""

import os
import tomllib
import zoneinfo
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ConfigError(ValueError):
    """Raised when configuration loading or validation fails."""


class QuotaCosts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    search_list: int = Field(ge=0)
    videos_list: int = Field(ge=0)
    channels_list: int = Field(ge=0)
    subscriptions_list: int = Field(ge=0)
    playlists_list: int = Field(ge=0)
    playlist_items_list: int = Field(ge=0)
    video_categories_list: int = Field(ge=0)
    playlists_insert: int = Field(ge=0)
    playlist_items_insert: int = Field(ge=0)


class QuotaConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    daily_budget: int = Field(gt=0)
    safety_reserve_pct: int = Field(ge=0, le=50)
    machine_daily_budget: int = Field(gt=0)
    reset_tz: str
    costs: QuotaCosts

    @model_validator(mode="after")
    def validate_tz(self) -> "QuotaConfig":
        try:
            zoneinfo.ZoneInfo(self.reset_tz)
        except Exception as exc:
            raise ValueError(f"Invalid IANA timezone '{self.reset_tz}'") from exc
        return self


class VideoWeights(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: float = Field(ge=0.0)
    tag: float = Field(ge=0.0)
    category: float = Field(ge=0.0)
    duration: float = Field(ge=0.0)
    language: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "VideoWeights":
        total = self.text + self.tag + self.category + self.duration + self.language
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Video weights must sum to 1.0, got {total}")
        return self


class ChannelWeights(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: float = Field(ge=0.0)
    topic: float = Field(ge=0.0)
    cadence: float = Field(ge=0.0)
    size: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "ChannelWeights":
        total = self.text + self.topic + self.cadence + self.size
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Channel weights must sum to 1.0, got {total}")
        return self


class SimilarityConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    default_limit: int = Field(ge=1)
    max_limit: int = Field(ge=1)
    channel_default_limit: int = Field(ge=1)
    channel_max_limit: int = Field(ge=1)
    default_candidates: int = Field(ge=1)
    max_candidates: int = Field(ge=1)
    fr1_search_queries: int = Field(ge=1)
    channel_recent_uploads: int = Field(ge=1)
    field_weight_title: int = Field(ge=1)
    field_weight_tags: int = Field(ge=1)
    field_weight_description: int = Field(ge=1)
    video: VideoWeights
    channel: ChannelWeights

    @model_validator(mode="after")
    def validate_limits(self) -> "SimilarityConfig":
        if self.max_limit < self.default_limit:
            raise ValueError("max_limit must be at least default_limit")
        if self.channel_max_limit < self.channel_default_limit:
            raise ValueError("channel_max_limit must be at least channel_default_limit")
        if self.max_candidates < self.default_candidates:
            raise ValueError("max_candidates must be at least default_candidates")
        return self


class TasteConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    likes: float = Field(ge=0.0)
    playlists: float = Field(ge=0.0)
    subscriptions: float = Field(ge=0.0)
    half_life_days: int = Field(ge=1)
    source_cap: int = Field(ge=1)
    per_channel_top10: int = Field(ge=1)
    mmr_lambda: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_sum(self) -> "TasteConfig":
        total = self.likes + self.playlists + self.subscriptions
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Taste weights must sum to 1.0, got {total}")
        return self


class PlaylistConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tolerance_pct: int = Field(ge=0, le=50)
    per_channel_cap: int = Field(ge=1)
    dp_unit_s: int = Field(ge=1)
    dp_top_n: int = Field(ge=1)
    search_queries: int = Field(ge=1)
    min_total_s: int = Field(ge=1)
    max_total_s: int = Field(ge=1)
    min_item_s: int = Field(ge=1)
    topic_max_len: int = Field(ge=1)
    title_max_len: int = Field(ge=1)
    proposal_ttl_min: int = Field(ge=1)
    default_visibility: Literal["private", "unlisted", "public"] = "private"

    @model_validator(mode="after")
    def validate_totals(self) -> "PlaylistConfig":
        if self.max_total_s < self.min_total_s:
            raise ValueError("max_total_s must be at least min_total_s")
        return self


class CacheConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ttl_video_channel_h: int = Field(ge=1)
    ttl_search_h: int = Field(ge=1)
    ttl_categories_d: int = Field(ge=1)


class LimitsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rate_limit_per_min: int = Field(ge=1)
    max_input_len: int = Field(ge=1)
    retry_max: int = Field(ge=0)
    http_timeout_s: int = Field(ge=1)


class ApprovalConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: Literal["auto", "elicitation", "oob"] = "auto"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    quota: QuotaConfig
    similarity: SimilarityConfig
    taste: TasteConfig
    playlist: PlaylistConfig
    cache: CacheConfig
    limits: LimitsConfig
    approval: ApprovalConfig
    provider: Literal["fixture", "live", "recording"] = "fixture"
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".local" / "share" / "ytmcp")


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default.toml"


def _coerce_value(target: Any, raw_value: str, var_name: str) -> Any:
    if isinstance(target, bool):
        return raw_value.lower() in ("true", "1", "yes")
    if isinstance(target, int):
        try:
            return int(raw_value)
        except ValueError as exc:
            raise ConfigError(f"Invalid integer value for '{var_name}': {raw_value}") from exc
    if isinstance(target, float):
        try:
            return float(raw_value)
        except ValueError as exc:
            raise ConfigError(f"Invalid float value for '{var_name}': {raw_value}") from exc
    return raw_value


def _resolve_target_container(
    data: dict[str, Any], segments: list[str], var_name: str
) -> tuple[dict[str, Any], str]:
    curr: Any = data
    for seg in segments[:-1]:
        if not isinstance(curr, dict):
            raise ConfigError(f"Environment variable '{var_name}' continues below a value")
        if seg not in curr:
            raise ConfigError(
                f"Unknown section or key '{seg}' in environment variable '{var_name}'"
            )
        curr = curr[seg]

    if not isinstance(curr, dict):
        raise ConfigError(f"Environment variable '{var_name}' continues below a value")

    leaf_key = segments[-1]
    if leaf_key not in curr:
        raise ConfigError(f"Unknown key '{leaf_key}' in environment variable '{var_name}'")
    if isinstance(curr[leaf_key], dict):
        raise ConfigError(f"Environment variable '{var_name}' targets a section/table, not a value")
    return curr, leaf_key


def _apply_override(data: dict[str, Any], var_name: str, raw_value: str) -> None:
    key_path_str = var_name[len("YTMCP_") :]
    segments = key_path_str.lower().split("__")
    if any(seg == "" for seg in segments):
        raise ConfigError(f"Invalid environment variable '{var_name}': empty path segment")
    container, leaf_key = _resolve_target_container(data, segments, var_name)
    container[leaf_key] = _coerce_value(container[leaf_key], raw_value, var_name)


def _process_env(data: dict[str, Any], env: Mapping[str, str]) -> None:
    for key, value in env.items():
        if key.startswith("YTMCP_TOKEN_PASSPHRASE"):
            continue
        if key == "YTMCP_PROVIDER":
            if value not in ("fixture", "live", "recording"):
                raise ConfigError(
                    f"Invalid provider '{value}' for 'YTMCP_PROVIDER'. "
                    "Must be one of: fixture, live, recording"
                )
            data["provider"] = value
        elif key == "YTMCP_DATA_DIR":
            if value != "":
                data["data_dir"] = Path(value).expanduser()
        elif key.startswith("YTMCP_") and "__" in key:
            _apply_override(data, key, value)


def load_settings(
    path: Path | str | None = None,
    env: Mapping[str, str] | None = None,
) -> Settings:
    """Load configuration from TOML and environment variables into Settings."""
    config_path = DEFAULT_CONFIG_PATH if path is None else Path(path)
    if not config_path.is_file():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open("rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Failed to parse TOML configuration at {config_path}: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"Failed to read configuration file at {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file root must be a table: {config_path}")

    active_env = os.environ if env is None else env
    _process_env(data, active_env)

    try:
        return Settings(**data)
    except ValidationError as exc:
        raise ConfigError(f"Configuration validation failed: {exc}") from exc


__all__ = [
    "ApprovalConfig",
    "CacheConfig",
    "ChannelWeights",
    "ConfigError",
    "DEFAULT_CONFIG_PATH",
    "LimitsConfig",
    "PlaylistConfig",
    "QuotaConfig",
    "QuotaCosts",
    "Settings",
    "SimilarityConfig",
    "TasteConfig",
    "VideoWeights",
    "load_settings",
]
