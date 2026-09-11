"""Regression tests for the application-root vs. project-root distinction.

PI-AI-CODER is installed once (the "application root", wherever this repo
or its installed package lives) but must operate on whatever directory the
user is actually working in (the "project root"), resolved from the
current working directory at launch time or an explicit --project
override -- never conflated with where PI-AI-CODER itself lives.

These tests spawn the real CLI entry point (assistant.py) as a subprocess
with an explicit `cwd=` pointing at a throwaway temp directory that has no
relation to the PI-AI-CODER source tree, so they faithfully exercise "user
runs `pi-coder` from inside their own project" without needing the console
script installed. All use --fake-model; none require a real model.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pi_ai_coder.core.project import ProjectRootError, resolve_project_root

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSISTANT_PY = REPO_ROOT / "assistant.py"


def run_cli(args, cwd, env=None):
    return subprocess.run(
        [sys.executable, str(ASSISTANT_PY), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def make_git_project(tmp_path: Path, name: str = "proj") -> Path:
    project = tmp_path / name
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=project, check=True)
    (project / "main.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "main.py"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project, check=True)
    return project


# -- resolve_project_root() unit behavior -------------------------------

def test_resolve_project_root_accepts_existing_directory(tmp_path):
    assert resolve_project_root(str(tmp_path)) == tmp_path.resolve()


def test_resolve_project_root_rejects_missing_path(tmp_path):
    with pytest.raises(ProjectRootError):
        resolve_project_root(str(tmp_path / "nope"))


def test_resolve_project_root_rejects_a_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(ProjectRootError):
        resolve_project_root(str(f))


def test_resolve_project_root_dot_resolves_against_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_project_root(".") == tmp_path.resolve()


def test_resolve_project_root_relative_path_resolves_against_cwd(tmp_path, monkeypatch):
    sub = tmp_path / "sub"
    sub.mkdir()
    monkeypatch.chdir(tmp_path)
    assert resolve_project_root("sub") == sub.resolve()


# -- 1. cwd becomes project_root by default (CLI, via subprocess) -------

def test_cli_default_project_root_is_launch_cwd(tmp_path):
    """No --project given: the directory the process was launched from (not
    the PI-AI-CODER repo) must be what `diff`/`exec` operate on."""
    project = make_git_project(tmp_path)
    (project / "main.py").write_text("print('changed')\n")

    proc = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--fake-model"],
        input="diff\nquit\n",
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "main.py" in proc.stdout


# -- 2 & 3. --project overrides it, relative paths resolve correctly -----

def test_cli_project_flag_overrides_cwd(tmp_path):
    project = make_git_project(tmp_path, "target")
    other_cwd = tmp_path / "elsewhere"
    other_cwd.mkdir()

    # Launch from `other_cwd` but point at `target` via --project (relative path)
    result = run_cli(
        ["--project", "../target", "--fake-model", "-q", "hi"],
        cwd=other_cwd,
    )
    assert result.returncode == 0, result.stderr


def test_cli_project_dot_works(tmp_path):
    project = make_git_project(tmp_path)
    result = run_cli(["--project", ".", "--fake-model", "-q", "hi"], cwd=project)
    assert result.returncode == 0, result.stderr


def test_cli_rejects_nonexistent_project(tmp_path):
    result = run_cli(["--project", str(tmp_path / "nope"), "--fake-model", "-q", "hi"], cwd=tmp_path)
    assert result.returncode != 0
    assert "does not exist" in result.stderr


# -- 4/5/6. shell/git/file operations use project_root -------------------

def test_cli_exec_runs_with_project_root_as_cwd(tmp_path):
    project = make_git_project(tmp_path)
    (project / "marker.txt").write_text("found me\n")
    # Launch from tmp_path (unrelated to `project`) but point --project at it,
    # then run `exec cat marker.txt` through the REPL -- it should find the
    # file via project_root, not the launch directory.
    proc = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--project", str(project), "--fake-model"],
        input="exec cat marker.txt\nquit\n",
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "found me" in proc.stdout


def test_cli_diff_shows_project_repo_status(tmp_path):
    project = make_git_project(tmp_path)
    (project / "main.py").write_text("print('changed')\n")

    proc = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--project", str(project), "--fake-model"],
        input="diff\nquit\n",
        cwd=str(tmp_path),  # launched from an unrelated directory
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert "main.py" in proc.stdout


def test_cli_save_writes_inside_project_root_by_default(tmp_path):
    project = make_git_project(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--project", str(project), "--fake-model"],
        input="write a hello world\nsave out.py\nquit\n",
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert (project / "out.py").exists()


# -- launching from outside the PI-AI-CODER repo / install vs. workspace --

def test_cli_works_launched_from_outside_pi_ai_coder_repo(tmp_path):
    """#8/#9: application root (this repo) and project root (tmp_path) are
    unrelated, and the CLI must not silently operate on the repo."""
    assert not str(tmp_path).startswith(str(REPO_ROOT))
    project = make_git_project(tmp_path)
    result = run_cli(["--fake-model", "-q", "hello"], cwd=project)
    assert result.returncode == 0, result.stderr
    assert "hello from the fake model" in result.stdout


# -- 7. session state isolated between two projects (TUI, in-process) ----

@pytest.mark.asyncio
async def test_session_state_isolated_between_two_projects(tmp_path):
    from pi_ai_coder.config import AppConfig
    from pi_ai_coder.tui.app import PiAiCoderApp

    project_a = make_git_project(tmp_path, "project-a")
    project_b = make_git_project(tmp_path, "project-b")

    app_a = PiAiCoderApp(project_root=str(project_a), config=AppConfig(), fake_model=True)
    async with app_a.run_test():
        app_a.service.add_context_files([str(project_a / "main.py")])
        app_a._save_session()

    app_b = PiAiCoderApp(project_root=str(project_b), config=AppConfig(), fake_model=True)
    async with app_b.run_test():
        assert app_b.session.context_files == []  # did not inherit project A's context

    # project A's session file only exists under project A
    assert (project_a / ".pi-ai-coder" / "session.json").exists()
    assert not (project_b / ".pi-ai-coder" / "session.json").exists()

    data = json.loads((project_a / ".pi-ai-coder" / "session.json").read_text())
    assert data["context_files"] == [str(project_a / "main.py")]


# -- 10. fake-model TUI can launch against a temporary external project --

@pytest.mark.asyncio
async def test_tui_launches_against_external_project_with_fake_model(tmp_path):
    from pi_ai_coder.config import AppConfig
    from pi_ai_coder.tools.git import GitTool
    from pi_ai_coder.tui.app import PiAiCoderApp
    from pi_ai_coder.tui.widgets import ConversationView, ProjectTree

    project = make_git_project(tmp_path)
    (project / "notes.md").write_text("# notes\n")

    app = PiAiCoderApp(project_root=str(project), config=AppConfig(), fake_model=True)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.project_root == project.resolve()
        assert Path(app.query_one(ProjectTree).path) == project.resolve()
        assert isinstance(app.git_tool, GitTool)
        assert app.git_tool.current_branch() is not None
        assert app.query_one(ConversationView) is not None
        assert app.shell_tool.cwd == str(project.resolve())
        assert app.file_tool.project_root == str(project.resolve())
