# `mgr`

Deploys the Ceph managers and configures the ceph-mgr modules. Run it after the
`mon` role (the cluster must already be bootstrapped).

Meta-depends on `defaults` + `cephadm`.

## What it does

1. **Admin host** — locates the mon that holds the cluster store (the admin host)
   to run orchestrator commands against.
2. **Host registration** — includes the `cephadm_host` role for each mgr host.
3. **Service spec** — applies `service_type: mgr` placement by the `mgr` label.
4. **Readiness** — waits (up to `ceph_mgr_check_retry` × 3s) for each mgr daemon
   to appear in `ceph orch ps`.
5. **mgr modules** — enables/disables each entry in `ceph_mgr_modules` via the
   `ceph_mgr_module` module.

Runs inside a block that sets the `CEPHADM_*` environment (image/fsid/admin-mon
config) for the fast cephadm-shell path.

## Key variables (in the `defaults` role)

| Variable | Default | Purpose |
| --- | --- | --- |
| `ceph_mgr_group` | `controllers` | inventory group holding the mgrs |
| `ceph_mgr_check_retry` | `120` | mgr-readiness retries (×3s) |
| `ceph_mgr_modules` | `dashboard`, `diskprediction_local`, `iostat` | list of `{name, state}` (state: `enable`/`disable`) |

The `dashboard` module here is what the `configure`
(dashboard TLS/users) role build on — keep this enabled if you use this role.
