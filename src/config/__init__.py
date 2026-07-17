"""Cross-layer configuration store. Shared by the CLI engine (src/) and the
web server (server/) so both read from the same `data/settings.json`."""
from .store import (
    DEFAULT_REFERENCE_LISTS,
    DEFAULTS,
    SettingsStore,
    get_api_key,
    get_default_model,
    get_default_passage_rule,
    get_default_temperature,
    get_prompt,
    get_reference_list,
    get_settings_store,
    load,
    save,
)

__all__ = [
    "DEFAULT_REFERENCE_LISTS",
    "DEFAULTS",
    "SettingsStore",
    "get_api_key",
    "get_default_model",
    "get_default_passage_rule",
    "get_default_temperature",
    "get_prompt",
    "get_reference_list",
    "get_settings_store",
    "load",
    "save",
]
