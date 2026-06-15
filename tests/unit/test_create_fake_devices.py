from pathlib import Path

import yaml


def test_logical_volume_task_does_not_use_invocation_metadata():
    playbook = yaml.safe_load(Path("playbooks/create_fake_devices.yml").read_text())
    tasks = playbook[0]["tasks"]

    lvol_task = next(
        task
        for task in tasks
        if task.get("name") == "Create a logical volume for each loop device"
    )

    assert "invocation" not in str(lvol_task)
    assert lvol_task["loop"] == "{{ ceph_osds }}"
    assert lvol_task["community.general.lvol"]["vg"] == (
        "ceph-{{ inventory_hostname_short }}-{{ item }}"
    )
    assert lvol_task["loop_control"]["label"] == (
        "ceph-{{ inventory_hostname_short }}-{{ item }}"
    )
