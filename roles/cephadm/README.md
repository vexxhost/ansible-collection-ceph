# `cephadm`

Base host preparation for a cephadm-managed cluster. This is the foundation role
every component role (`mon`/`mgr`/`osd`/`rgw`) meta-depends on, so it
runs on **every** ceph host before any daemon is placed.

## What it does

- Pulls in its dependencies (see `meta/main.yml`):
  - `defaults` — the shared config surface.
  - `vexxhost.containers.docker` — the container engine (Docker only; no podman).
  - `vexxhost.containers.download_artifact` — installs the **cephadm binary**
    straight to `/usr/bin/cephadm` (checksum-verified). No repos, no
    `ceph-common` package — nothing that would touch the host's package repos.
- Removes any stale `/usr/local/bin/cephadm` from the legacy install path.
- Creates the **cephadm SSH user** (`ceph_ssh_user`) with passwordless sudo.
- Logs in to the container registry (when `ceph_registry_username` is set) and
  **pre-pulls the Ceph image** so bootstrap/daemon placement is fast.

## Key variables

Shared (in the `defaults` role): `ceph_version`, `ceph_image`, `ceph_ssh_user`,
`ceph_registry_url` / `ceph_registry_username` / `ceph_registry_password`.

Role-internal (in `roles/cephadm/defaults/main.yml`, override only if needed):

| Variable | Default | Purpose |
| --- | --- | --- |
| `cephadm_download_url` | `https://download.ceph.com/rpm-{{ ceph_version }}/el9/noarch/cephadm` | where the cephadm binary is fetched from |
| `cephadm_download_dest` | `/usr/bin/cephadm` | install path |
| `cephadm_binary_checksum` | `{{ cephadm_checksums[ceph_version] }}` | sha256, keyed by release |

To support a new Ceph point release, add its cephadm sha256 to `cephadm_checksums`
in `roles/cephadm/defaults/main.yml`.
