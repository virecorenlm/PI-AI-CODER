import subprocess

import pytest

from pi_ai_coder.tools.base import PathOutsideProjectError, resolve_within_project
from pi_ai_coder.tools.files import FileTool
from pi_ai_coder.tools.git import GitTool
from pi_ai_coder.tools.shell import ShellTool


# -- path safety --------------------------------------------------------

def test_resolve_within_project_allows_relative_path(tmp_path):
    (tmp_path / "sub").mkdir()
    resolved = resolve_within_project("sub/file.py", str(tmp_path))
    assert resolved == (tmp_path / "sub" / "file.py").resolve()


def test_resolve_within_project_rejects_dotdot_escape(tmp_path):
    with pytest.raises(PathOutsideProjectError):
        resolve_within_project("../outside.py", str(tmp_path))


def test_resolve_within_project_rejects_absolute_outside_path(tmp_path):
    with pytest.raises(PathOutsideProjectError):
        resolve_within_project("/etc/passwd", str(tmp_path))


def test_resolve_within_project_allows_absolute_inside_path(tmp_path):
    target = tmp_path / "file.py"
    resolved = resolve_within_project(str(target), str(tmp_path))
    assert resolved == target.resolve()


# -- FileTool -------------------------------------------------------------

def test_file_tool_save_and_read_roundtrip(tmp_path):
    tool = FileTool(project_root=str(tmp_path))
    result = tool.save("out/output.py", "print('hi')\n")
    assert result.success

    read_result = tool.read_text("out/output.py")
    assert read_result.success
    assert read_result.output == "print('hi')\n"


def test_file_tool_save_rejects_path_outside_project(tmp_path):
    tool = FileTool(project_root=str(tmp_path))
    result = tool.save("../escape.py", "x = 1\n")
    assert not result.success
    assert "escapes project root" in result.error


def test_file_tool_read_missing_file(tmp_path):
    tool = FileTool(project_root=str(tmp_path))
    result = tool.read_text("nope.py")
    assert not result.success


def test_file_tool_save_unrestricted_allows_explicit_outside_path(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    outside_dir = tmp_path / "elsewhere"
    outside_dir.mkdir()
    target = outside_dir / "explicit.py"

    tool = FileTool(project_root=str(project))
    result = tool.save(str(target), "x = 1\n", restrict_to_project=False)

    assert result.success
    assert target.read_text() == "x = 1\n"


# -- ShellTool --------------------------------------------------------------

def test_shell_tool_run_success():
    tool = ShellTool()
    result = tool.run("echo hello")
    assert result.success
    assert "hello" in result.output
    assert result.exit_code == 0


def test_shell_tool_run_failure_exit_code():
    tool = ShellTool()
    result = tool.run("exit 3")
    assert not result.success
    assert result.exit_code == 3


def test_shell_tool_run_timeout():
    tool = ShellTool(timeout=0.1)
    result = tool.run("sleep 2")
    assert not result.success
    assert "timed out" in result.error


def test_shell_tool_run_streaming_yields_lines_and_sets_last_result():
    tool = ShellTool()
    lines = list(tool.run_streaming("echo one; echo two"))
    assert lines == ["one", "two"]
    assert tool.last_result is not None
    assert tool.last_result.success
    assert tool.last_result.exit_code == 0


def test_shell_tool_run_streaming_records_nonzero_exit():
    tool = ShellTool()
    list(tool.run_streaming("exit 5"))
    assert tool.last_result.exit_code == 5
    assert not tool.last_result.success


# -- GitTool ------------------------------------------------------------

@pytest.fixture
def git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    tracked = tmp_path / "tracked.py"
    tracked.write_text("x = 1\n")
    subprocess.run(["git", "add", "tracked.py"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
    return tmp_path


def test_git_tool_is_repo(git_repo):
    tool = GitTool(cwd=str(git_repo))
    assert tool.is_repo()


def test_git_tool_not_a_repo(tmp_path):
    tool = GitTool(cwd=str(tmp_path))
    assert not tool.is_repo()


def test_git_tool_status_detects_modified_and_untracked(git_repo):
    (git_repo / "tracked.py").write_text("x = 2\n")
    (git_repo / "new.py").write_text("y = 1\n")

    tool = GitTool(cwd=str(git_repo))
    statuses = {s.path: s for s in tool.status()}

    assert "tracked.py" in statuses
    assert statuses["tracked.py"].worktree_status == "M"
    assert "new.py" in statuses
    assert statuses["new.py"].is_untracked


def test_git_tool_diff_shows_change(git_repo):
    (git_repo / "tracked.py").write_text("x = 2\n")
    tool = GitTool(cwd=str(git_repo))
    result = tool.diff()
    assert result.success
    assert "tracked.py" in result.output
