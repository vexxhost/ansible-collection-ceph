# `mon`

Bootstraps the cluster (first run) and deploys the monitors. This is the entry
point of the whole collection — run it against the `mons` group first.

Meta-depends on `defaults` + `cephadm`.

## What it does

1. **Public IP** — picks each mon's single address inside `ceph_public_network`
   (asserts exactly one) → `ceph_mon_ip`.
2. **Bootstrap detection** — checks every mon for an existing
   `/var/lib/ceph/<fsid>/mon.<host>/store.db`. If one exists, that host is the
   admin/bootstrap node; otherwise the first mon is chosen. Bootstrap runs **only**
   when no mon store exists anywhere, so re-runs are safe (idempotent, no
   re-bootstrap).
3. **Bootstrap** (`bootstrap.yml`, first run only) — writes the SSH identity
   (caller-provided key, else a generated keypair), assembles ceph.conf overrides,
   and runs the `cephadm_bootstrap` module with an explicit `fsid` + `image` and
   `--skip-monitoring-stack` / `--skip-dashboard` (those come later, from the
   `mgr`/`monitoring` roles).
4. **Host registration** — includes the `cephadm_host` role for each mon.
5. **Service spec** — applies `service_type: mon` placement by the `mon` label.
6. **Readiness** — waits (up to `ceph_mon_check_retry` × 3s) for each mon daemon
   to appear in `ceph orch ps`.

Everything after bootstrap-node selection runs inside one block that sets the
`CEPHADM_*` environment (image/fsid/admin-mon config) so every module and raw
command uses the fast `cephadm shell --fsid --config` path.

## Key variables (in the `defaults` role)

| Variable | Purpose |
| --- | --- |
| `ceph_fsid` | stable cluster FSID (required; central to bootstrap detection) |
| `ceph_public_network` / `ceph_cluster_network` | required CIDRs |
| `ceph_mon_group` | inventory group holding the mons (default `controllers`) |
| `ceph_ssh_public_key` / `ceph_ssh_private_key` | provide both to inject your own SSH identity; empty → cephadm generates one |
| `ceph_bootstrap_*` | bootstrap toggles (dashboard/firewalld off, FQDN/single-host defaults) |
| `ceph_mon_conf_overrides` | list of `{section, option, value}` written into ceph.conf at bootstrap |
| `ceph_mon_check_retry` | mon-readiness retries (×3s) |
| `ceph_mon_ssh_{public,private}_key_path` | where the cluster SSH identity is written on the bootstrap host |

## Usage

For a single-host (AIO) cluster set `ceph_bootstrap_single_host_defaults: true`
(and `ceph_bootstrap_allow_fqdn_hostname: true` if the host has an FQDN).
