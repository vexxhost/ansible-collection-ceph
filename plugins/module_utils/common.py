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
#   https://github.com/ceph/cephadm-ansible/blob/fbe6eccd705ed203e5ce30a2cf33d9e77e98d4c9/plugins/module_utils/ceph_common.py
# Changes:
#   - Removed the debug print() calls from retry() (they wrote to stdout and
#     corrupted an Ansible module's JSON result).
#   - Added the ceph-ansible ca_common.py data-plane helpers
#     (generate_cmd, pre_generate_cmd, container_exec, is_containerized,
#     exec_command), REIMPLEMENTED on the cephadm-shell model so the vendored
#     ceph-ansible day-2 modules port with an import rewrite only. Source:
#     https://github.com/ceph/ceph-ansible/blob/8599b192d33e1c55104c1c2fd1abfa8431c64664/module_utils/ca_common.py
#
# This is the single, unified module_utils for the collection. Everything runs
# "ceph"/"radosgw-admin" through "cephadm shell". The legacy execution model
# from ca_common.py -- a `docker/podman run --entrypoint` into a container
# selected by the CEPH_CONTAINER_BINARY env var -- is NOT carried over. The
# only remnant is is_containerized(), which now returns an OPTIONAL explicit
# image override (CEPH_CONTAINER_IMAGE) passed to `cephadm --image`; when unset
# (the default), cephadm resolves the image itself from the running cluster.

from __future__ import absolute_import, division, print_function
__metaclass__ = type

import os
import datetime
import time
from typing import TYPE_CHECKING, Any, List, Dict, Callable, Type, TypeVar, Optional

if TYPE_CHECKING:
    from ansible.module_utils.basic import AnsibleModule  # type: ignore

ExceptionType = TypeVar('ExceptionType', bound=BaseException)


def retry(exceptions: Type[ExceptionType], retries: int = 20, delay: int = 1) -> Callable:
    def decorator(f: Callable) -> Callable:
        def _retry(*args: Any, **kwargs: Any) -> Callable:
            _tries = retries
            while _tries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions:
                    time.sleep(delay)
                    _tries -= 1
            return f(*args, **kwargs)
        return _retry
    return decorator


def shell_timeout_args() -> List[str]:
    '''
    Bound every `cephadm shell` invocation so a hung call fails the task
    instead of blocking the play forever (idea borrowed from
    stackhpc.cephadm). Override the number of seconds via the CEPHADM_TIMEOUT
    env var.

    The default is 120s: every command routed through `cephadm shell` here is
    a fast control-plane metadata call (ceph config/pool/auth/orch,
    radosgw-admin ...), so 120s comfortably covers container cold-start plus a
    slow mon RPC while still failing fast on a wedged cluster. The only
    long-running op, `cephadm bootstrap`, does not go through this path.
    '''
    return ['--timeout', os.environ.get('CEPHADM_TIMEOUT', '120')]


def shell_scope_args(module: "AnsibleModule" = None) -> List[str]:
    '''
    `--fsid`/`--config` options for `cephadm shell`, taken from the module's
    params when present, otherwise from the CEPHADM_FSID / CEPHADM_CONFIG env
    vars. Pointing cephadm at the cluster fsid and the mon daemon's config
    (e.g. /var/lib/ceph/<fsid>/mon.<host>/config) skips cluster/config
    discovery and makes each shell call dramatically faster.

    The env fallback lets a role/play set these once (e.g. delegated to the
    admin host) so day-2 modules that have no fsid/config params are sped up
    too. The cephadm binary itself ignores these env vars, so raw `cephadm
    shell` command tasks are unaffected.
    '''
    args = []
    fsid = (module.params.get('fsid') if module else None) or os.environ.get('CEPHADM_FSID')
    if fsid:
        args.extend(['--fsid', fsid])
    config = (module.params.get('config') if module else None) or os.environ.get('CEPHADM_CONFIG')
    if config:
        args.extend(['--config', config])
    return args


def build_base_cmd(module: "AnsibleModule") -> List[str]:
    cmd = ['cephadm']
    docker = module.params.get('docker')
    image = module.params.get('image')

    if docker:
        cmd.append('--docker')
    if image:
        cmd.extend(['--image', image])

    return cmd


