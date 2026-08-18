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
# Adapted from:
#   https://github.com/ceph/cephadm-ansible/blob/fbe6eccd705ed203e5ce30a2cf33d9e77e98d4c9/plugins/modules/ceph_orch_host.py
#
# Changes from upstream:
#   * module_utils import path rewritten to this collection's fully-qualified
#     namespace (ansible_collections.vexxhost.ceph.plugins.module_utils.common).
#   * state=present now reconciles the host `addr` as well as labels: if an
#     existing host's registered address differs from the requested one, run
#     `ceph orch host set-addr`. Upstream only ever set the addr at `host add`
#     time, so a host first registered by `cephadm bootstrap` (which stores the
#     short hostname as its addr) kept that addr forever — causing cephadm to
#     advertise monitoring targets (ceph-exporter scrape target, etc.) by an
#     unresolvable short hostname instead of the IP.

from __future__ import absolute_import, division, print_function
from typing import Optional, List, Tuple
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule  # type: ignore
from ansible_collections.vexxhost.ceph.plugins.module_utils.common import exit_module, build_base_cmd_orch
import datetime
import json


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ceph_orch_host
short_description: add/remove hosts
version_added: "2.9"
description:
    - Add or remove hosts from ceph orchestration.
options:
    fsid:
        description:
            - the fsid of the Ceph cluster to interact with.
        required: false
    name:
        description:
            - name of the host
        required: true
    image:
        description:
            - The Ceph container image to use.
        required: false
    address:
        description:
            - address of the host. Applied at host-add time and, for an already
              registered host, reconciled via `ceph orch host set-addr` whenever
              it differs from the host's current addr.
        required: true when state is present
    set_admin_label:
        description:
            - enforce '_admin' label on the host specified
              in 'name'
        required: false
        default: false
    labels:
        description:
            - list of labels to apply on the host
        required: false
        default: []
    state:
        description:
            - if set to 'present', it will ensure the name specified
              in 'name' will be present.
            - if set to 'absent', it will remove the host specified in
              'name'.
            - if set to 'drain', it will schedule to remove all daemons
              from the host specified in 'name'.
        required: false
        default: present
author:
    - Guillaume Abrioux <gabrioux@redhat.com>
'''

EXAMPLES = '''
- name: add a host
  ceph_orch_host:
    name: my-node-01
    address: 10.10.10.101

- name: add a host
  ceph_orch_host:
    name: my-node-02
    labels:
      - mon
      - mgr
      - grp013
    address: 10.10.10.102

- name: remove a host
  ceph_orch_host:
    name: my-node-01
    state: absent
'''


def get_current_state(module: "AnsibleModule") -> Tuple[int, List[str], str, str]:
    cmd = build_base_cmd_orch(module)
    cmd.extend(['host', 'ls', '--format', 'json'])
    rc, out, err = module.run_command(cmd)

    if rc:
        raise RuntimeError(err)

    return rc, cmd, out, err


def update_label(module: "AnsibleModule",
                 action: str,
                 host: str,
                 label: str = '') -> Tuple[int, List[str], str, str]:
    cmd = build_base_cmd_orch(module)
    cmd.extend(['host', 'label', action,
                host, label])
    rc, out, err = module.run_command(cmd)

    if rc:
        raise RuntimeError(err)

    return rc, cmd, out, err


def set_host_addr(module: "AnsibleModule",
                  host: str,
                  address: str) -> Tuple[int, List[str], str, str]:
    cmd = build_base_cmd_orch(module)
    cmd.extend(['host', 'set-addr', host, address])
    rc, out, err = module.run_command(cmd)

    if rc:
        raise RuntimeError(err)

    return rc, cmd, out, err


def update_host(module: "AnsibleModule",
                action: str,
                name: str,
                address: str = '',
                labels: Optional[List[str]] = None) -> Tuple[int, List[str], str, str]:
    cmd = build_base_cmd_orch(module)
    cmd.extend(['host', action, name])
    if action == 'add' and address:
        cmd.append(address)
    if labels:
        cmd.extend(["--labels", ",".join(labels)])
    rc, out, err = module.run_command(cmd)

    if rc:
        raise RuntimeError(err)

    return rc, cmd, out, err


def main() -> None:
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            address=dict(type='str', required=False),
            set_admin_label=dict(type=bool, required=False, default=False),
            labels=dict(type='list', required=False, default=[]),
            state=dict(type='str',
                       required=False,
                       choices=['present', 'absent', 'drain'],
                       default='present'),
            docker=dict(type=bool,
                        required=False,
                        default=False),
            fsid=dict(type='str', required=False),
            image=dict(type='str', required=False)
        ),
        supports_check_mode=True
    )
    run(module)


def run(module: AnsibleModule) -> None:
    name = module.params.get('name')
    address = module.params.get('address')
    set_admin_label = module.params.get('set_admin_label')
    labels = module.params.get('labels')
    state = module.params.get('state')
    if state == 'absent':
        state = 'rm'

    startd = datetime.datetime.now()
    changed = False

    cmd = ['cephadm']

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

    rc, cmd, out, err = get_current_state(module)
    current_state = json.loads(out)
    current_names = [name['hostname'] for name in current_state]

    if state == 'present':
        if set_admin_label and '_admin' not in labels:
            labels.append('_admin')
        if name in current_names:
            current_state_host = [host for host in current_state if host['hostname'] == name][0]
            _out = []

            # Reconcile the address: cephadm only records it at `host add` time,
            # so an existing host (e.g. added by bootstrap with its short hostname
            # as addr) is corrected here to the requested address.
            if address and current_state_host.get('addr') != address:
                rc, cmd, out, err = set_host_addr(module, name, address)
                _out.append(f"addr={address}")

            # Reconcile labels (symmetric diff: add missing, remove extras).
            differences = set(labels) ^ set(current_state_host['labels'])
            for diff in differences:
                if diff in current_state_host['labels']:
                    action = 'rm'
                else:
                    action = 'add'
                rc, cmd, out, err = update_label(module, action, current_state_host['hostname'], diff)
                _out.append(f"label:{diff}")

            if _out:
                exit_module(rc=rc,
                            startd=startd,
                            module=module,
                            cmd=cmd,
                            out=f"Host updated: {', '.join(_out)}",
                            err=err,
                            changed=True)
            out = '{} is already present, skipping.'.format(name)
        else:
            rc, cmd, out, err = update_host(module, 'add', name, address, labels)
            if not rc:
                changed = True

    if state in ['rm', 'drain']:
        if name not in current_names:
            out = '{} is not present, skipping.'.format(name)
        else:
            rc, cmd, out, err = update_host(module, state, name)
            changed = True

    exit_module(
        module=module,
        out=out,
        rc=rc,
        cmd=cmd,
        err=err,
        startd=startd,
        changed=changed
    )


if __name__ == '__main__':
    main()
