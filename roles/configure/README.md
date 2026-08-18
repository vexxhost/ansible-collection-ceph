# `configure`

Applies the day-2 declarative config plane to a running cephadm cluster:
`ceph config`, erasure-code profiles, CRUSH rules, pools, CephX keys and
dashboard users. Everything runs **once**, delegated to the cluster admin host,
over the fast `cephadm shell` path.

Meta-depends on `defaults` (which holds the public-API variables below). Steps
run in dependency order:

`ceph_config` → `ceph_ec_profiles` → `ceph_crush_rules` → `ceph_pools` →
`ceph_keys` → `ceph_dashboard_users`

Any list left empty is skipped.

## Variables (defined in the `defaults` role; set in group_vars)

| Variable | Module | Item shape |
| --- | --- | --- |
| `ceph_config` | `ceph_config` | grouped by `who`: `{<who>: {settings: [{name, value, sensitive?}]}}` |
| `ceph_ec_profiles` | `ceph_ec_profile` | `{name, k, m, plugin?, technique?, ...}` — see the erasure-code options note below |
| `ceph_crush_rules` | `ceph_crush_rule` | `{name, rule_type, bucket_root?, bucket_type?, device_class?, profile?, state?}` |
| `ceph_pools` | `ceph_pool` | `{name, type?, pg_num?, pgp_num?, size?, min_size?, pg_autoscale_mode?, target_size_ratio?, rule_name?, erasure_profile?, application?, expected_num_objects?, state?}` |
| `ceph_keys` | `ceph_key` | `{name, caps, secret?, dest?, import_key?, state?}` |
| `ceph_dashboard_users` | `ceph_dashboard_user` | `{name, password, roles?, state?}` |
| `ceph_dashboard_cert` / `ceph_dashboard_key` | (raw `ceph dashboard`) | PEM cert/key; both set → installed, else a self-signed cert is generated |

## Examples

```yaml
# Central config — grouped by `who` (named once); sensitive: true no_log's that item
ceph_config:
  global:
    settings:
      - { name: mon_max_pg_per_osd, value: 300 }
  mon:
    settings:
      - { name: mon_allow_pool_delete, value: true }
  client.rgw:
    settings:
      - { name: rgw_resolve_cname, value: true }
      - { name: rgw_sts_key, value: "abcdef", sensitive: true }

# Erasure-code profiles
ceph_ec_profiles:
  - name: ec_2_2_hdd            # jerasure (default plugin)
    k: 2
    m: 2
    plugin: jerasure
    technique: reed_sol_van
    jerasure_per_chunk_alignment: false   # real bool (no quotes)
    crush_device_class: hdd
    crush_failure_domain: host
  - name: ec_4_2_clay           # clay plugin (MSR, low recovery bandwidth)
    k: 4
    m: 2
    plugin: clay
    d: 5
    scalar_mds: jerasure
    crush_failure_domain: host

# CRUSH rules (replicated or erasure)
ceph_crush_rules:
  - { name: rep_ssd, rule_type: replicated, bucket_root: default, bucket_type: host, device_class: ssd }
  - { name: ec_hdd,  rule_type: erasure,    profile: ec_2_2_hdd }

# Pools
ceph_pools:
  - { name: rbd, type: replicated, application: rbd, pg_autoscale_mode: "on", rule_name: rep_ssd }
  - name: ec_data
    type: erasure
    application: rgw
    erasure_profile: ec_2_2_hdd
    rule_name: ec_hdd
    pg_autoscale_mode: "on"

# CephX auth entities (caps is a dict; secret optional -> cephadm generates one)
ceph_keys:
  - name: client.rbd
    caps:
      mon: "profile rbd"
      osd: "profile rbd pool=rbd"
  - name: client.kube
    caps:
      mon: "allow r"
      osd: "allow rwx pool=kube"
    secret: "AQ...=="        # optional; no_log'd

# Dashboard users
ceph_dashboard_users:
  - { name: admin, password: "ChangeMe123!", roles: [administrator] }
  - { name: viewer, password: "ReadOnly123!", roles: [read-only] }

# Dashboard TLS — leave cert/key empty for an auto self-signed cert, or provide
# your own PEM pair. Changing either re-installs it and reloads the dashboard.
ceph_dashboard_cert: |
  -----BEGIN CERTIFICATE-----
  ...
  -----END CERTIFICATE-----
ceph_dashboard_key: |
  -----BEGIN PRIVATE KEY-----
  ...
  -----END PRIVATE KEY-----
```

