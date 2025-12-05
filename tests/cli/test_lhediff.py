import subprocess

import skhep_testdata


def test_lhediff_same_file():
    # run the executable and capture output
    result = subprocess.run(
        [
            "./src/pylhe/cli/lhediff.py",
            skhep_testdata.data_path("pylhe-testfile-pr29.lhe"),
            skhep_testdata.data_path("pylhe-testfile-pr29.lhe"),
        ],  # path to your executable
        check=False,
        capture_output=True,
        text=True,
    )
    # check return code
    assert result.returncode == 0
    assert result.stdout == ""


def test_lhediff_different_file():
    # run the executable and capture output
    result = subprocess.run(
        [
            "./src/pylhe/cli/lhediff.py",
            skhep_testdata.data_path("pylhe-testfile-pr29.lhe"),
            skhep_testdata.data_path("pylhe-testlhef3.lhe"),
        ],  # path to your executable
        check=False,
        capture_output=True,
        text=True,
    )
    # check return code
    assert result.returncode == 1
    assert result.stdout != ""
