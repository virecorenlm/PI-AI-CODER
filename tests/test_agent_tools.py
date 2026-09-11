"""Tests for the agent's ToolRegistry -- required tests #1-9, #16."""

import os
import subprocess

import pytest

from pi_ai_coder.agent.protocol import ToolCall
from pi_ai_coder.agent.tools import ToolRegistry
from pi_ai_coder.tools.base import RiskLevel
from pi_ai_coder.tools.files import FileTool
from pi_ai_coder.tools.git import GitTool
from pi_ai_coder.tools.search import SearchTool


def make_registry(project_root, **kwargs):
    file_tool = FileTool(project_root=str(project_root))
    git_tool = GitTool(cwd=str(project_root))
    search_tool = SearchTool(project_root=str(project_root))
    return ToolRegistry(project_root=str(project_root), file_tool=file_tool, git_tool=git_tool, search_tool=search_tool, **kwargs)


def call(registry, name, **arguments):
    return registry.execute(ToolCall(id="t1", name=name, arguments=arguments))


# -- 1. read_file inside project -----------------------------------------

def test_read_file_inside_project(tmp_path):
    (tmp_path / "a.py").write_text("print('hi')\n")
    registry = make_registry(tmp_path)
    result = call(registry, "read_file", path="a.py")
    assert result.success
    assert "print('hi')" in result.output


# -- 2. path escape rejection ---------------------------------------------

def test_read_file_rejects_path_escape(tmp_path):
    outside = tmp_path.parent / "outside_secret.txt"
    outside.write_text("secret")
    registry = make_registry(tmp_path)
    result = call(registry, "read_file", path="../outside_secret.txt")
    assert not result.success
    assert "escapes project root" in result.error


def test_apply_patch_rejects_path_escape(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="../../etc/passwd", edits=[{"old": "root", "new": "x"}])
    assert not result.success
    assert "escapes project root" in result.error


def test_write_file_rejects_absolute_path_outside_project(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "write_file", path="/etc/pi-coder-should-not-exist.txt", content="x")
    assert not result.success


# -- 3. symlink escape rejection -------------------------------------------

def test_read_file_rejects_symlink_escape(tmp_path):
    outside_dir = tmp_path.parent / "escape_target"
    outside_dir.mkdir(exist_ok=True)
    (outside_dir / "secret.txt").write_text("top secret")

    project = tmp_path / "project"
    project.mkdir()
    link = project / "link_out"
    try:
        link.symlink_to(outside_dir)
    except OSError:
        pytest.skip("symlinks not supported in this environment")

    registry = make_registry(project)
    result = call(registry, "read_file", path="link_out/secret.txt")
    assert not result.success
    assert "escapes project root" in result.error


# -- 4. create_file ----------------------------------------------------

def test_create_file(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "create_file", path="new/module.py", content="x = 1\n")
    assert result.success
    assert (tmp_path / "new" / "module.py").read_text() == "x = 1\n"


def test_create_file_fails_if_exists(tmp_path):
    (tmp_path / "existing.py").write_text("x = 1\n")
    registry = make_registry(tmp_path)
    result = call(registry, "create_file", path="existing.py", content="y = 2\n")
    assert not result.success
    assert "already exists" in result.error


# -- 5. apply_patch -----------------------------------------------------

def test_apply_patch_success(tmp_path):
    (tmp_path / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="calc.py", edits=[
        {"old": "    return a / b", "new": "    if b == 0:\n        raise ValueError('no')\n    return a / b"},
    ])
    assert result.success
    content = (tmp_path / "calc.py").read_text()
    assert "raise ValueError" in content
    assert "diff" in result.data


# -- 6. patch conflict/failure --------------------------------------------

def test_apply_patch_fails_when_text_not_found(tmp_path):
    (tmp_path / "calc.py").write_text("def divide(a, b):\n    return a / b\n")
    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="calc.py", edits=[
        {"old": "def multiply(a, b):", "new": "def multiply(a, b, c):"},
    ])
    assert not result.success
    assert "not found" in result.error
    # file must be untouched
    assert (tmp_path / "calc.py").read_text() == "def divide(a, b):\n    return a / b\n"


def test_apply_patch_fails_when_text_ambiguous(tmp_path):
    (tmp_path / "dup.py").write_text("x = 1\nx = 1\n")
    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="dup.py", edits=[{"old": "x = 1", "new": "x = 2"}])
    assert not result.success
    assert "matched 2 times" in result.error
    assert (tmp_path / "dup.py").read_text() == "x = 1\nx = 1\n"


