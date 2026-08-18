# `rgw`

Deploys and configures RADOS Gateway on a cephadm cluster:

- **multisite** objects — realm → zonegroup → zone (with a `period update --commit`
  when anything changed),
- **RGW service** placement via `ceph_orch_apply` (label-placed on the `rgw`
  group; flexible `count_per_host` / `networks` / arbitrary `spec`),

Meta-depends on `defaults` + `cephadm`. Everything cluster-wide runs once,
delegated to the admin host. `radosgw_*` modules run over the fast `cephadm shell` path.

## Not handled: ingress / load balancing

This role does **not** deploy cephadm `ingress` (haproxy + keepalived).
**Front RGW with your own external load balancer.** The RGW daemons listen on
their `rgw_frontend_port`; point your LB at the `rgw` hosts on that port.

> Set `ceph_rgw_enabled: false` so this collection
> does not touch RGW.

## Variables (in the `defaults` role; set in group_vars)

| Variable | Purpose | Item shape |
| --- | --- | --- |
| `ceph_rgw_enabled` | master switch (default `true`); `false` → role no-ops | bool |
| `ceph_rgw_realms` | `radosgw_realm` | `{name, default?, url?, access_key?, secret_key?, state?}` |
| `ceph_rgw_zonegroups` | `radosgw_zonegroup` | `{name, realm, master?, default?, endpoints?, state?}` |
| `ceph_rgw_zones` | `radosgw_zone` | `{name, realm, zonegroup, master?, default?, endpoints?, access_key?, secret_key?, state?}` |
| `ceph_rgw_services` | `ceph_orch_apply` (rgw) | `{id, count_per_host?, networks?, spec?}` — `spec` passed to cephadm **verbatim** |
| `ceph_rgw_redeploy_on_change` | `ceph orch redeploy rgw.<id>` when a redeploy-triggering key changes | bool (default `true`) |
| `ceph_rgw_redeploy_spec_keys` | spec keys whose change triggers a redeploy (SSL, frontend, …; extensible) | list |
| `ceph_rgw_remove_default_resources` | remove default zone/zonegroup + `default.rgw.*` pools (destructive) | bool (default `false`) |

RGW hosts are the `ceph_rgw_group` (`rgws`) inventory group — membership gives
them the `rgw` label (see the `cephadm_host` role).

## Example

```yaml
ceph_rgw_realms:
  - { name: molecule, default: true }

ceph_rgw_zonegroups:
  - name: us
    realm: molecule
    master: true
    default: true
    endpoints: ["https://s3.us.example.net"]

ceph_rgw_zones:
  - name: us-1
    realm: molecule
    zonegroup: us
    master: true
    default: true
    endpoints: ["https://s3.us.example.net"]

ceph_rgw_services:
  - id: us
    count_per_host: 1
    networks: 10.0.0.0/24        # string or list
    spec:
      rgw_realm: molecule
      rgw_zonegroup: us
      rgw_zone: us-1
      rgw_frontend_port: 8443
      # --- backend TLS (optional; see "SSL / TLS" below) ---
      ssl: true
      # ONE field holds the key AND the cert (concatenated PEM):
      rgw_frontend_ssl_certificate: |
        -----BEGIN PRIVATE KEY-----
        ...
        -----END PRIVATE KEY-----
        -----BEGIN CERTIFICATE-----
        ...
        -----END CERTIFICATE-----
      # ...or let cephadm self-sign instead of providing a cert:
      # generate_cert: true

# ceph_rgw_remove_default_resources: true   # opt-in: purge the stock default zone/pools
```

## SSL / TLS in transit

RGW sits behind your external LB, so **TLS is normally terminated at the LB** and
the RGW frontend runs plain HTTP on a trusted network — the sane default (omit
`ssl`). Enable **backend TLS (LB→RGW)** only when you need end-to-end encryption
(zero-trust, PCI, or an LB doing TLS **re-encryption**).

cephadm's SSL spec fields for tentacle (put them under `item.spec`):

| Field | Purpose |
| --- | --- |
| `ssl: true` | enable TLS on the frontend |
| `rgw_frontend_ssl_certificate` | PEM holding the **key and the cert concatenated** in one field (`str` or a list of lines) |
| `generate_cert: true` | let cephadm generate a self-signed key/cert instead of providing one (useful when the LB doesn't verify the backend cert) |

Cert changes are handled by the redeploy mechanism below (SSL/cert only ever
lands on a `redeploy`, not a `reconfig`).

## Changes that require a redeploy

cephadm reconciles most RGW spec changes live, but some — **SSL/cert** and the
**frontend listener** — only take effect on a `ceph orch redeploy`. After applying
the specs, the role snapshots the pre-apply spec and, for each service,
subset-compares the redeploy-triggering keys it declares against that snapshot; if
any differ it runs `ceph orch redeploy rgw.<id>` for **that service only**
(`ceph_rgw_redeploy_on_change`, default `true`).

`ceph_rgw_redeploy_spec_keys` is a **generic, extensible** list (not SSL-specific).
Default: `ssl`, `rgw_frontend_ssl_certificate`, `generate_cert`,
`ssl_cert`/`ssl_key`/`certificate_source` (latest/dev), `rgw_frontend_port`,
`rgw_frontend_type`. Add any other field that needs a daemon restart.

- **cert rotation / first-time TLS / `ssl` toggle / port or frontend change** →
  automatic redeploy of just that service.
- **other changes** (placement, `networks`, …) → no redeploy (cephadm reconciles
  those itself).
- **`generate_cert: true`** → no redeploy loop: the compare is restricted to the
  keys *you* set, so the cert cephadm generates and stores back doesn't count as a
  change.

Behind an LB with ≥2 RGW instances the brief per-daemon restart is a non-event.
Set `ceph_rgw_redeploy_on_change: false` to disable.

## Notes

- Order is realm → zonegroup → zone → `period update --commit` (only when a
  multisite object changed) → services → **redeploy SSL-changed services** →
  users → optional cleanup.
- `item.spec` is passed to cephadm **verbatim**, so any RGW spec field for your
  release works — `rgw_realm`/`rgw_zonegroup`/`rgw_zone`, `rgw_frontend_type`,
  `rgw_frontend_port`, `ssl`, `rgw_frontend_ssl_certificate`, `generate_cert`, …
  See the [cephadm RGW docs (tentacle)](https://docs.ceph.com/en/tentacle/cephadm/services/rgw/).
- `networks` accepts a string or a list.
- To disable RGW management entirely, set `ceph_rgw_enabled: false`.
