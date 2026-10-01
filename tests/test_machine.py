"""The machine reading: what this machine has, read the way an operator would.

A fake `sysctl` on `PATH` and a fake proc directory stand in for the real ones,
because what the adapter does is run the programs an operator has and read the
files a system exposes. Unknown is a value, never an exception.
"""

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
