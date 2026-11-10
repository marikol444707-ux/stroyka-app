# JEV on a separate worker server

The existing Hermes Telegram/MAX gateway remains the sole message consumer. Its
root admission relay still checks the kernel PID, UID/GID and process start time
of the reviewed live gateway before forwarding a request. The new main server
uses the unchanged owner/company policy and signs/publishes into its own durable
queue. Only the main server executes searches and reserves completion delivery.
The existing notification ledger suppresses repeats after uncertain sends.

The deployment is explicit and default-off. `/etc/stroyka-jev-remote/role.json`
is a root-owned 0600 regular file with exactly `role` (`main` or `gateway`),
`peer_ip`, and boolean `enabled`. No tenant or recipient comes from this file:
they remain in the existing protected v2/v3 policies. Both peer IP and forced
SSH command must match, with no caller-supplied original command.

Each direction uses a distinct root-readable key, a pinned known-host key and
`/etc/stroyka-jev-remote/ssh_config`. Aliases `jev-main` and `jev-gateway` accept
no arbitrary commands. Public key authorization MUST include `restrict`, an
exact `from="peer IP"`, and a forced isolated host_entry `remote receive` or
`remote send` command. Never enable a general root shell or port forwarding for
these keys. Keys are not put into Hermes, environment variables or this repo.

Main: install the worker template for protocols 2 and 3. Keep local Hermes and
old local admission services disabled. Gateway: override only the two existing
JEV services' ExecStart with `host_entry.py remote relay 2`/`3`; retain their
systemd sockets. Relay startup does not read the signing key or execute work.
The old file queue runner remains beside Hermes as an intake adapter; its fixed
CLI forwards to main. Main uses the original pinned CLI and browser controller. The browser profile is
mounted from `/var/lib/stroyka-jev-browser/stroyka-jev-qa`; migrate it while the
source browser is stopped and compare content/ownership/modes before starting.
Exclude only Chrome transient process locks. A temporary, IP-restricted forced
SSH receiver may transfer this fixed directory directly between servers; revoke
that key immediately after verification. No other target path is accepted.

`ProtectSystem=strict` requires an explicit writable `/tmp`. Keep `PrivateTmp=false`
because the reviewed CLI passes temporary profile files to the host Docker daemon.
Verify native document extraction under these exact service restrictions; a plain
root-shell health check cannot establish that this namespace is usable.
The gateway CLI proxy uses `host_entry.py remote cli "$@"`; the old direct
controller entry uses `host_entry.py remote control --server` for compatibility.

## Cutover and rollback

1. Pin the installed source revision. Test the new package, forbidden identities,
   repeat requests, uncertain sends, lock exclusion and both restricted SSH
   directions in isolation. Verify renderer/model/provider access on main.
2. Record source service/socket/timer/restart states and hashes. Back up only
   files that will change and target state that will be replaced. Keep all
   unrelated application changes. Snapshot current frontend manifest/public
   files only if actually updating them; this migration does not do so.
3. Stop source JEV sockets/intake timer to reject new intake, then gracefully
   finish/stop both JEV workers. Do not kill an in-flight search or send. Stop the
   source renderer watchdog/container. Leave Hermes running.
4. Transfer the final JEV queues, admission receipts, result/delivery ledgers,
   commercial registry, settings, credentials and renderer state privately.
   Preserve owner/mode and compare complete file manifests. Do not replace
   Hermes data or Telegram offsets. Do not replay an unknown delivery.
5. Enable main workers/renderer and gateway relays/proxies only after the source
   workers are stopped. The two gateway services are now relays, not workers.
6. Test a real authorized request through the existing bot, its one response and
   old settings/history. Verify source has no search worker/browser, main has
   exactly one executor per protocol, and application/DB/frontend/browser are OK.
7. If unsuccessful, first stop new intake and main workers gracefully, return
   their latest durable state to source, restore source code/units/wrappers and
   service states, then restart old source workers. Never restore a stale ledger
   after a potentially successful send. Disable main restart policies.
8. Keep rollback while unfinished or failed. Only after all checks and user
   workflow confirmation remove exact obsolete backup/staging paths under the
   repository retention rules; retain a small receipt. This does not authorize
   deleting the VPS, which still hosts Hermes and other services.

The SSH keys authenticate only this infrastructure path; source user policy and
main company ownership checks remain mandatory. The gateway-to-main transfer is
not a Telegram network proxy. The main worker does not poll Telegram or receive
its token. Loss of connectivity returns unconfirmed admission, never success.
