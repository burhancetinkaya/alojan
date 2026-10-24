"""Carrier launch defaults must preserve native caller-number normalization."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("override,expected", [(None, "0"), ("none", "none")])
def test_netgsm_launcher_sets_national_number_policy(tmp_path, override, expected):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    source = Path(__file__).resolve().parents[1] / "scripts/run-netgsm.sh"
    shutil.copyfile(source, scripts / source.name)
    private = tmp_path / ".local"
    private.mkdir()
    settings = (
        "ALOJAN_SIP_BIND=127.0.0.1\n"
        "ALOJAN_SIP_PUBLIC=127.0.0.1\n"
        "ALOJAN_SIP_SOURCE=192.0.2.10\n"
        "ALOJAN_VOICE_PROFILE=agent\n"
    )
    if override:
        settings += f"ALOJAN_CALLER_NATIONAL_PREFIX={override}\n"
    (private / "netgsm.env").write_text(settings)
    binary = tmp_path / "build/local/voice-gateway"
    binary.parent.mkdir(parents=True)
    binary.write_text(f"#!{sys.executable}\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n")
    binary.chmod(0o700)
    env = {key: value for key, value in os.environ.items() if not key.startswith("ALOJAN_")}
    result = subprocess.run(
        ["sh", str(scripts / source.name)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    args = json.loads(result.stdout)
    flags = dict(zip(args[::2], args[1::2], strict=True))
    assert flags["--caller-national-prefix"] == expected
    assert flags["--trusted-identity-ip"] == flags["--allow-sip-ip"] == "192.0.2.10"
    assert flags["--answer-delay-ms"] == "3000"
    assert flags["--agent-port"] == "15073"
