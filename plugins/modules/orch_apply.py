# Copyright Red Hat
# SPDX-License-Identifier: Apache-2.0
# Author: Guillaume Abrioux <gabrioux@redhat.com>
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
#
# Vendored from:
#   https://github.com/ceph/cephadm-ansible/blob/fbe6eccd705ed203e5ce30a2cf33d9e77e98d4c9/plugins/modules/ceph_orch_apply.py
# Changes from upstream:
#   - module_utils import path rewritten to this collection's fully-qualified
#     namespace (ansible_collections.vexxhost.ceph.plugins.module_utils.common).
#   - retrieve_current_spec(): narrow `ceph orch ls` to the specific service and
#     robustly handle rc/empty/"No services reported" (run_command returns a
#     tuple, so the upstream `isinstance(out, str)` check never fired).
#   - change_required(): compare the desired spec as a SUBSET of the running
#     one, so cephadm's normalised additions (filter_logic, objectstore, status,
#     ...) don't make every run report "changed"; also tolerate falsy defaults
#     cephadm OMITS from the stored spec (e.g. `ssl: false`).

from __future__ import absolute_import, division, print_function
from typing import Any, List, Tuple, Dict
__metaclass__ = type

import datetime
import yaml

from ansible.module_utils.basic import AnsibleModule  # type: ignore
from ansible_collections.vexxhost.ceph.plugins.module_utils.common import exit_module, build_base_cmd_orch


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ceph_orch_apply
short_description: apply service spec
version_added: "2.9"
description:
    - apply a service spec
options:
    fsid:
        description:
            - the fsid of the Ceph cluster to interact with.
        required: false
    image:
        description:
            - The Ceph container image to use.
        required: false
    spec:
        description:
            - The service spec to apply
        required: true
author:
    - Guillaume Abrioux <gabrioux@redhat.com>
'''

EXAMPLES = '''
- name: apply osd spec
  ceph_orch_apply:
    spec: |
      service_type: osd
      service_id: osd
      placement:
        label: osds
      spec:
        data_devices:
          all: true
'''


def parse_spec(spec: str) -> Dict:
    """ parse spec string to yaml """
    yaml_spec = yaml.safe_load(spec)
    return yaml_spec


def retrieve_current_spec(module: AnsibleModule, expected_spec: Dict) -> Dict:
    """ retrieve the current config of the specific service """
    service: str = expected_spec["service_type"]
    cmd = build_base_cmd_orch(module)
    cmd.extend(['ls', service])
    # Narrow to the specific service so we compare against the right one.
    if expected_spec.get('service_name'):
        cmd.append(expected_spec['service_name'])
    elif expected_spec.get('service_id'):
        cmd.append('{}.{}'.format(service, expected_spec['service_id']))
    cmd.append('--format=yaml')

    rc, out, err = module.run_command(cmd)
    if rc != 0 or not out or not out.strip() or 'No services reported' in out:
        # service does not exist yet
        return {}
    parsed = yaml.safe_load(out)
    return parsed if isinstance(parsed, dict) else {}


def apply_spec(module: "AnsibleModule",
               data: str) -> Tuple[int, List[str], str, str]:
    cmd = build_base_cmd_orch(module)
    cmd.extend(['apply', '-i', '-'])
    rc, out, err = module.run_command(cmd, data=data)

    if rc:
        raise RuntimeError(err)

    return rc, cmd, out, err


def spec_satisfied(expected: Any, current: Any) -> bool:
    """ True if every value in `expected` is already satisfied by `current`
    (recursively). Two cephadm normalisations are tolerated so an
    already-applied spec does not read back as changed:
      * extra keys cephadm ADDS (status, events, service_name, ...) are ignored;
      * keys cephadm OMITS because they are falsy defaults (e.g. `ssl: false`)
        are treated as satisfied when our desired value is also falsy — only a
        truthy value that is missing/different counts as a real change.
    """
    if isinstance(expected, dict):
        if not isinstance(current, dict):
            return False
        for key, value in expected.items():
            if key in current:
                if not spec_satisfied(value, current[key]):
                    return False
            elif value:
                return False
        return True
    return expected == current


def change_required(current: Dict, expected: Dict) -> bool:
    """ checks if the current config already satisfies what is expected """
    if not current:
        return True
    return not spec_satisfied(expected, current)


def run_module() -> None:

    module_args = dict(
        spec=dict(type='str', required=True),
        fsid=dict(type='str', required=False),
        docker=dict(type=bool,
                    required=False,
                    default=False),
        image=dict(type='str', required=False)
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    startd = datetime.datetime.now()
    spec = module.params.get('spec')

    if module.check_mode:
        exit_module(
            module=module,
            out='',
            rc=0,
            cmd=[],
            err='',
            startd=startd,
            changed=False
        )

    # Idempotency check
    expected = parse_spec(module.params.get('spec'))
    current_spec = retrieve_current_spec(module, expected)

    if change_required(current_spec, expected):
        rc, cmd, out, err = apply_spec(module, spec)
        changed = True
    else:
        rc = 0
        cmd = []
        out = ''
        err = ''
        changed = False

    exit_module(
        module=module,
        out=out,
        rc=rc,
        cmd=cmd,
        err=err,
        startd=startd,
        changed=changed
    )


def main() -> None:
    run_module()


if __name__ == '__main__':
    main()
