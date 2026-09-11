import pytest

from pi_ai_coder.config import AppConfig
from pi_ai_coder.models.factory import create_provider
from pi_ai_coder.models.fake_provider import FakeModelProvider
from pi_ai_coder.models.llama_cpp_provider import LlamaCppProvider
from pi_ai_coder.models.ollama_provider import OllamaProvider


def test_fake_model_flag_wins_regardless_of_provider():
    config = AppConfig()
    config.model.provider = "ollama"
    provider = create_provider(config, fake_model=True)
    assert isinstance(provider, FakeModelProvider)


def test_creates_ollama_provider(tmp_path):
    config = AppConfig()
    config.model.provider = "ollama"
    config.ollama.model = "qwen3.5:latest"
    config.ollama.host = "http://example:11434"
    provider = create_provider(config)
    assert isinstance(provider, OllamaProvider)
    assert provider.config.model == "qwen3.5:latest"
    assert provider.config.host == "http://example:11434"


def test_creates_llama_cpp_provider(tmp_path):
    llama_dir = tmp_path / "llama.cpp"
    llama_dir.mkdir()
    (llama_dir / "main").touch()
    model_path = tmp_path / "model.gguf"
    model_path.touch()

    config = AppConfig()
    config.model.provider = "llama_cpp"
    config.model.llama_cpp_dir = str(llama_dir)
    config.model.path = str(model_path)

    provider = create_provider(config)
    assert isinstance(provider, LlamaCppProvider)
    assert provider.config.model_path == str(model_path)


def test_unknown_provider_raises():
    config = AppConfig()
    config.model.provider = "something-else"
    with pytest.raises(ValueError):
        create_provider(config)
