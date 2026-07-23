# Dummy Operator — native Android board

A native Kotlin / Jetpack Compose app that renders Dummy's live operator board
on a phone, synced over **Tailscale**. Read-only: it fetches the dashboard's
GET JSON endpoints (`/api/overview`, `/api/scopes`, `/api/bet_board`) and never
touches the trading path. The dashboard's write/control endpoints stay
loopback-origin guarded on the host, so nothing on the phone can move capital.

## What it shows
- **Paper account** — balance, fills, orders, active sources, `EXEC: LOCKED`,
  proof-valid, freshness dot in the app bar.
- **CRYPTO / SPORTS** cards — hit rate, Brier, edge-vs-market, plus a per-scope
  row list with improvement trend arrows.
- **Tap any scope → its daily betting guide** — the league's ranked A/B/C
  picks, each headlined by an unmistakable **TAKE** line (e.g. "NYM to win",
  "OVER 8.5", "NO — no run in the 1st (NRFI)"), with model/market probability
  and edge.
- Auto-refreshes every 20 s; pull-to-refresh via the ↻ button.

## Connectivity
The default dashboard URL is this node's Tailscale IP (`http://100.98.141.113:8787`).
Change it in ⚙ Settings if your tailnet address differs. The phone reaches it
over the encrypted Tailscale tunnel; cleartext HTTP is permitted only because
that tunnel is already end-to-end encrypted.

## Serving the board on the tailnet
The primary `DummyDashboard` task binds loopback only. Run the read-only tailnet
instance (bound to this node's Tailscale IP, so it is reachable only over the
tunnel and does not collide with the loopback port):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_dashboard_tailnet_task.ps1
```

(Register-ScheduledTask needs an elevated shell; the launcher itself is
`scripts/tasks/launch_dashboard_tailnet.vbs`.)

## Build & install
```bash
cd android/DummyOperator
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
Requires the Android SDK (compileSdk 35, build-tools 35) and JDK 17+. minSdk 26.
Zero external network libraries — plain `HttpURLConnection` + `org.json`.