def test_apply_patch_missing_file_says_use_create_file(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="nope.py", edits=[{"old": "a", "new": "b"}])
    assert not result.success
    assert "create_file" in result.error


# -- 7. editing an already-modified git file without discarding unrelated changes --

def test_apply_patch_preserves_unrelated_changes_in_same_file(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    original = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
    (tmp_path / "mod.py").write_text(original)
    subprocess.run(["git", "add", "mod.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    # user already has an unrelated, uncommitted change to function a()
    (tmp_path / "mod.py").write_text("def a():\n    return 999  # user's own WIP change\n\n\ndef b():\n    return 2\n")

    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="mod.py", edits=[
        {"old": "def b():\n    return 2", "new": "def b():\n    return 3"},
    ])
    assert result.success
    content = (tmp_path / "mod.py").read_text()
    assert "return 999  # user's own WIP change" in content  # untouched
    assert "return 3" in content  # our edit applied
    assert "return 2\n" not in content or "return 3" in content


def test_apply_patch_preserves_other_uncommitted_files(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "b.py").write_text("y = 1\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    (tmp_path / "b.py").write_text("y = 999  # unrelated WIP\n")

    registry = make_registry(tmp_path)
    result = call(registry, "apply_patch", path="a.py", edits=[{"old": "x = 1", "new": "x = 2"}])
    assert result.success
    assert (tmp_path / "b.py").read_text() == "y = 999  # unrelated WIP\n"


# -- 8. search_code ---------------------------------------------------

def test_search_code_finds_matches(tmp_path):
    (tmp_path / "auth.py").write_text("def register_user():\n    pass\n")
    (tmp_path / "other.py").write_text("def unrelated():\n    pass\n")
    registry = make_registry(tmp_path)
    result = call(registry, "search_code", query="register_user")
    assert result.success
    assert "auth.py" in result.output
    assert "other.py" not in result.output


def test_search_code_respects_glob(tmp_path):
    (tmp_path / "a.py").write_text("TARGET\n")
    (tmp_path / "a.txt").write_text("TARGET\n")
    registry = make_registry(tmp_path)
    result = call(registry, "search_code", query="TARGET", glob="*.py")
    assert "a.py" in result.output
    assert "a.txt" not in result.output


# -- 9. command result propagation -----------------------------------------

def test_run_command_propagates_output_and_exit_code(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "run_command", command="echo hello && exit 0")
    assert result.success
    assert "hello" in result.output
    assert result.data["exit_code"] == 0


def test_run_command_propagates_failure(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "run_command", command="exit 7")
    assert not result.success
    assert result.data["exit_code"] == 7


def test_run_command_output_is_capped(tmp_path):
    registry = make_registry(tmp_path, max_output_chars=100)
    result = call(registry, "run_command", command="python3 -c \"print('x' * 5000)\"")
    assert result.success
    assert "[output truncated]" in result.output
    assert len(result.output) < 5000


# -- 16. non-destructive development command execution ----------------------

def test_routine_dev_commands_classified_as_execute_not_destructive(tmp_path):
    registry = make_registry(tmp_path)
    for cmd in ["pytest -q", "python -m pytest", "git status", "git diff"]:
        tc = ToolCall(id="x", name="run_command", arguments={"command": cmd})
        assert registry.classify(tc) == RiskLevel.EXECUTE


# -- misc registry behavior -------------------------------------------------

def test_unknown_tool_returns_clean_failure_not_crash(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "delete_universe")
    assert not result.success
    assert "Unknown tool" in result.error


def test_missing_required_argument_returns_clean_failure(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "read_file")  # no path
    assert not result.success
    assert "path" in result.error


def test_git_status_and_diff_tools_are_read_only(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    registry = make_registry(tmp_path)
    tc_status = ToolCall(id="x", name="git_status", arguments={})
    tc_diff = ToolCall(id="y", name="git_diff", arguments={})
    assert registry.classify(tc_status) == RiskLevel.READ
    assert registry.classify(tc_diff) == RiskLevel.READ
    assert call(registry, "git_status").success
    assert call(registry, "git_diff").success


def test_run_command_cwd_argument_is_project_scoped(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "marker.txt").write_text("here\n")
    registry = make_registry(tmp_path)
    result = call(registry, "run_command", command="cat marker.txt", cwd="sub")
    assert result.success
    assert "here" in result.output


def test_run_command_cwd_escape_rejected(tmp_path):
    registry = make_registry(tmp_path)
    result = call(registry, "run_command", command="pwd", cwd="../")
    assert not result.success
    assert "escapes project root" in result.error
