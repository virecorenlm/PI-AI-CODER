from pathlib import Path

from pi_ai_coder.context.manager import ContextManager


def test_should_ignore_common_patterns():
    cm = ContextManager()
    assert cm.should_ignore(Path("foo/__pycache__/bar.pyc"))
    assert cm.should_ignore(Path("node_modules/pkg/index.js"))
    assert not cm.should_ignore(Path("src/main.py"))


def test_should_ignore_custom_patterns():
    cm = ContextManager(ignore_patterns=["vendor"])
    assert cm.should_ignore(Path("vendor/lib.py"))


def test_chunk_python_file_splits_functions_and_classes():
    cm = ContextManager()
    content = (
        "import os\n\n"
        "def foo():\n"
        "    return 1\n\n"
        "class Bar:\n"
        "    def method(self):\n"
        "        return 2\n"
    )
    chunks = cm.chunk_python_file(content, "example.py")
    types = [c.chunk_type for c in chunks]
    assert "function" in types
    assert "class" in types


def test_build_context_respects_char_budget(tmp_path):
    cm = ContextManager()
    big_file = tmp_path / "big.py"
    big_file.write_text("def f():\n" + "    pass\n" * 5000)

    context = cm.build_context([str(big_file)], "f")
    assert len(context) <= cm.MAX_CONTEXT_CHARS + 2000  # a little slack for headers


def test_load_file_skips_oversized_files(tmp_path):
    cm = ContextManager(max_file_size_kb=1)
    big_file = tmp_path / "big.txt"
    big_file.write_text("x" * 2048)
    assert cm.load_file(str(big_file)) == []


def test_load_file_caches_result(tmp_path):
    cm = ContextManager()
    f = tmp_path / "a.py"
    f.write_text("def a():\n    return 1\n")
    first = cm.load_file(str(f))
    second = cm.load_file(str(f))
    assert first is second


def test_invalidate_clears_cache(tmp_path):
    cm = ContextManager()
    f = tmp_path / "a.py"
    f.write_text("def a():\n    return 1\n")
    cm.load_file(str(f))
    assert str(f) in cm.file_cache
    cm.invalidate(str(f))
    assert str(f) not in cm.file_cache
