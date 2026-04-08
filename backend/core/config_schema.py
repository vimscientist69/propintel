from __future__ import annotations

from typing import Any


class SourcesConfigValidationError(ValueError):
    """Raised when sources config shape/types do not match expected schema."""


_TOP_LEVEL_KEYS = {"input", "website", "google_maps", "scoring", "runtime"}
_INPUT_KEYS = {"required_any", "schema_aliases", "defaults", "strict_contact_validation"}
_INPUT_ALIAS_FIELDS = {"company_name", "agent_name", "website", "email", "phone", "location", "source"}
_WEBSITE_KEYS = {
    "enabled",
    "discover_with_serper",
    "max_retries",
    "request_timeout_seconds",
    "serper_timeout_seconds",
    "user_agent",
    "email_selectors",
    "phone_patterns",
    "chatbot_keywords",
}
_GOOGLE_KEYS = {"enabled", "timeout_seconds", "max_retries", "min_name_match_score", "region", "language"}
_SCORING_KEYS = {"enabled", "base_score", "weights"}
_RUNTIME_KEYS = {"batch_size", "stop_on_batch_error", "worker_concurrency", "providers"}
_RUNTIME_PROVIDERS_KEYS = {"google_maps", "serper"}
_RUNTIME_PROVIDER_KEYS = {
    "enabled",
    "requests_per_second",
    "burst",
    "max_concurrent",
    "timeout_seconds",
    "retry",
}
_RUNTIME_RETRY_KEYS = {"max_attempts", "base_delay_ms", "max_delay_ms", "jitter_ms"}
_WEIGHTS_KEYS = {
    "contact_quality_verified",
    "contact_quality_likely",
    "contact_quality_low",
    "both_channels_bonus",
    "chatbot_penalty",
    "last_updated_bonus",
    "last_updated_unknown_penalty",
    "website_speed_high_threshold",
    "website_speed_high_bonus",
    "website_speed_mid_threshold",
    "website_speed_mid_bonus",
    "website_speed_low_threshold",
    "website_speed_low_penalty",
    "website_speed_unknown_penalty",
    "has_website",
    "google_maps_source_bonus",
    "has_location_bonus",
    "has_agent_name_bonus",
}


def _err(msg: str) -> SourcesConfigValidationError:
    return SourcesConfigValidationError(msg)


