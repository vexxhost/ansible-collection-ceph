# Copyright 2020, Red Hat, Inc.
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

# ---------------------------------------------------------------------------
# Vendored from:
#   https://github.com/ceph/ceph-ansible/blob/8599b192d33e1c55104c1c2fd1abfa8431c64664/library/radosgw_realm.py
# Changes from upstream:
#   - local container_exec() reworked to run via `cephadm shell` (with --fsid/--config from CEPHADM_FSID/CEPHADM_CONFIG) instead of `docker/podman run --entrypoint`
#   - is_containerized() reads CEPHADM_IMAGE (dropped legacy CEPH_CONTAINER_IMAGE)
#   - pre_generate_radosgw_cmd() always wraps radosgw-admin in `cephadm shell` (never bare on the host)
# The upstream copyright/license header above is retained unmodified.
# ---------------------------------------------------------------------------

from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.basic import AnsibleModule
import datetime
import os


ANSIBLE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: radosgw_realm

short_description: Manage RADOS Gateway Realm

version_added: "2.8"

description:
    - Manage RADOS Gateway realm(s) creation, deletion and updates.
options:
    cluster:
        description:
            - The ceph cluster name.
        required: false
        default: ceph
    name:
        description:
            - name of the RADOS Gateway realm.
        required: true
    state:
        description:
            If 'present' is used, the module creates a realm if it doesn't
            exist or update it if it already exists.
            If 'absent' is used, the module will simply delete the realm.
            If 'info' is used, the module will return all details about the
            existing realm (json formatted).
        required: false
        choices: ['present', 'absent', 'info']
        default: present
    default:
        description:
            - set the default flag on the realm.
        required: false
        default: false
    url:
        description:
            - URL to the master RADOS Gateway zone.
        required: false
    access_key:
        description:
            - S3 access key of the master RADOS Gateway zone.
        required: false
    secret_key:
        description:
            - S3 secret key of the master RADOS Gateway zone.
        required: false

author:
    - Dimitri Savineau <dsavinea@redhat.com>
'''

EXAMPLES = '''
- name: create a RADOS Gateway default realm
  radosgw_realm:
    name: foo
    default: true

- name: get a RADOS Gateway realm information
  radosgw_realm:
    name: foo
    state: info

- name: delete a RADOS Gateway realm
  radosgw_realm:
    name: foo
    state: absent
'''

RETURN = '''#  '''


def container_exec(binary, container_image, container_args=None):
    """
    Build a `cephadm shell -- <binary>` prefix (cephadm-shell model).

    Any legacy `docker run` bind-mounts passed via container_args as
    `-v host:container[:opts]` pairs are translated into `cephadm shell
    --mount host:container` so e.g. `radosgw-admin zone set --infile=` can read
    a host file inside the ephemeral shell container.
    """
    cmd = ['cephadm']
    if container_image:
        cmd.extend(['--image', container_image])
    # Bound the shell so a hung call fails the task (see stackhpc.cephadm).
    cmd.extend(['--timeout', os.environ.get('CEPHADM_TIMEOUT', '120')])
    cmd.append('shell')
    # Pass --fsid/--config from the env (matching the shared shell builders) so
    # cephadm skips cluster/config discovery -- radosgw-admin calls are ~5x faster.
    _fsid = os.environ.get('CEPHADM_FSID')
    if _fsid:
        cmd.extend(['--fsid', _fsid])
    _config = os.environ.get('CEPHADM_CONFIG')
    if _config:
        cmd.extend(['--config', _config])
    if container_args:
        i = 0
        while i < len(container_args):
            if container_args[i] == '-v' and i + 1 < len(container_args):
                spec = ':'.join(container_args[i + 1].split(':')[:2])
                cmd.extend(['--mount', spec])
                i += 2
            else:
                i += 1
    cmd.extend(['--', binary])
    return cmd


def is_containerized():
    """
    Container image for the `cephadm shell` (CEPHADM_IMAGE env, or None).
    The legacy CEPH_CONTAINER_IMAGE / CEPH_CONTAINER_BINARY model is not used.
    """
    return os.environ.get('CEPHADM_IMAGE') or None


def pre_generate_radosgw_cmd(container_image=None):
    '''
    Generate radosgw-admin prefix comaand
    '''
    cmd = container_exec('radosgw-admin', container_image)

    return cmd


