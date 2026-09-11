"""Regression test for a circular-import bug: pi_ai_coder.models.base needs
pi_ai_coder.core.events, and pi_ai_coder.core (via assistant_service) needs
pi_ai_coder.models.base. Whichever one is imported *first* in a fresh
process used to determine whether this worked, since pytest's own import
order happened to mask it. Run each import alone, in a fresh subprocess, to
make sure order doesn't matter.
"""

import subprocess
import sys

import pytest

IMPORT_STATEMENTS = [
    "import pi_ai_coder.models.base",
    "import pi_ai_coder.models",
    "import pi_ai_coder.core",
    "import pi_ai_coder.core.assistant_service",
    "from pi_ai_coder.models.base import Message, ModelConfig",
    "from pi_ai_coder.core import AssistantService",
    "from pi_ai_coder.models import create_provider",
]


@pytest.mark.parametrize("statement", IMPORT_STATEMENTS)
def test_module_imports_cleanly_as_first_import(statement):
    result = subprocess.run(
        [sys.executable, "-c", statement],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