def _ensure_obj(value: Any, ctx: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _err(f"{ctx} must be an object")
    return value


def _check_unknown_keys(value: dict[str, Any], allowed: set[str], ctx: str) -> None:
    unknown = sorted(set(value.keys()) - allowed)
    if unknown:
        raise _err(f"{ctx} has unknown keys: {', '.join(unknown)}")


def _ensure_list_of_str(value: Any, ctx: str) -> None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise _err(f"{ctx} must be a list of strings")


def _ensure_bool(value: Any, ctx: str) -> None:
    if not isinstance(value, bool):
        raise _err(f"{ctx} must be a boolean")


def _ensure_number(value: Any, ctx: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise _err(f"{ctx} must be a number")


def _ensure_int(value: Any, ctx: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise _err(f"{ctx} must be an integer")


def _ensure_positive_number(value: Any, ctx: str) -> None:
    _ensure_number(value, ctx)
    if float(value) <= 0:
        raise _err(f"{ctx} must be > 0")


def validate_sources_config(sources_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = _ensure_obj(sources_cfg, "sources config")
    _check_unknown_keys(cfg, _TOP_LEVEL_KEYS, "sources config")

    if "input" in cfg:
        input_cfg = _ensure_obj(cfg["input"], "input")
        _check_unknown_keys(input_cfg, _INPUT_KEYS, "input")
        if "required_any" in input_cfg:
            _ensure_list_of_str(input_cfg["required_any"], "input.required_any")
        if "schema_aliases" in input_cfg:
            aliases = _ensure_obj(input_cfg["schema_aliases"], "input.schema_aliases")
            _check_unknown_keys(aliases, _INPUT_ALIAS_FIELDS, "input.schema_aliases")
            for field, values in aliases.items():
                _ensure_list_of_str(values, f"input.schema_aliases.{field}")
        if "defaults" in input_cfg:
            defaults = _ensure_obj(input_cfg["defaults"], "input.defaults")
            for k, v in defaults.items():
                if not isinstance(k, str):
                    raise _err("input.defaults keys must be strings")
                if not isinstance(v, (str, int, float, bool)) and v is not None:
                    raise _err(f"input.defaults.{k} must be scalar")
        if "strict_contact_validation" in input_cfg:
            _ensure_bool(input_cfg["strict_contact_validation"], "input.strict_contact_validation")

    if "website" in cfg:
        website_cfg = _ensure_obj(cfg["website"], "website")
        _check_unknown_keys(website_cfg, _WEBSITE_KEYS, "website")
        for b in ("enabled", "discover_with_serper"):
            if b in website_cfg:
                _ensure_bool(website_cfg[b], f"website.{b}")
        for i in ("max_retries", "request_timeout_seconds", "serper_timeout_seconds"):
            if i in website_cfg:
                _ensure_int(website_cfg[i], f"website.{i}")
        if "user_agent" in website_cfg and not isinstance(website_cfg["user_agent"], str):
            raise _err("website.user_agent must be a string")
        for arr in ("email_selectors", "phone_patterns", "chatbot_keywords"):
            if arr in website_cfg:
                _ensure_list_of_str(website_cfg[arr], f"website.{arr}")

    if "google_maps" in cfg:
        g_cfg = _ensure_obj(cfg["google_maps"], "google_maps")
        _check_unknown_keys(g_cfg, _GOOGLE_KEYS, "google_maps")
        if "enabled" in g_cfg:
            _ensure_bool(g_cfg["enabled"], "google_maps.enabled")
        for i in ("timeout_seconds", "max_retries"):
            if i in g_cfg:
                _ensure_int(g_cfg[i], f"google_maps.{i}")
        if "min_name_match_score" in g_cfg:
            _ensure_number(g_cfg["min_name_match_score"], "google_maps.min_name_match_score")
        for s in ("region", "language"):
            if s in g_cfg and not isinstance(g_cfg[s], str):
                raise _err(f"google_maps.{s} must be a string")

    if "scoring" in cfg:
        s_cfg = _ensure_obj(cfg["scoring"], "scoring")
        _check_unknown_keys(s_cfg, _SCORING_KEYS, "scoring")
        if "enabled" in s_cfg:
            _ensure_bool(s_cfg["enabled"], "scoring.enabled")
        if "base_score" in s_cfg:
            _ensure_int(s_cfg["base_score"], "scoring.base_score")
        if "weights" in s_cfg:
            weights = _ensure_obj(s_cfg["weights"], "scoring.weights")
            _check_unknown_keys(weights, _WEIGHTS_KEYS, "scoring.weights")
            for k, v in weights.items():
                _ensure_number(v, f"scoring.weights.{k}")

    if "runtime" in cfg:
        r_cfg = _ensure_obj(cfg["runtime"], "runtime")
        _check_unknown_keys(r_cfg, _RUNTIME_KEYS, "runtime")
        if "batch_size" in r_cfg:
            _ensure_int(r_cfg["batch_size"], "runtime.batch_size")
            if int(r_cfg["batch_size"]) < 10 or int(r_cfg["batch_size"]) > 2000:
                raise _err("runtime.batch_size must be between 10 and 2000")
        if "stop_on_batch_error" in r_cfg:
            _ensure_bool(r_cfg["stop_on_batch_error"], "runtime.stop_on_batch_error")
        if "worker_concurrency" in r_cfg:
            _ensure_int(r_cfg["worker_concurrency"], "runtime.worker_concurrency")
            if int(r_cfg["worker_concurrency"]) < 1 or int(r_cfg["worker_concurrency"]) > 64:
                raise _err("runtime.worker_concurrency must be between 1 and 64")
        if "providers" in r_cfg:
            providers = _ensure_obj(r_cfg["providers"], "runtime.providers")
            _check_unknown_keys(providers, _RUNTIME_PROVIDERS_KEYS, "runtime.providers")
            for provider_name, provider_cfg_raw in providers.items():
                provider_cfg = _ensure_obj(provider_cfg_raw, f"runtime.providers.{provider_name}")
                _check_unknown_keys(
                    provider_cfg,
                    _RUNTIME_PROVIDER_KEYS,
                    f"runtime.providers.{provider_name}",
                )
                if "enabled" in provider_cfg:
                    _ensure_bool(provider_cfg["enabled"], f"runtime.providers.{provider_name}.enabled")
                if "requests_per_second" in provider_cfg:
                    _ensure_positive_number(
                        provider_cfg["requests_per_second"],
                        f"runtime.providers.{provider_name}.requests_per_second",
                    )
                for int_key in ("burst", "max_concurrent", "timeout_seconds"):
                    if int_key in provider_cfg:
                        _ensure_int(
                            provider_cfg[int_key],
                            f"runtime.providers.{provider_name}.{int_key}",
                        )
                        if int(provider_cfg[int_key]) < 1:
                            raise _err(
                                f"runtime.providers.{provider_name}.{int_key} must be >= 1"
                            )
                if "retry" in provider_cfg:
                    retry_cfg = _ensure_obj(
                        provider_cfg["retry"], f"runtime.providers.{provider_name}.retry"
                    )
                    _check_unknown_keys(
                        retry_cfg,
                        _RUNTIME_RETRY_KEYS,
                        f"runtime.providers.{provider_name}.retry",
                    )
                    for retry_key in _RUNTIME_RETRY_KEYS:
                        if retry_key in retry_cfg:
                            _ensure_int(
                                retry_cfg[retry_key],
                                f"runtime.providers.{provider_name}.retry.{retry_key}",
                            )
                            if int(retry_cfg[retry_key]) < 0:
                                raise _err(
                                    f"runtime.providers.{provider_name}.retry.{retry_key} must be >= 0"
                                )

    return cfg
