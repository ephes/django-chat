"""Exercise deployment selection with real Ansible and harmless fixture roles."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    ("group", "mode", "provisioned", "active", "success", "expected"),
    [
        ("staging", None, True, True, True, {"uv_install", "wagtail_deploy"}),
        (
            "production",
            "standalone",
            False,
            False,
            True,
            {"baseline", "uv_install", "traefik_deploy", "wagtail_deploy"},
        ),
        ("staging", "standalone", True, True, False, set()),
        ("production", "typo", True, True, False, set()),
        ("staging", None, False, True, False, set()),
        ("staging", None, True, False, False, set()),
    ],
)
def test_proxy_ownership_selection(
    tmp_path: Path,
    group: str,
    mode: str | None,
    provisioned: bool,
    active: bool,
    success: bool,
    expected: set[str],
) -> None:
    executable = shutil.which("ansible-playbook")
    assert executable is not None, "Run uv sync to install the ansible-core dev dependency"
    original = yaml.safe_load((ROOT / "deploy/deploy.yml").read_text())[0]
    defaults = yaml.safe_load((ROOT / "deploy/group_vars/django_chat.yml").read_text())
    markers = tmp_path / "markers"
    markers.mkdir()
    collection = tmp_path / "collections/ansible_collections/local/ops_library/roles"
    for role in ["uv_install", "traefik_deploy", "wagtail_deploy"]:
        tasks = collection / role / "tasks"
        tasks.mkdir(parents=True)
        (tasks / "main.yml").write_text(
            yaml.safe_dump(
                [{"ansible.builtin.file": {"path": str(markers / role), "state": "touch"}}]
            )
        )
    binary = tmp_path / "traefik"
    routes = tmp_path / "dynamic"
    if provisioned:
        binary.write_text("#!/bin/sh\nexit 0\n")
        binary.chmod(0o700)
        routes.mkdir()
    commands = tmp_path / "bin"
    commands.mkdir()
    systemctl = commands / "systemctl"
    systemctl.write_text(f"#!/bin/sh\nexit {0 if active else 3}\n")
    systemctl.chmod(0o700)
    baseline = tmp_path / "baseline.yml"
    baseline.write_text(
        yaml.safe_dump(
            [{"ansible.builtin.file": {"path": str(markers / "baseline"), "state": "touch"}}]
        )
    )
    preflight = dict(original["pre_tasks"][0])
    preflight["ansible.builtin.import_tasks"] = str(ROOT / "deploy/tasks/proxy-preflight.yml")
    baseline_task = next(
        dict(task)
        for task in original["pre_tasks"]
        if task["name"] == "Deploy | Run clean-VPS baseline tasks"
    )
    baseline_task["ansible.builtin.import_tasks"] = str(baseline)
    variables = {
        "django_chat_host_mode": mode or defaults["django_chat_host_mode"],
        "traefik_binary_path": str(binary),
        "traefik_dynamic_dir": str(routes),
        # Even a caller requesting a force-update must never run the full role
        # in shared mode.
        "traefik_force_update": True,
        "ansible_python_interpreter": sys.executable,
    }
    playbook = tmp_path / "play.yml"
    playbook.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": "fixture",
                    "gather_facts": False,
                    "vars": variables,
                    "environment": {"PATH": f"{commands}:{os.environ['PATH']}"},
                    "pre_tasks": [preflight, baseline_task],
                    "roles": original["roles"],
                }
            ]
        )
    )
    inventory = tmp_path / "hosts.ini"
    inventory.write_text(f"[{group}]\nfixture ansible_connection=local\n")
    result = subprocess.run(
        [executable, "-i", str(inventory), str(playbook)],
        cwd=tmp_path,
        env={
            **os.environ,
            "ANSIBLE_COLLECTIONS_PATH": str(tmp_path / "collections"),
            "ANSIBLE_LOCAL_TEMP": str(tmp_path / "ansible-tmp"),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert (result.returncode == 0) == success, result.stdout + result.stderr
    assert {p.name for p in markers.iterdir()} == expected, result.stdout


def test_bootstrap_requires_standalone_before_mutations() -> None:
    play = yaml.safe_load((ROOT / "deploy/bootstrap.yml").read_text())[0]
    assertions = play["tasks"][0]["ansible.builtin.assert"]["that"]
    assert "django_chat_host_mode == 'standalone'" in assertions
    assert "'staging' not in group_names" in assertions
    assert play["tasks"][1]["ansible.builtin.import_tasks"] == "tasks/proxy-preflight.yml"


def test_staging_defaults_to_shared_proxy() -> None:
    variables = yaml.safe_load((ROOT / "deploy/group_vars/staging.yml").read_text())
    assert variables["django_chat_host_mode"] == "shared"