def generate_radosgw_cmd(cluster, args, container_image=None):
    '''
    Generate 'radosgw' command line to execute
    '''

    cmd = pre_generate_radosgw_cmd(container_image=container_image)

    base_cmd = [
        '--cluster',
        cluster,
        'realm'
    ]

    cmd.extend(base_cmd + args)

    return cmd


def exec_commands(module, cmd):
    '''
    Execute command(s)
    '''

    rc, out, err = module.run_command(cmd)

    return rc, cmd, out, err


def create_realm(module, container_image=None):
    '''
    Create a new realm
    '''

    cluster = module.params.get('cluster')
    name = module.params.get('name')
    default = module.params.get('default', False)

    args = ['create', '--rgw-realm=' + name]

    if default:
        args.append('--default')

    cmd = generate_radosgw_cmd(cluster=cluster,
                               args=args,
                               container_image=container_image)

    return cmd


def get_realm(module, container_image=None):
    '''
    Get existing realm
    '''

    cluster = module.params.get('cluster')
    name = module.params.get('name')

    args = ['get', '--rgw-realm=' + name, '--format=json']

    cmd = generate_radosgw_cmd(cluster=cluster,
                               args=args,
                               container_image=container_image)

    return cmd


def remove_realm(module, container_image=None):
    '''
    Remove a realm
    '''

    cluster = module.params.get('cluster')
    name = module.params.get('name')

    args = ['delete', '--rgw-realm=' + name]

    cmd = generate_radosgw_cmd(cluster=cluster,
                               args=args,
                               container_image=container_image)

    return cmd


def pull_realm(module, container_image=None):
    '''
    Pull a realm
    '''

    cluster = module.params.get('cluster')
    name = module.params.get('name')
    url = module.params.get('url')
    access_key = module.params.get('access_key')
    secret_key = module.params.get('secret_key')
    default = module.params.get('default', False)

    args = [
        'pull',
        '--rgw-realm=' + name,
        '--url=' + url,
        '--access-key=' + access_key,
        '--secret=' + secret_key
    ]
    if default:
        args.append('--default')

    cmd = generate_radosgw_cmd(cluster=cluster,
                               args=args,
                               container_image=container_image)

    return cmd


def exit_module(module, out, rc, cmd, err, startd, changed=False):
    endd = datetime.datetime.now()
    delta = endd - startd

    result = dict(
        cmd=cmd,
        start=str(startd),
        end=str(endd),
        delta=str(delta),
        rc=rc,
        stdout=out.rstrip("\r\n"),
        stderr=err.rstrip("\r\n"),
        changed=changed,
    )
    module.exit_json(**result)


def run_module():
    module_args = dict(
        cluster=dict(type='str', required=False, default='ceph'),
        name=dict(type='str', required=True),
        state=dict(type='str', required=False, choices=['present', 'absent', 'info', 'pull'], default='present'),  # noqa: E501
        default=dict(type='bool', required=False, default=False),
        url=dict(type='str', required=False),
        access_key=dict(type='str', required=False),
        secret_key=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[['state', 'pull', ['url', 'access_key', 'secret_key']]],
    )

    # Gather module parameters in variables
    name = module.params.get('name')
    state = module.params.get('state')

    if module.check_mode:
        module.exit_json(
            changed=False,
            stdout='',
            stderr='',
            rc=0,
            start='',
            end='',
            delta='',
        )

    startd = datetime.datetime.now()
    changed = False

    # will return either the image name or None
    container_image = is_containerized()

    if state == "present":
        rc, cmd, out, err = exec_commands(module, get_realm(module, container_image=container_image))  # noqa: E501
        if rc != 0:
            rc, cmd, out, err = exec_commands(module, create_realm(module, container_image=container_image))  # noqa: E501
            changed = True

    elif state == "absent":
        rc, cmd, out, err = exec_commands(module, get_realm(module, container_image=container_image))  # noqa: E501
        if rc == 0:
            rc, cmd, out, err = exec_commands(module, remove_realm(module, container_image=container_image))  # noqa: E501
            changed = True
        else:
            rc = 0
            out = "Realm {} doesn't exist".format(name)

    elif state == "info":
        rc, cmd, out, err = exec_commands(module, get_realm(module, container_image=container_image))  # noqa: E501

    elif state == "pull":
        rc, cmd, out, err = exec_commands(module, pull_realm(module, container_image=container_image))  # noqa: E501

    exit_module(module=module, out=out, rc=rc, cmd=cmd, err=err, startd=startd, changed=changed)  # noqa: E501


def main():
    run_module()


if __name__ == '__main__':
    main()
