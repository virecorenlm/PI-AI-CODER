import pytest

from pi_ai_coder.models.base import Message, ModelConfig
from pi_ai_coder.models.llama_cpp_provider import LlamaCppProvider, find_llama_executable


def test_find_llama_executable_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_llama_executable(tmp_path)


def test_find_llama_executable_prefers_new_name(tmp_path):
    (tmp_path / "main").touch()
    (tmp_path / "llama-cli").touch()
    assert find_llama_executable(tmp_path).name == "llama-cli"


def test_find_llama_executable_falls_back_to_main(tmp_path):
    (tmp_path / "main").touch()
    assert find_llama_executable(tmp_path).name == "main"


def test_format_prompt_uses_chatml(tmp_path):
    (tmp_path / "main").touch()
    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path="model.gguf"),
    )
    prompt = provider.format_prompt([
        Message("system", "be helpful"),
        Message("user", "hi"),
    ])
    assert "<|im_start|>system\nbe helpful<|im_end|>" in prompt
    assert "<|im_start|>user\nhi<|im_end|>" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")


def test_clean_output_strips_chatml_markers(tmp_path):
    (tmp_path / "main").touch()
    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path="model.gguf"),
    )
    raw = "some preamble<|im_start|>assistant\nhello world<|im_end|>"
    assert provider._clean_output(raw) == "hello world"


def test_health_check_reports_missing_model_file(tmp_path):
    (tmp_path / "main").touch()
    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path=str(tmp_path / "nope.gguf")),
    )
    health = provider.health_check()
    assert not health.available
    assert "not found" in health.message.lower()


def test_health_check_available_when_files_exist(tmp_path):
    (tmp_path / "main").touch()
    model_path = tmp_path / "model.gguf"
    model_path.touch()
    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path=str(model_path)),
    )
    assert provider.health_check().available


def test_list_models_scans_models_directory_only(tmp_path):
    (tmp_path / "main").touch()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "a.gguf").write_bytes(b"x" * 10)
    (models_dir / "b.gguf").write_bytes(b"x" * 20)
    (models_dir / "notes.txt").write_text("not a model")

    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path=str(models_dir / "a.gguf")),
    )
    models = provider.list_models()
    names = {m.name for m in models}
    assert names == {"a.gguf", "b.gguf"}


def test_set_model_resolves_sibling_filename(tmp_path):
    (tmp_path / "main").touch()
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    (models_dir / "a.gguf").touch()
    (models_dir / "b.gguf").touch()

    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path=str(models_dir / "a.gguf")),
    )
    provider.set_model("b.gguf")
    assert provider.config.model_path == str((models_dir / "b.gguf").resolve())


def test_set_model_accepts_full_path(tmp_path):
    (tmp_path / "main").touch()
    other = tmp_path / "elsewhere.gguf"
    other.touch()
    provider = LlamaCppProvider(
        llama_cpp_dir=str(tmp_path),
        config=ModelConfig(model_path="model.gguf"),
    )
    provider.set_model(str(other))
    assert provider.config.model_path == str(other)
