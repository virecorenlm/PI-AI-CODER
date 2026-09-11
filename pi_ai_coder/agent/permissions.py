"""Risk classification for agent tool calls.

Static, per-tool risk (READ/WRITE) covers most tools. Shell commands are
special: the same tool (``run_command``/``run_tests``) can be perfectly
routine (``pytest -q``) or genuinely destructive (``rm -rf .``) depending on
the argument, so their risk is classified dynamically by pattern-matching
the command string. This is a denylist of *examples*, not an exhaustive
list -- CLAUDE.md is explicit that arbitrary shell commands are inherently
EXECUTE-risk, and this only escalates the obviously dangerous ones to
DESTRUCTIVE (requiring approval) on top of that.
"""

from __future__ import annotations

import re

from pi_ai_coder.tools.base import RiskLevel

# Patterns are matched case-insensitively against the full command string.
_DESTRUCTIVE_PATTERNS = [
    r"\brm\s+.*-[a-z]*r[a-z]*f",     # rm -rf, rm -fr, rm -Rf ...
    r"\brm\s+.*-[a-z]*f[a-z]*r",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-z]*f",
    r"\bgit\s+push\b.*(--force|-f\b)",
    r"\bgit\s+push\b(?!.*--dry-run)",
    r"\bgit\s+commit\b",
    r"\bgit\s+rebase\b",
    r"\bgit\s+merge\b",
    r"\bgit\s+checkout\s+--\s",
    r"\bgit\s+restore\b",
    r"\bdrop\s+(table|database)\b",
    r"\btruncate\s+table\b",
    r"\bmkfs(\.\w+)?\b",
    r"\bdd\s+if=",
    r">\s*/dev/(sd|nvme|hd)",
    r"\bchmod\s+-R\s+000\b",
    r":\(\)\s*\{.*:\|:.*\}\s*;\s*:",   # classic fork bomb
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bsudo\b",
    r"\bmv\s+.*\s+/dev/null\b",
    r"\bcurl\b.*\|\s*(sh|bash)\b",
    r"\bwget\b.*\|\s*(sh|bash)\b",
]

_DESTRUCTIVE_RE = re.compile("|".join(_DESTRUCTIVE_PATTERNS), re.IGNORECASE)


def classify_command(command: str) -> RiskLevel:
    """Classify a shell command string as EXECUTE (routine) or DESTRUCTIVE
    (needs explicit approval before running)."""
    if not command:
        return RiskLevel.EXECUTE
    if _DESTRUCTIVE_RE.search(command):
        return RiskLevel.DESTRUCTIVE
    return RiskLevel.EXECUTE


# Static per-tool risk. run_command/run_tests are intentionally absent --
# their risk is always determined dynamically via classify_command().
TOOL_RISK = {
    "read_file": RiskLevel.READ,
    "read_file_range": RiskLevel.READ,
    "list_directory": RiskLevel.READ,
    "find_files": RiskLevel.READ,
    "search_code": RiskLevel.READ,
    "git_status": RiskLevel.READ,
    "git_diff": RiskLevel.READ,
    "write_file": RiskLevel.WRITE,
    "create_file": RiskLevel.WRITE,
    "apply_patch": RiskLevel.WRITE,
    "delete_file": RiskLevel.WRITE,
    "move_file": RiskLevel.WRITE,
}
