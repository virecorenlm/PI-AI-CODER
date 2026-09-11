"""Configuration loading for PI-AI-CODER.

Precedence (lowest to highest):

    built-in defaults  <  user config  <  project config file  <  selected host profile  <  environment variables  <  CLI arguments

The application must remain usable without the user ever creating a config
file -- every field has a sensible default matching ``config.example.yaml``.

PI-AI-CODER targets multiple Linux hosts (Raspberry Pi, workstations, etc.)
with different model backends. Hardware-specific tuning (thread counts,
context sizes, which provider to use) belongs here -- in configuration and
optional per-host "profiles" -- never hard-coded into the application core.

There are two separate roots at play: the *application* root (wherever
PI-AI-CODER is installed) and the *project* root (the user's active
workspace, resolved by ``pi_ai_coder.core.project.resolve_project_root``).
Project-level config (``<project>/config.yaml``) is scoped to whichever
project is currently open. But provider/profile setup (e.g. "always use my
Ollama server") is something a user reasonably wants to configure *once*
and have apply everywhere, regardless of which project they're in -- that's
what the user-level config file below is for. It is intentionally NOT tied
to the application's install directory either: it lives in the standard
per-user config location so `pip install`-ing PI-AI-CODER elsewhere doesn't
lose it.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a declared dependency
    yaml = None

DEFAULT_CONFIG_FILENAMES = ("config.yaml", "config.yml", ".pi-ai-coder.yaml")


@dataclass
class ModelSettings:
    provider: str = "llama_cpp"  # "llama_cpp" | "ollama"
    path: str = "./models/qwen2.5-coder-7b-instruct-q4_k_m.gguf"  # llama.cpp GGUF path
    context_size: int = 4096
    max_tokens: int = 2048
    temperature: float = 0.1
    top_p: float = 0.95
    top_k: int = 40
    repeat_penalty: float = 1.1
    threads: int = 4  # generic default -- tune per host via config/profile, not code
    llama_cpp_dir: str = "./llama.cpp"


@dataclass
class OllamaSettings:
    host: str = "http://127.0.0.1:11434"
    model: str = ""
    timeout: float = 120.0


@dataclass
class UiSettings:
    theme: str = "dark"
    show_token_usage: bool = False


@dataclass
class ProjectSettings:
    auto_context: bool = True
    max_file_size_kb: int = 500


@dataclass
class AppConfig:
    model: ModelSettings = field(default_factory=ModelSettings)
    ollama: OllamaSettings = field(default_factory=OllamaSettings)
    ui: UiSettings = field(default_factory=UiSettings)
    project: ProjectSettings = field(default_factory=ProjectSettings)
    profiles: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    active_profile: Optional[str] = None


def _find_config_file(project_dir: Path) -> Optional[Path]:
    for name in DEFAULT_CONFIG_FILENAMES:
        candidate = project_dir / name
        if candidate.is_file():
            return candidate
    return None


def user_config_path(env: Optional[Dict[str, str]] = None) -> Path:
    """Where the user-level config file lives: ``$XDG_CONFIG_HOME/pi-ai-coder/config.yaml``,
    or ``~/.config/pi-ai-coder/config.yaml`` if that's unset.

    Reads from ``env`` (falling back to real ``os.environ``) rather than
    always reading the process environment directly, so callers -- tests
    especially -- can fully isolate this from the actual user's home
    directory by passing a custom ``env`` dict.
    """
    env = env if env is not None else os.environ
    xdg_home = env.get("XDG_CONFIG_HOME")
    if xdg_home:
        base = Path(xdg_home).expanduser()
    else:
        home = env.get("HOME")
        base = (Path(home).expanduser() if home else Path.home()) / ".config"
    return base / "pi-ai-coder" / "config.yaml"


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load a config file but is not installed")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _apply_file(config: AppConfig, data: Dict[str, Any]) -> AppConfig:
    if not data:
        return config

    model_data = data.get("model", {}) or {}
    ollama_data = data.get("ollama", {}) or {}
    ui_data = data.get("ui", {}) or data.get("interface", {}) or {}
    project_data = data.get("project", {}) or data.get("context", {}) or {}
    profiles_data = data.get("profiles", {}) or {}

    model = replace(
        config.model,
        **{k: v for k, v in model_data.items() if k in ModelSettings.__dataclass_fields__},
    )
    ollama = replace(
        config.ollama,
        **{k: v for k, v in ollama_data.items() if k in OllamaSettings.__dataclass_fields__},
    )
    ui = replace(
        config.ui,
        **{k: v for k, v in ui_data.items() if k in UiSettings.__dataclass_fields__},
    )
    project_updates = {}
    if "auto_context" in project_data:
        project_updates["auto_context"] = project_data["auto_context"]
    if "auto_discovery" in project_data:
        project_updates["auto_context"] = project_data["auto_discovery"]
    if "max_file_size_kb" in project_data:
        project_updates["max_file_size_kb"] = project_data["max_file_size_kb"]
    project = replace(config.project, **project_updates)

    return AppConfig(
        model=model,
        ollama=ollama,
        ui=ui,
        project=project,
        profiles={**config.profiles, **profiles_data},
        active_profile=config.active_profile,
    )


# Flat profile keys (see config.example.yaml's `profiles:` section) mapped
# to (section, field). "model" is handled separately since it means
# different things depending on the profile's provider (a GGUF path for
# llama_cpp, an Ollama model tag for ollama).
_PROFILE_FLAT_MAP: Dict[str, tuple] = {
    "provider": ("model", "provider"),
    "path": ("model", "path"),
    "context_size": ("model", "context_size"),
    "max_tokens": ("model", "max_tokens"),
    "temperature": ("model", "temperature"),
    "top_p": ("model", "top_p"),
    "top_k": ("model", "top_k"),
    "repeat_penalty": ("model", "repeat_penalty"),
    "threads": ("model", "threads"),
    "llama_cpp_dir": ("model", "llama_cpp_dir"),
    "ollama_host": ("ollama", "host"),
    "ollama_timeout": ("ollama", "timeout"),
}


def _apply_profile(config: AppConfig, profile: Dict[str, Any]) -> AppConfig:
    provider = profile.get("provider", config.model.provider)
    model_updates: Dict[str, Any] = {}
    ollama_updates: Dict[str, Any] = {}

    for key, value in profile.items():
        if key == "model":
            if provider == "ollama":
                ollama_updates["model"] = value
            else:
                model_updates["path"] = value
            continue
        mapping = _PROFILE_FLAT_MAP.get(key)
        if mapping is None:
            continue
        section, field_name = mapping
        if section == "model":
            model_updates[field_name] = value
        else:
            ollama_updates[field_name] = value

    return AppConfig(
        model=replace(config.model, **model_updates),
        ollama=replace(config.ollama, **ollama_updates),
        ui=config.ui,
        project=config.project,
        profiles=config.profiles,
        active_profile=config.active_profile,
    )


_ENV_MAP: Dict[str, tuple] = {
    "PI_CODER_MODEL_PROVIDER": ("model", "provider", str),
    "PI_CODER_MODEL_PATH": ("model", "path", str),
    "PI_CODER_MODEL_CONTEXT_SIZE": ("model", "context_size", int),
    "PI_CODER_MODEL_MAX_TOKENS": ("model", "max_tokens", int),
    "PI_CODER_MODEL_TEMPERATURE": ("model", "temperature", float),
    "PI_CODER_MODEL_THREADS": ("model", "threads", int),
    "PI_CODER_LLAMA_DIR": ("model", "llama_cpp_dir", str),
    "PI_CODER_OLLAMA_HOST": ("ollama", "host", str),
    "PI_CODER_OLLAMA_MODEL": ("ollama", "model", str),
    "PI_CODER_OLLAMA_TIMEOUT": ("ollama", "timeout", float),
    "PI_CODER_UI_THEME": ("ui", "theme", str),
    "PI_CODER_SHOW_TOKEN_USAGE": ("ui", "show_token_usage", bool),
    "PI_CODER_AUTO_CONTEXT": ("project", "auto_context", bool),
    "PI_CODER_MAX_FILE_SIZE_KB": ("project", "max_file_size_kb", int),
}


def _coerce_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _apply_env(config: AppConfig, env: Dict[str, str]) -> AppConfig:
    updates: Dict[str, Dict[str, Any]] = {"model": {}, "ollama": {}, "ui": {}, "project": {}}
    for env_key, (section, field_name, kind) in _ENV_MAP.items():
        if env_key not in env:
            continue
        raw = env[env_key]
        value: Any = _coerce_bool(raw) if kind is bool else kind(raw)
        updates[section][field_name] = value

    return AppConfig(
        model=replace(config.model, **updates["model"]),
        ollama=replace(config.ollama, **updates["ollama"]),
        ui=replace(config.ui, **updates["ui"]),
        project=replace(config.project, **updates["project"]),
        profiles=config.profiles,
        active_profile=config.active_profile,
    )


def load_config(
    config_path: Optional[str] = None,
    project_dir: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    cli_overrides: Optional[Dict[str, Any]] = None,
    profile: Optional[str] = None,
) -> AppConfig:
    """Load configuration applying:

        defaults < user config < project config file < selected profile < env < CLI

    ``project_dir`` should be the *project* root (see
    ``pi_ai_coder.core.project.resolve_project_root``), not wherever
    PI-AI-CODER happens to be installed -- callers must pass it explicitly
    rather than relying on the ``Path.cwd()`` fallback below, which only
    exists for standalone/test use.

    ``cli_overrides`` is a flat dict of dotted keys, e.g. ``{"model.path": "..."}``
    or ``{"ollama.host": "..."}``. ``profile`` selects a host profile by name
    (see config.example.yaml); it can also come from the user or project
    config's top-level ``profile:`` key or the ``PI_CODER_PROFILE`` env var
    -- CLI wins if given explicitly. Profiles defined in both the user and
    project config are merged, with the project's definitions winning on
    name collisions.
    """
    env = env if env is not None else os.environ
    project_dir_path = Path(project_dir) if project_dir else Path.cwd()
    config = AppConfig()

    user_data: Dict[str, Any] = {}
    user_path = user_config_path(env)
    if user_path.is_file():
        user_data = _load_yaml_file(user_path)
        config = _apply_file(config, user_data)

    project_data: Dict[str, Any] = {}
    file_path = Path(config_path) if config_path else _find_config_file(project_dir_path)
    if file_path and file_path.is_file():
        project_data = _load_yaml_file(file_path)
        config = _apply_file(config, project_data)

    selected_profile = (
        profile
        or env.get("PI_CODER_PROFILE")
        or project_data.get("profile")
        or user_data.get("profile")
    )
    if selected_profile:
        profile_data = config.profiles.get(selected_profile)
        if profile_data is None:
            raise ValueError(
                f"Unknown profile '{selected_profile}'. Known profiles: {', '.join(sorted(config.profiles)) or '(none defined)'}"
            )
        config = _apply_profile(config, profile_data)
        config = replace(config, active_profile=selected_profile)

    config = _apply_env(config, env)

    if cli_overrides:
        model_updates: Dict[str, Any] = {}
        ollama_updates: Dict[str, Any] = {}
        ui_updates: Dict[str, Any] = {}
        project_updates: Dict[str, Any] = {}
        for dotted_key, value in cli_overrides.items():
            if value is None:
                continue
            section, _, field_name = dotted_key.partition(".")
            if section == "model" and field_name in ModelSettings.__dataclass_fields__:
                model_updates[field_name] = value
            elif section == "ollama" and field_name in OllamaSettings.__dataclass_fields__:
                ollama_updates[field_name] = value
            elif section == "ui" and field_name in UiSettings.__dataclass_fields__:
                ui_updates[field_name] = value
            elif section == "project" and field_name in ProjectSettings.__dataclass_fields__:
                project_updates[field_name] = value
        config = AppConfig(
            model=replace(config.model, **model_updates),
            ollama=replace(config.ollama, **ollama_updates),
            ui=replace(config.ui, **ui_updates),
            project=replace(config.project, **project_updates),
            profiles=config.profiles,
            active_profile=config.active_profile,
        )

    return config
