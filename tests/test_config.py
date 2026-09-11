import pytest

from pi_ai_coder.config import load_config


def test_defaults_without_any_config():
    config = load_config(project_dir="/nonexistent/path/for/defaults", env={})
    assert config.model.path.endswith(".gguf")
    assert config.model.temperature == 0.1
    assert config.project.auto_context is True
    assert config.project.max_file_size_kb == 500


def test_file_overrides_defaults(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
model:
  path: "./models/custom.gguf"
  temperature: 0.5
  threads: 8
project:
  auto_context: false
  max_file_size_kb: 250
ui:
  theme: light
"""
    )
    config = load_config(config_path=str(config_file), env={})
    assert config.model.path == "./models/custom.gguf"
    assert config.model.temperature == 0.5
    assert config.model.threads == 8
    assert config.project.auto_context is False
    assert config.project.max_file_size_kb == 250
    assert config.ui.theme == "light"


def test_env_overrides_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("model:\n  temperature: 0.5\n")
    env = {"PI_CODER_MODEL_TEMPERATURE": "0.9"}
    config = load_config(config_path=str(config_file), env=env)
    assert config.model.temperature == 0.9


def test_cli_overrides_everything(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("model:\n  temperature: 0.5\n")
    env = {"PI_CODER_MODEL_TEMPERATURE": "0.9"}
    config = load_config(
        config_path=str(config_file),
        env=env,
        cli_overrides={"model.temperature": 0.2},
    )
    assert config.model.temperature == 0.2


def test_auto_discovers_config_yaml_in_project_dir(tmp_path):
    (tmp_path / "config.yaml").write_text("project:\n  auto_context: false\n")
    config = load_config(project_dir=str(tmp_path), env={})
    assert config.project.auto_context is False


def test_default_provider_is_llama_cpp():
    config = load_config(project_dir="/nonexistent", env={})
    assert config.model.provider == "llama_cpp"


def test_ollama_section_loads_from_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
model:
  provider: ollama
ollama:
  host: "http://example:1234"
  model: "qwen3.5:latest"
  timeout: 30
"""
    )
    config = load_config(config_path=str(config_file), env={})
    assert config.model.provider == "ollama"
    assert config.ollama.host == "http://example:1234"
    assert config.ollama.model == "qwen3.5:latest"
    assert config.ollama.timeout == 30


def test_ollama_cli_overrides(tmp_path):
    config = load_config(
        project_dir=str(tmp_path),
        env={},
        cli_overrides={"ollama.host": "http://other:9999", "model.provider": "ollama"},
    )
    assert config.ollama.host == "http://other:9999"
    assert config.model.provider == "ollama"


def test_env_selects_provider_and_ollama_settings():
    env = {
        "PI_CODER_MODEL_PROVIDER": "ollama",
        "PI_CODER_OLLAMA_HOST": "http://envhost:11434",
        "PI_CODER_OLLAMA_MODEL": "llama3:latest",
    }
    config = load_config(project_dir="/nonexistent", env=env)
    assert config.model.provider == "ollama"
    assert config.ollama.host == "http://envhost:11434"
    assert config.ollama.model == "llama3:latest"


def test_profile_applies_flat_overrides(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
model:
  provider: llama_cpp
profiles:
  asrock:
    provider: ollama
    ollama_host: "http://127.0.0.1:11434"
    model: "qwen3.5:latest"
  pi5:
    provider: llama_cpp
    threads: 4
    context_size: 4096
"""
    )
    config = load_config(config_path=str(config_file), env={}, profile="asrock")
    assert config.model.provider == "ollama"
    assert config.ollama.host == "http://127.0.0.1:11434"
    assert config.ollama.model == "qwen3.5:latest"
    assert config.active_profile == "asrock"


def test_profile_from_file_top_level_key(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
profile: pi5
profiles:
  pi5:
    threads: 8
"""
    )
    config = load_config(config_path=str(config_file), env={})
    assert config.model.threads == 8
    assert config.active_profile == "pi5"


def test_unknown_profile_raises(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("profiles:\n  pi5:\n    threads: 4\n")
    with pytest.raises(ValueError):
        load_config(config_path=str(config_file), env={}, profile="nonexistent")


def test_env_and_cli_still_win_over_profile(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
profiles:
  pi5:
    threads: 4
"""
    )
    config = load_config(
        config_path=str(config_file),
        env={"PI_CODER_MODEL_THREADS": "16"},
        profile="pi5",
        cli_overrides={"model.threads": 2},
    )
    assert config.model.threads == 2
