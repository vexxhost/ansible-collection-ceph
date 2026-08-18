# `osd`

Deploys Ceph OSDs on a cephadm-managed cluster. Meta-depends on the `cephadm`
role (which pulls in `defaults` + the docker/binary setup). Runs against the
`ceph_osd_group` hosts, registers each host into the cluster (via `cephadm_host`,
which applies the `osd` label), then provisions OSDs by one or both of:

- **`ceph_osd_spec`** — declarative cephadm *drive-group* service specs, applied
  once cluster-wide via `ceph_orch_apply` (idempotent). **Recommended.**
- **`ceph_osd_devices`** — an explicit, per-host list of device paths, each added
  individually via `ceph orch daemon add osd` (data-only, one OSD per device).

Finally it waits for the OSD daemons to reach `running`.

## Variables

| Variable | Scope | Default | Description |
| --- | --- | --- | --- |
| `ceph_osd_spec` | global (group_vars) | `[]` | List of cephadm drive-group specs. Each item is a service spec **without** `service_type` (added by the role). Target hosts via each item's `placement`. |
| `ceph_osd_devices` | per-host (host_vars) | `[]` | Explicit device paths on *this* host. Data-only, one OSD per device; no db/wal separation (use `ceph_osd_spec` for that). Prefer stable `/dev/disk/by-id` paths. |
| `ceph_osd_check_retry` | — | `120` | Retries (×5s) waiting for OSD daemons to come up. |

Cluster-wide settings (`ceph_fsid`, `ceph_public_network`, `ceph_mon_group`,
`ceph_ssh_public_key`, `ceph_host_location`, …) come from the `defaults` role.

> **`service_id` must be stable.** The idempotency read (`ceph orch ls osd
> osd.<service_id>`) is keyed on it; change it and cephadm gets a *second*
> service. Don't set `objectstore` (bluestore is the only production backend on
> squid/tentacle) or `filter_logic` (defaults to `AND`) — cephadm's normalized
> additions are ignored by the module's subset comparison.

## `ceph_osd_spec` examples

```yaml
# 1) All available disks (simplest)
ceph_osd_spec:
  - service_id: default
    placement: { host_pattern: "*" }
    spec:
      data_devices: { all: true }

# 2) All flash vs all spinning (device class auto-detected)
ceph_osd_spec:
  - service_id: flash
    placement: { label: osd }
    spec:
      data_devices: { rotational: 0 }   # SSD/NVMe
  - service_id: spinning
    placement: { label: osd }
    spec:
      data_devices: { rotational: 1 }   # HDD

# 3) Hybrid: HDD data + shared NVMe for DB (typical RGW/RBD node)
ceph_osd_spec:
  - service_id: hdd_nvme_db
    placement: { label: osd }
    spec:
      data_devices: { rotational: 1 }
      db_devices:   { rotational: 0 }
      db_slots: 6                       # up to 6 OSDs share one db device

# 4) HDD data + SSD DB + NVMe WAL (three tiers)
ceph_osd_spec:
  - service_id: tiered
    placement: { hosts: [storage-01, storage-02] }
    spec:
      data_devices: { rotational: 1 }
      db_devices:   { model: "SAMSUNG_SSD" }
      wal_devices:  { rotational: 0, size: ":200G" }

# 5) Size-based selection (big disks = data, small NVMe = db)
ceph_osd_spec:
  - service_id: bysize
    placement: { host_pattern: "storage*" }
    spec:
      data_devices: { size: "1T:" }      # >= 1 TB
      db_devices:   { size: ":400G" }    # <= 400 GB

# 6) Explicit device paths (stable /dev/disk/by-id recommended)
ceph_osd_spec:
  - service_id: explicit
    placement: { hosts: [storage-01] }
    spec:
      data_devices:
        paths:
          - /dev/disk/by-id/wwn-0x5000c500a1b2c3d4
          - /dev/disk/by-id/wwn-0x5000c500a1b2c3d5

# 7) Encrypted OSDs (dmcrypt)
ceph_osd_spec:
  - service_id: encrypted
    placement: { label: osd }
    spec:
      data_devices: { all: true }
      encrypted: true

# 8) Multiple OSDs per fast NVMe (better parallelism on large NVMe)
ceph_osd_spec:
  - service_id: nvme_split
    placement: { label: osd }
    spec:
      data_devices: { rotational: 0, size: "2T:" }
      osds_per_device: 2

# 9) Vendor/model + limit + override CRUSH device class
ceph_osd_spec:
  - service_id: curated
    placement: { hosts: [storage-03] }
    spec:
      data_devices:
        vendor: "ATA"
        model: "MZ7"
        limit: 4                         # consume at most 4 matching disks
      crush_device_class: "fast_ssd"

# 10) AIO 3-disk box: size-split into data + shared DB
ceph_osd_spec:
  - service_id: aio
    placement: { host_pattern: "*" }
    spec:
      data_devices: { size: "30G:" }     # sda(50G)+sdc(40G) -> 2 data OSDs
      db_devices:   { size: ":25G" }     # sdb(20G) -> shared DB

# 11) OR logic: a device qualifies if it is flash OR >= 2 TB (either matches).
#     filter_logic is a spec-level field (sibling of data_devices), not inside it.
ceph_osd_spec:
  - service_id: flash_or_big
    placement: { label: osd }
    spec:
      data_devices:
        rotational: 0                    # SSD/NVMe ...
        size: "2T:"                      # ... OR any disk >= 2 TB
      filter_logic: OR                   # default is AND (all criteria must match)
```

