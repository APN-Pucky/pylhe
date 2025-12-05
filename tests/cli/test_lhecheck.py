import subprocess

import skhep_testdata


def test_lhecheck_good():
    # run the executable and capture output
    result = subprocess.run(
        [
            "./src/pylhe/cli/lhecheck.py",
            skhep_testdata.data_path("pylhe-testfile-whizard-3.1.4-eeWW.lhe"),
            "--onshell-abs",
            "1e-3",
        ],  # path to your executable
        check=False,
        capture_output=True,
        text=True,
    )
    # check return code
    assert result.returncode == 0
    assert result.stdout == ""
