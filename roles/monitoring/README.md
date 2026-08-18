# `monitoring`

Deploys the cephadm-managed monitoring stack as `ceph orch` services (idempotent,
run-once, delegated to the admin host). Since bootstrap runs with
`--skip-monitoring-stack`, this role is what brings the stack up.

Meta-depends on `defaults` + `cephadm`.

## Why the mgr `prometheus` module isn't enough

The mgr `prometheus` module (enabled via `ceph_mgr_modules` in the `mgr` role)
only exposes a **metrics endpoint** (`:9283`). A working stack also needs the
scraper and the exporters, all deployed as cephadm services:

| Service | Role |
| --- | --- |
| `node-exporter` | per-host OS metrics (CPU/mem/disk/net) |
| `ceph-exporter` | per-host Ceph daemon perf counters |
| `prometheus` | scrapes mgr `:9283` + ceph-exporter + node-exporter |
| `alertmanager` | Ceph alert rules/routing (cephadm ships defaults) |
| `grafana` | dashboards (datasource = prometheus; cephadm ships Ceph dashboards) |

cephadm auto-wires them (prometheus scrape config, grafana datasource,
alertmanager rules) once the services exist.

## Variables (in the `defaults` role)

| Variable | Purpose |
| --- | --- |
| `ceph_monitoring_enabled` | master switch (default `true`); `false` → role no-ops (e.g. feeding an external Prometheus/Grafana) |
| `ceph_monitoring_services` | list of cephadm service specs to apply (drop/reorder/extend) |
| `ceph_monitoring_images` | optional air-gap image pins (dict) |

Default `ceph_monitoring_services`:

```yaml
ceph_monitoring_services:
  - { service_type: ceph-exporter, placement: { host_pattern: "*" } }   # no `networks` field
```

`networks: ["{{ ceph_public_network }}"]` binds each daemon to the public-network
interface. `ceph-exporter` is the exception — it uses the base `ServiceSpec`, which
has **no `networks` field** (passing one fails with
`unexpected keyword argument 'networks'`), so it's left off that one.

### How cephadm addresses the monitoring targets

The address cephadm bakes into the Grafana→Prometheus datasource and the
node-/ceph-exporter scrape targets is:

```python
dd.ip if dd.ip else socket.getfqdn(<host addr from `ceph orch host ls`>)
```

Monitoring daemons usually don't populate `dd.ip`, so in practice the **host addr**
is what matters — cephadm reverse-resolves it. Two requirements follow:

1. **The host addr must be an IP.** The `cephadm_host` role registers each host
   with its `ceph_public_network` IP, and the vendored `ceph_orch_host` module
   reconciles it on re-converge (a host first added by `cephadm bootstrap` starts
   with its short hostname as addr).
2. **That IP must reverse-resolve to a name that resolves forward again** (or to
   nothing, in which case `getfqdn` returns the IP literal — also fine). A stale
   PTR pointing the IP at an old/renamed hostname is the classic failure: the
   datasource becomes `http://<old-name>:9095`, the Grafana container can't
   resolve it, and you get **HTTP 502**. Fix it at the resolver/PTR, or locally
   with an `/etc/hosts` entry (NSS `files` beats DNS for reverse lookups).

This is host/DNS provisioning, not a collection setting — a host whose forward and
reverse records match its name works out of the box.

Each item is a full cephadm service spec — add a `spec:` block for tuning, e.g.:

```yaml
ceph_monitoring_services:
  - service_type: prometheus
    placement: { label: mon }
    spec:
      retention_time: "30d"
      retention_size: "50GB"
  - service_type: grafana
    placement: { count: 1 }
    spec:
      initial_admin_password: "ChangeMe123!"
```

## Air-gap image pins

The monitoring images are **upstream** (prometheus/grafana/alertmanager/
node-exporter), not the ceph image (`ceph-exporter` uses the ceph image). Pin
them for offline mirrors — keys map to `mgr/cephadm/container_image_<key>`:

```yaml
ceph_monitoring_images:
  prometheus: mirror.local/prometheus/prometheus:v2.51.0
  grafana: mirror.local/ceph/ceph-grafana:9.4.12
  alertmanager: mirror.local/prometheus/alertmanager:v0.27.0
  node_exporter: mirror.local/prometheus/node-exporter:v1.7.0
```

## Dashboard integration

The dashboard's **Performance** panels (Grafana embeds) and alerts badge read
Grafana/Prometheus/Alertmanager URLs from `mgr/dashboard/*`. **cephadm sets these
automatically** each time it (re)deploys a monitoring service, using the same
address resolution described above — so normally you don't touch them, and they
come out correct once the host addr/DNS is sane.

Only override when you need a specific address (external LB, a Grafana reverse
proxy, etc.). Do it via `ceph_config` on `who: mgr` — but note cephadm **re-clobbers
these on that service's next redeploy**, so an override is not durable:

```yaml
ceph_config:
  mgr:
    settings:
      # cephadm-managed; set only to override, ports are the cephadm defaults:
      - { name: mgr/dashboard/PROMETHEUS_API_HOST,    value: "http://<addr>:9095" }
      - { name: mgr/dashboard/ALERTMANAGER_API_HOST,  value: "http://<addr>:9093" }
      - { name: mgr/dashboard/GRAFANA_API_URL,        value: "https://<addr>:3000" }
      # NOT cephadm-managed — safe to keep here (Grafana ships a self-signed cert):
      - { name: mgr/dashboard/GRAFANA_API_SSL_VERIFY, value: "false" }
```

Grafana panels render **browser-side**: your browser must reach the Grafana
address and trust (or click-through) its self-signed cert on `:3000`.

## Notes

- The mgr `prometheus` module must be enabled (it's in the default
  `ceph_mgr_modules`) for the prometheus service to have cluster metrics to scrape,
  and the `dashboard` module for the integration above.
- Verify: `ceph orch ls` (services running), `ceph mgr services`
  (dashboard/prometheus URLs), and browse Grafana on its host.
