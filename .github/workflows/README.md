# GarStream workflow contracts

`garstream-ec2-e2e.yml` runs the product-owned Golden scenario against two
already-provisioned **simulation** EC2 nodes.  The workflow checks out GAR and
the `GarStreamTx` / `GarStreamRx` product branches, then executes the real
`gar system test --scenario ... --json` control path.  Runtime start/stop uses
GAR's `ssh_remote` SimulationRuntime; the workflow never builds, deploys, or
connects to a physical Target.

The EC2 job requires these repository secrets:

- `GARSTREAM_EC2_CONFIG_JSON`: complete GAR workspace config for TX/RX.  The
  workflow replaces only the two local checkout paths and requires
  `selected_environments.simulator=ssh_remote`.
- `GARSTREAM_EC2_SSH_CONFIG`: restricted `Host` / `HostName` / `User` / `Port`
  aliases (and optional `ProxyJump` or timeout settings) for the simulation
  nodes.
- `GARSTREAM_EC2_SSH_KEY` and `GARSTREAM_EC2_KNOWN_HOSTS`: the limited key and
  pinned host keys.  Both GAR and the tunnel use `HostKeyAlias=<runtime alias>`,
  so every alias must already have a matching known-host entry.
- `GARSTREAM_EC2_TX_BRIDGE_PORT` and `GARSTREAM_EC2_RX_BRIDGE_PORT`: the two
  remote loopback Bridge ports.  The runner creates distinct host-key-pinned
  SSH local forwards and passes only their `127.0.0.1` origins to the scenario.

Missing EC2 protected configuration produces an uploaded structured `skipped`
record.  A configured run uploads the GAR JSON result and a redacted run record
whether the scenario passes or fails.

`garstream-physical-hil.yml` is manual-only.  Repository settings must provide
a protected `physical-hil` environment with required reviewers and a
`self-hosted, physical-hil` runner connected to the physical Targets.  It
requires `GARSTREAM_HIL_CONFIG_JSON` plus `GARSTREAM_HIL_ARTIFACTS_DIR`, an
external runner path containing the pre-approved GAR schema-v2 snapshots used
by read-only compatibility preflight.  The runner's default `known_hosts` must
pin both physical Target aliases.  The caller must supply `approval_ref`.

This workflow honestly records **read-only HIL coverage only**: `gar target
preflight --json` and `gar target diag --json` for Raspberry Pi TX and RK3506
RX.  It records Target IDs, expected/running build IDs, compatibility, service
status, and health for 90 days.  It has no build or deploy command.  A full
physical execution of the Bridge-driven Golden scenario remains unimplemented
until GAR has an explicit physical-harness scenario adapter; every record marks
that limitation instead of claiming a full Golden HIL pass.

Product-parent CI builds the real simulation hook bundle and captures both
simulation and Target bundles through GAR's schema-v2 artifact store.  TX uses
its production Python Target bundle.  RX standard CI uses a real armhf ELF
contract stub to exercise the Target hook and architecture envelope because the
production binary requires the separately managed Luckfox Buildroot SDK.  The
RX product-child workflow still builds the complete native GStreamer executable
and runs its CTest suite on every normal CI run.
