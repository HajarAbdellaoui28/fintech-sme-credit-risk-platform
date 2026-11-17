"""Actual DVC cache/remote/reproduction round trip on disposable data, without ML."""

import os
import subprocess
import sys


def test_dvc_round_trip_and_noop_reproduction(tmp_path_factory):
    # DVC run-cache paths contain two long hashes; keep below Windows MAX_PATH.
    tmp_path = tmp_path_factory.mktemp("dvc")
    repository = tmp_path / "repository"
    repository.mkdir(mode=0o700)
    remote = tmp_path / "remote"
    remote.mkdir(mode=0o700)
    env = {**os.environ, "DVC_NO_ANALYTICS": "1", "DO_NOT_TRACK": "1"}
    for key, folder in [
        ("DVC_SITE_CACHE_DIR", "state"),
        ("DVC_GLOBAL_CONFIG_DIR", "global-config"),
        ("DVC_SYSTEM_CONFIG_DIR", "system-config"),
    ]:
        directory = tmp_path / folder
        directory.mkdir(mode=0o700)
        if os.name == "posix":
            assert directory.stat().st_mode & 0o077 == 0
        env[key] = str(directory)

    def dvc(*arguments):
        result = subprocess.run(
            [sys.executable, "-m", "dvc", *arguments],
            cwd=repository,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout

    dvc("init", "--no-scm")
    dvc("config", "cache.dir", str(repository / ".dvc/cache"))
    dvc("config", "cache.type", "copy")
    dvc("remote", "add", "--default", "local", str(remote))
    source = repository / "input.txt"
    source.write_text("DVC cache round trip, no financial data or ML\n", encoding="utf-8")
    (repository / "copy_stage.py").write_text(
        "from pathlib import Path\nPath('result.txt').write_bytes(Path('input.txt').read_bytes())\n",
        encoding="utf-8",
    )
    dvc("add", "input.txt")
    dvc(
        "stage",
        "add",
        "--name",
        "copy",
        "--deps",
        "input.txt",
        "--deps",
        "copy_stage.py",
        "--outs",
        "result.txt",
        sys.executable,
        "copy_stage.py",
    )
    dvc("repro")
    lock = (repository / "dvc.lock").read_bytes()
    expected = source.read_bytes()
    dvc("push")
    source.unlink()  # Exact temporary test file only; never touches project data.
    (repository / "result.txt").unlink()
    # Purge only these known object files so pull must retrieve them from the remote.
    objects = repository / ".dvc/cache/files/md5"
    assert list(objects.glob("*/*")), "Expected disposable local cache objects"
    for item in objects.glob("*/*"):
        if item.is_file():
            item.chmod(0o600)
            item.unlink()
    dvc("pull")
    assert source.read_bytes() == (repository / "result.txt").read_bytes() == expected
    dvc("repro")
    assert (repository / "dvc.lock").read_bytes() == lock
    assert dvc("status", "--json").strip() == "{}"