### Filter reference

- Filters combine with `filter_logic: AND` by default, e.g.
  `{ rotational: 1, size: "1T:" }` = HDD **and** ≥1 TB. Add `filter_logic: OR`
  under `spec:` for either.
- `size`: `"1T:"` (≥), `":400G"` (≤), `"200G:2T"` (range). Units: `G`, `T`.
- `data_devices` / `db_devices` / `wal_devices` accept `all`, `rotational`,
  `size`, `model`, `vendor`, `paths`, `limit`.
- `db_slots` / `wal_slots`: how many OSDs share one db/wal device.
- `osds_per_device`: multiple OSDs carved from one (fast) device.
- `placement`: `host_pattern` (glob), `label`, or explicit `hosts: [...]`.

## `ceph_osd_devices` examples (per host, in `host_vars/<host>.yml`)

Data-only, one OSD per device.

> **Device paths must NOT contain a colon (`:`).** They are passed straight to
> `ceph orch daemon add osd <host>:<device>`, whose parser splits on `:`. So:
>
> - **canonical `/dev` names** (`/dev/sdb`) — recommended: fully idempotent
>   (the `ceph-volume` re-run guard reports canonical names, so it matches).
> - **`by-id`** (`/dev/disk/by-id/wwn-0x…`) — no colon, works. Stable across
>   reordering. Note: the idempotency guard compares against `ceph-volume`'s
>   canonical output, so a `by-id` entry won't be recognised on re-run — prefer
>   canonical names here, or use `ceph_osd_spec` (which selects by stable
>   attributes and is fully idempotent).
> - **`by-path`** (`/dev/disk/by-path/pci-0000:00:1f.2-ata-2`) — **not
>   supported** via `ceph_osd_devices` (the `pci-0000:00:…` address contains
>   colons). Use `ceph_osd_spec` with a device filter instead.

```yaml
# host_vars/aio.yml — quick AIO test (canonical names; fully idempotent)
ceph_osd_devices:
  - /dev/sdb
  - /dev/sdc

# host_vars/storage-01.yml — by-id (stable; no colon)
ceph_osd_devices:
  - /dev/disk/by-id/wwn-0x5000c500a1b2c3d4
  - /dev/disk/by-id/wwn-0x5000c500a1b2c3d5
```
