"""Session-wide configuration for the differential suite.

Prints the number of differential comparisons performed per channel at the end
of the run, so the suite can evidence how many generated cases it exercised.
"""

from . import compare


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    counts = compare.COUNTS
    terminalreporter.write_sep("=", "differential comparison counts")
    terminalreporter.write_line(
        "parse comparisons:   %d" % counts["parse"]
    )
    terminalreporter.write_line(
        "unparse comparisons: %d" % counts["unparse"]
    )
    terminalreporter.write_line(
        "cli comparisons:     %d" % counts["cli"]
    )
