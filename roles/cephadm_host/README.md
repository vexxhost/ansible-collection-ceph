# `cephadm_host`

Registers a single host into an already-bootstrapped cluster: authorises the
cluster SSH key, computes the host's labels from inventory membership, and adds
it to the orchestrator with the right address (and optional CRUSH location).

This is a **helper role included by the component roles** (`mon`/`mgr`/`osd`/`rgw`),
not applied on its own. Each component role includes it for its host, so a
co-located host (e.g. an AIO that is mon+mgr+osd) gets registered once with the
**full** label set — see the idempotency note below.

## What it does

1. **SSH key** — if no key is provided, fetches the cluster public key via
   `ceph cephadm get-pub-key` and authorises it for `cephadm_host_user`. If a key
   was provided (caller-supplied identity), that is authorised instead.
2. **Labels** — derives the complete label set from inventory group membership:
   `mon`/`mgr` → also `_admin`, plus `osd`, `rgw`, plus `cephadm_host_extra_labels`.
   The full set is computed here (not per-calling-role) so every caller passes the
   same desired labels, which is what keeps `ceph_orch_host` idempotent for
   co-located daemons (it diffs labels symmetrically — adds missing, removes extras).
3. **Address** — finds the host's single IP inside `ceph_public_network` (asserts
   exactly one) and registers/reconciles it. The vendored `ceph_orch_host` module
   runs `ceph orch host set-addr` when an existing host's addr differs, so a host
   first added by `cephadm bootstrap` (short hostname as addr) is corrected to its IP.
4. **CRUSH location** — when `cephadm_host_location` is set, applies a full host
   spec (`service_type: host`) carrying `location:` instead of the bare add.

## Variables (role-internal, set by the caller)

| Variable | Default | Purpose |
| --- | --- | --- |
| `cephadm_host_admin_host` | *(required)* | host to run orchestrator commands on |
| `cephadm_host_user` | `{{ ceph_ssh_user }}` | local user the cluster key is authorised for |
| `cephadm_host_public_key` | `{{ ceph_ssh_public_key }}` | caller-supplied key; empty → fetch from cluster |
| `cephadm_host_public_network` | `{{ ceph_public_network }}` | CIDR the host address is picked from |
| `cephadm_host_location` | `{{ ceph_host_location }}` | optional CRUSH topology (root/rack/row) |
| `cephadm_host_extra_labels` | `[]` | extra labels beyond the group-derived ones |
