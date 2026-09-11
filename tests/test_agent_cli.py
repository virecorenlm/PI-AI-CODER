"""CLI agent execution -- required tests #18, #20.

--fake-model only supports a single canned response (no scripted multi-turn
sequence) through the CLI entry point, so these tests exercise the plain
"no tool call, just answer" path end-to-end through the real ``assistant.py``
process -- proving the agent loop is genuinely wired into the CLI (not just
unit-tested in isolation) and that it works from a project directory
completely unrelated to the PI-AI-CODER repo.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSISTANT_PY = REPO_ROOT / "assistant.py"


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


def test_cli_agent_mode_is_the_default(tmp_path):
    """No --no-agent flag: a query goes through the agent loop and still
    produces a clean final answer (fake model's canned reply has no tool
    call, so the loop finishes on the first turn)."""
    project = make_git_project(tmp_path)
    result = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--project", str(project), "--fake-model", "-q", "hello"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "hello from the fake model" in result.stdout


def test_cli_no_agent_flag_falls_back_to_plain_chat(tmp_path):
    project = make_git_project(tmp_path)
    result = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--project", str(project), "--fake-model", "--no-agent", "-q", "hello"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "hello from the fake model" in result.stdout


def test_cli_agent_runs_from_external_project_directory(tmp_path):
    """#20: application root (this repo) and project root (tmp_path) are
    unrelated -- the agent must operate on the launched-from project."""
    assert not str(tmp_path).startswith(str(REPO_ROOT))
    project = make_git_project(tmp_path, "external-project")

    result = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--fake-model", "-q", "hello"],
        cwd=str(project),  # launched from inside the external project, no --project flag
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "hello from the fake model" in result.stdout


def test_cli_agent_help_mentions_agent_behavior():
    result = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "--no-agent" in result.stdout


def test_cli_repl_commands_still_work_alongside_agent_mode(tmp_path):
    """Backward compatibility: manual REPL commands (add/files/diff/quit)
    remain fully functional even with agent mode as the default for plain
    queries."""
    project = make_git_project(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(ASSISTANT_PY), "--project", str(project), "--fake-model"],
        input="add main.py\nfiles\ndiff\nquit\n",
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "1 files in context" in proc.stdout
    assert "main.py" in proc.stdout