## Dashboard notes

The dashboard needs the `dashboard` mgr module enabled (via the `mgr` role's
`ceph_mgr_modules`) **and** a TLS certificate before it will serve. Since
bootstrap runs with `--skip-dashboard`, this role enrolls the cert:

- **cert enrollment** (`dashboard.yml`): if `ceph_dashboard_cert` + `_key` are
  set, that PEM pair is installed (`ceph dashboard set-ssl-certificate[-key]`);
  otherwise a self-signed cert is generated (only when none exists). On a
  change, the dashboard is reloaded (`ceph mgr module disable/enable dashboard` +
  `ceph orch reconfig mgr`) so it picks up the new cert. It no-ops when the
  module isn't enabled.
- **listen ports** are Ceph config keys, not dedicated vars — set them through
  `ceph_config` under `mgr`, alongside any other mgr/dashboard tuning:

  ```yaml
  ceph_config:
    mgr:
      settings:
        - { name: mgr/dashboard/ssl_server_port, value: 8443 }   # HTTPS
        - { name: mgr/dashboard/server_port, value: 8080 }        # HTTP (ssl off)
        - { name: mgr/dashboard/standby_behaviour, value: error }
        - { name: mgr/dashboard/RGW_API_SSL_VERIFY, value: false }
        - { name: mgr/dashboard/FEATURE_TOGGLE_CEPHFS, value: false }
        - { name: mgr/dashboard/FEATURE_TOGGLE_ISCSI, value: false }
        - { name: mgr/dashboard/FEATURE_TOGGLE_MIRRORING, value: false }
        - { name: mgr/dashboard/FEATURE_TOGGLE_NFS, value: false }
        - { name: mgr/prometheus/rbd_stats_pools, value: "kube" }
  ```

## Notes

- `type` on a pool maps to the module's `pool_type` (`replicated` | `erasure`,
  default `replicated`). For erasure pools set `erasure_profile` (and usually a
  matching `rule_name`).
- **`pg_autoscale_mode`** accepts `on` / `off` / `warn`. The module normalizes
  aliases: `true`/`on`/`yes` → `on`, `false`/`off`/`no` → `off`, and anything
  else → `warn` (so a typo silently becomes `warn`). In YAML the bare words
  `on`/`off`/`yes`/`no` are booleans, so quote the string forms (`"on"`,
  `"warn"`) — or just use the bools `true`/`false`. The compare is against the
  pool's current normalized mode, so it's idempotent.
- Ordering handles dependencies: EC profiles exist before crush rules/pools that
  reference them; pools before keys that scope to them.
- **Erasure-code profile keys** (all current/non-deprecated on squid & tentacle):
  - *common:* `plugin`, `k`, `m`, `crush_root`, `crush_failure_domain`,
    `crush_device_class`, `crush_num_failure_domains`,
    `crush_osds_per_failure_domain`, `directory`, `stripe_unit`
  - *jerasure:* `technique`, `packetsize`, `w`, `jerasure_per_chunk_alignment` (bool)
  - *isa:* `technique`
  - *lrc:* `l`, `crush_locality`, and the low-level `mapping` / `layers` / `crush_steps`
  - *shec:* `c`
  - *clay:* `d`, `scalar_mds`, `technique`
  - EC profiles are effectively immutable once a pool uses them; changing values
    on an existing profile needs `force: true` (and won't reshape existing pools).
- All steps are idempotent (the modules diff current vs desired). `ceph_keys`
  and `ceph_dashboard_users` always run `no_log`.
