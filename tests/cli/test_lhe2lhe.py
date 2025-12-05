import subprocess

import skhep_testdata


def test_lhe2lhe_lhefilter_same():
    file = skhep_testdata.data_path("pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz")
    # First process: echo "hi "
    p1 = subprocess.Popen(["./src/pylhe/cli/lhe2lhe.py", file], stdout=subprocess.PIPE)

    # Second process: cat (reads from p1)
    p2 = subprocess.Popen(
        ["./src/pylhe/cli/lhe2lhe.py"],
        stdin=p1.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )

    p1.stdout.close()  # Allow p1 to receive SIGPIPE if p2 exits
    output, _ = p2.communicate()

    p3 = subprocess.Popen(
        ["./src/pylhe/cli/lhe2lhe.py", file], stdout=subprocess.PIPE, text=True
    )
    out, _ = p3.communicate()

    # check all three outputs are the same
    assert output == out
    # check exit codes are zero
    # assert p1.returncode == 0
    assert p2.returncode == 0
    assert p3.returncode == 0


def test_lhe2lhe_lhe2lhe_same():
    file = skhep_testdata.data_path("pylhe-testfile-madgraph-2.2.1-Z-ckkwl.lhe.gz")
    # First process: echo "hi "
    p1 = subprocess.Popen(["./src/pylhe/cli/lhe2lhe.py", file], stdout=subprocess.PIPE)

    # Second process: cat (reads from p1)
    p2 = subprocess.Popen(
        ["./src/pylhe/cli/lhefilter.py", "--event", "2"],
        stdin=p1.stdout,
        stdout=subprocess.PIPE,
        text=True,
    )

    p1.stdout.close()  # Allow p1 to receive SIGPIPE if p2 exits
    output, _ = p2.communicate()

    p3 = subprocess.Popen(
        [
            "./src/pylhe/cli/lhefilter.py",
            file,
            "--event",
            "2",
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    out, _ = p3.communicate()

    # check all three outputs are the same
    assert output == out
    # check exit codes are zero
    # assert p1.returncode == 0
    assert p2.returncode == 0
    assert p3.returncode == 0
