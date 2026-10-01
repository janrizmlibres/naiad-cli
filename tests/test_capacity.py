"""The ceiling: how many Runs may be live at once, resolved once when the
Supervisor starts. The nearest instruction wins — the option, then the
environment variable, then what the machine's memory allows."""

import pytest
from fake_machine import install_sysctl

from naiad.adapters.machine import Machine
from naiad.domain.capacity import (
    GB,
    CapacityError,
    Disk,
    ceiling_for,
    low_on_disk,
    resolve_ceiling,
)

GIB = 1 << 30


@pytest.mark.parametrize(
    ("gibibytes", "ceiling"),
    [(8, 1), (16, 5), (32, 16), (64, 37)],
)
def test_the_ceiling_derived_from_memory_read_off_the_machine(
    monkeypatch, tmp_path, gibibytes, ceiling
):
    """max(1, ⌊(total memory − 8 GiB) ÷ 1.5 GiB⌋)."""
    monkeypatch.setenv("PATH", str(tmp_path))
    install_sysctl(tmp_path, memsize=gibibytes * GIB)

    assert ceiling_for(Machine(platform="darwin").total_memory()) == ceiling


def test_less_than_the_reserve_still_allows_one():
    assert ceiling_for(4 * GIB) == 1


def test_unknown_memory_allows_one():
    """A machine that cannot say what it has is sized as the smallest."""
    assert ceiling_for(None) == 1


def never_read():
    raise AssertionError("the machine was read although the ceiling was given")


def test_the_option_beats_the_environment_variable():
    assert resolve_ceiling(option=3, variable="20", total_memory=never_read) == 3


def test_the_environment_variable_beats_the_derived_ceiling():
    assert resolve_ceiling(option=None, variable="20", total_memory=never_read) == 20


def test_with_neither_the_ceiling_is_derived_from_memory():
    assert resolve_ceiling(option=None, variable=None, total_memory=lambda: 32 * GIB) == 16


@pytest.mark.parametrize("variable", ["0", "-2", "abc", "2.5", "", " 3", "2_0"])
def test_an_environment_variable_that_is_not_a_positive_whole_number_is_refused(variable):
    with pytest.raises(CapacityError) as refused:
        resolve_ceiling(option=None, variable=variable, total_memory=never_read)

    assert "NAIAD_CAPACITY" in str(refused.value)


# The free-disk floor: the larger of a tenth of the volume and 10 GB.


@pytest.mark.parametrize(
    ("total", "free", "low"),
    [
        (50 * GB, 10 * GB, False),
        (50 * GB, 10 * GB - 1, True),
        (1000 * GB, 100 * GB, False),
        (1000 * GB, 100 * GB - 1, True),
    ],
)
def test_disk_is_low_below_the_larger_of_a_tenth_and_ten_gigabytes(total, free, low):
    assert low_on_disk(Disk(free=free, total=total)) is low


def test_an_unreadable_disk_is_not_low():
    assert low_on_disk(None) is False