def build_base_cmd_shell(module: "AnsibleModule") -> List[str]:
    cmd = build_base_cmd(module)

    cmd.extend(shell_timeout_args())
    cmd.append('shell')
    cmd.extend(shell_scope_args(module))

    return cmd


def build_base_cmd_orch(module: "AnsibleModule") -> List[str]:
    cmd = build_base_cmd_shell(module)
    cmd.extend(['ceph', 'orch'])

    return cmd


# ---------------------------------------------------------------------------
# Day-2 data-plane helpers.
#
# These preserve the ceph-ansible ca_common.py call signatures so the vendored
# ceph-ansible modules (pool, key, radosgw_*, ...) port with an
# import rewrite only -- but they are reimplemented to run every command inside
# an ephemeral `cephadm shell` instead of the legacy `docker/podman run
# --entrypoint` path. Inside `cephadm shell` the client authenticates as
# client.admin using the cluster keyring, so the upstream `-n <user> -k
# <keyring>` flags are dropped.
# ---------------------------------------------------------------------------

def is_containerized() -> Optional[str]:
    '''
    Container image for the `cephadm shell` these day-2 modules run in.

    Returns the CEPHADM_IMAGE env var when set (passed to `cephadm --image`),
    otherwise None -- in which case cephadm resolves the image itself. This is
    the same env the cephadm binary and the orch modules use; the legacy
    CEPH_CONTAINER_IMAGE / CEPH_CONTAINER_BINARY model is not used.
    '''
    return os.environ.get('CEPHADM_IMAGE') or None


def pre_generate_cmd(cmd: str = 'ceph',
                     container_image: Optional[str] = None,
                     interactive: bool = False) -> List[str]:
    '''
    Build the `cephadm shell -- <cmd>` prefix.
    '''
    base = ['cephadm']
    if container_image:
        base.extend(['--image', container_image])
    base.extend(shell_timeout_args())
    base.append('shell')
    base.extend(shell_scope_args())
    base.extend(['--', cmd])
    return base


def generate_cmd(cmd: str = 'ceph',
                 sub_cmd: Optional[List[str]] = None,
                 args: Optional[List[str]] = None,
                 user_key: Optional[str] = None,
                 cluster: str = 'ceph',
                 user: str = 'client.admin',
                 container_image: Optional[str] = None,
                 interactive: bool = False) -> List[str]:
    '''
    Generate a `ceph` command line to execute inside `cephadm shell`.
    '''
    full = pre_generate_cmd(cmd, container_image=container_image, interactive=interactive)

    if cluster and cluster != 'ceph':
        full.extend(['--cluster', cluster])

    if sub_cmd is not None:
        full.extend(sub_cmd)

    if args is not None:
        full.extend(args)

    return full


def container_exec(binary: str,
                   container_image: Optional[str] = None,
                   interactive: bool = False) -> List[str]:
    '''
    Build a `cephadm shell -- <binary>` prefix (used to wrap radosgw-admin,
    ceph-authtool, etc.).
    '''
    base = ['cephadm']
    if container_image:
        base.extend(['--image', container_image])
    base.extend(shell_timeout_args())
    base.append('shell')
    base.extend(shell_scope_args())
    base.extend(['--', binary])
    return base


def exec_command(module: "AnsibleModule",
                 cmd: List[str],
                 stdin: str = None,
                 check_rc: bool = False):
    '''
    Execute command(s)
    '''
    binary_data = False
    if stdin:
        binary_data = True
    rc, out, err = module.run_command(cmd, data=stdin, binary_data=binary_data, check_rc=check_rc)

    return rc, cmd, out, err


def exit_module(module: "AnsibleModule",
                rc: int, cmd: List[str],
                startd: datetime.datetime,
                out: str = '',
                err: str = '',
                changed: bool = False,
                diff: Dict[str, str] = dict(before="", after="")) -> None:
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
        diff=diff
    )
    module.exit_json(**result)


def fatal(message: str, module: "AnsibleModule") -> None:
    '''
    Report a fatal error and exit
    '''

    if module:
        module.fail_json(msg=message, rc=1)
    else:
        raise Exception(message)
