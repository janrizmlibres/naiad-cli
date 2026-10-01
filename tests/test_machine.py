"""The machine reading: what this machine has, read the way an operator would.

A fake `sysctl` on `PATH` and a fake proc directory stand in for the real ones,
because what the adapter does is run the programs an operator has and read the
files a system exposes. Unknown is a value, never an exception.
"""

import shutil

import pytest
from fake_machine import install_sysctl

from naiad.adapters.machine import Machine

GIB = 1 << 30


@pytest.fixture
def bin_dir(monkeypatch, tmp_path):
    directory = tmp_path / "bin"
    directory.mkdir()
    monkeypatch.setenv("PATH", str(directory))
    return directory


def test_total_memory_on_macos_is_what_sysctl_says(bin_dir):
    install_sysctl(bin_dir, memsize=32 * GIB)

    assert Machine(platform="darwin").total_memory() == 32 * GIB


def test_total_memory_on_macos_is_unknown_when_sysctl_fails(bin_dir):
    install_sysctl(bin_dir, memsize=None)

    assert Machine(platform="darwin").total_memory() is None


def test_total_memory_on_macos_is_unknown_without_sysctl(bin_dir):
    assert Machine(platform="darwin").total_memory() is None


def test_total_memory_on_linux_is_memtotal_from_meminfo(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "meminfo").write_text(
        "MemTotal:       16777216 kB\nMemFree:         1048576 kB\nMemAvailable:    8388608 kB\n"
    )

    assert Machine(platform="linux", proc=proc).total_memory() == 16 * GIB


def test_total_memory_on_linux_is_unknown_without_meminfo(tmp_path):
    assert Machine(platform="linux", proc=tmp_path / "proc").total_memory() is None


def test_total_memory_on_linux_is_unknown_when_meminfo_names_none(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "meminfo").write_text("MemFree:         1048576 kB\n")

    assert Machine(platform="linux", proc=proc).total_memory() is None


def test_total_memory_elsewhere_is_unknown(tmp_path):
    assert Machine(platform="win32", proc=tmp_path).total_memory() is None


# Memory strained: the operating system's own word on pressure, and unknown when
# it gives none.


@pytest.mark.parametrize(("level", "strained"), [(1, False), (2, True), (4, True)])
def test_memory_on_macos_is_strained_above_the_normal_pressure_level(bin_dir, level, strained):
    install_sysctl(bin_dir, pressure_level=level)

    assert Machine(platform="darwin").strained() is strained


def test_memory_on_macos_is_unknown_when_sysctl_gives_no_pressure_level(bin_dir):
    install_sysctl(bin_dir, memsize=32 * GIB)

    assert Machine(platform="darwin").strained() is None


def linux(tmp_path, *, pressure=None, meminfo=None):
    proc = tmp_path / "proc"
    proc.mkdir()
    if pressure is not None:
        (proc / "pressure").mkdir()
        (proc / "pressure" / "memory").write_text(pressure)
    if meminfo is not None:
        (proc / "meminfo").write_text(meminfo)
    return Machine(platform="linux", proc=proc)


def pressure(some_avg10):
    return (
        f"some avg10={some_avg10} avg60=0.50 avg300=0.10 total=123456\n"
        "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n"
    )


def meminfo(*, total_kib, available_kib):
    return f"MemTotal:       {total_kib} kB\nMemAvailable:   {available_kib} kB\n"


@pytest.mark.parametrize(("some_avg10", "strained"), [("10.00", False), ("10.01", True)])
def test_memory_on_linux_is_strained_when_the_pressure_file_says_above_ten(
    tmp_path, some_avg10, strained
):
    """The pressure file is read in preference, however much is available."""
    machine = linux(
        tmp_path,
        pressure=pressure(some_avg10),
        meminfo=meminfo(total_kib=16_000_000, available_kib=8_000_000),
    )

    assert machine.strained() is strained


@pytest.mark.parametrize(
    ("available_kib", "strained"), [(1_600_000, False), (1_599_999, True)]
)
def test_memory_on_linux_without_a_pressure_file_is_strained_below_a_tenth_available(
    tmp_path, available_kib, strained
):
    machine = linux(tmp_path, meminfo=meminfo(total_kib=16_000_000, available_kib=available_kib))

    assert machine.strained() is strained


def test_memory_on_linux_is_unknown_when_nothing_is_readable(tmp_path):
    assert linux(tmp_path).strained() is None


def test_memory_on_linux_is_unknown_when_meminfo_has_no_available_figure(tmp_path):
    machine = linux(tmp_path, meminfo="MemTotal:       16000000 kB\n")

    assert machine.strained() is None


def test_memory_elsewhere_is_unknown(tmp_path):
    assert Machine(platform="win32", proc=tmp_path).strained() is None


# Free disk: what the filesystem holding a path reports.


def test_free_disk_is_what_the_filesystem_reports(tmp_path):
    usage = shutil.disk_usage(tmp_path)

    disk = Machine().free_disk(tmp_path)

    assert disk is not None
    assert disk.total == usage.total
    assert abs(disk.free - usage.free) < GIB


def test_free_disk_for_a_path_not_made_yet_is_its_nearest_existing_directorys(tmp_path):
    """A Child's working tree may not exist until it starts; the volume it will
    land on is the one to ask."""
    disk = Machine().free_disk(tmp_path / "not" / "yet")

    assert disk is not None
    assert disk.total == shutil.disk_usage(tmp_path).total
