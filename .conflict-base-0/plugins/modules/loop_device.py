#!/usr/bin/python3

# Copyright (c) 2023 VEXXHOST, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from ansible.module_utils.basic import AnsibleModule


def lookup_loopdev(module, path):
    # Get list of all the loop devices
    loopdevs = []
    _, out, _ = module.run_command(["losetup", "-J"], check_rc=True)
    if out:
        loopdevs = json.loads(out).get("loopdevices", [])

    # Check if the path is already attached
    for loopdev in loopdevs:
        if loopdev.get("back-file") == path:
            return loopdev

    return None


def run_module():
    module_args = dict(
        state=dict(type="str", required=True, choices=["present", "absent"]),
        path=dict(type="str", required=True),
    )

    module = AnsibleModule(argument_spec=module_args)

    state = module.params["state"]
    path = module.params["path"]

    # Lookup the loop device
    loopdev = lookup_loopdev(module, path)

    if state == "present":
        if loopdev:
            module.exit_json(changed=False, loopdev=loopdev)

        module.run_command(["losetup", "-fP", path], check_rc=True)
        loopdev = lookup_loopdev(module, path)
        module.exit_json(changed=True, loopdev=loopdev)

    if state == "absent":
        if not loopdev:
            module.exit_json(changed=False)

        module.run_command(["losetup", "-d", loopdev.get("name")], check_rc=True)
        module.exit_json(changed=True)


def main():
    run_module()


if __name__ == "__main__":
    main()
