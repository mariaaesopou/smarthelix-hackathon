import subprocess
import sys

import pytest

from pipeline.cli import main


@pytest.mark.parametrize(
    ("outcome", "code"),
    [("ok", 0), ("retry", 75), ("permanent", 65), ("crash", 75)],
)
def test_outcome_maps_to_exit_code(outcome, code):
    assert main(["selftest", "--outcome", outcome]) == code


def test_bad_arguments_are_permanent():
    assert main(["selftest", "--outcome", "nonsense"]) == 65
    assert main(["no-such-job"]) == 65


def test_module_entrypoint_returns_the_code_to_the_os():
    # What the Node launcher actually does: start a process and read its exit code.
    r = subprocess.run([sys.executable, "-m", "pipeline", "selftest", "--outcome", "permanent"],
                       capture_output=True, text=True)
    assert r.returncode == 65
    assert "permanent failure" in r.stderr
