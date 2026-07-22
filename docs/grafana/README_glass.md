# liquiditybot · Liquid Glass command board

`liquiditybot_glass.json` — a single, curated, Apple **Liquid Glass** command
board for the trading desk. It replaces the "wall of 60 stat panels" with the
~22 panels a trader actually scans, ordered top-down by decision urgency:

1. **Vitals** — alive & armed (running, halted, entries, Kraken link, telemetry age, governor)
2. **Money** — equity curve, daily / weekly P&L, open uPNL, drawdown, pools
3. **Risk heat** — budget heat, gross exposure, open risk, positions open
4. **The book** — open positions ranked by R, diverging R-by-asset bars
5. **Execution** — markout (adverse selection) heat, slippage, rejects, makeability
6. **Model** — Brier trio (live vs champion vs baseline), calibration, Kelly, governor

Color is **semantic only** (Apple system palette): green = nominal/profit,
red = loss/unsafe, orange = watch/approaching-limit, blue = neutral info,
gray = disarmed-by-design, indigo = model domain. A healthy board is calm —
a solid green vitals strip and mostly neutral numbers; color pulls the eye
only to what needs a decision. Every text-on-glass pair is verified ≥ 4.5:1
(WCAG / Apple HIG).

## Import

1. Grafana → Dashboards → **New → Import**.
2. Upload `liquiditybot_glass.json` (or paste it).
3. Datasource is bound to `grafanacloud-prom` (the Prometheus/Mimir source the
   OTLP exporter already writes to). If your UID differs, pick your Prometheus
   source when prompted. All series are `liquiditybot_*{job="liquiditybot"}`.

That's it — the board is fully readable and correctly colored **natively**, on
any Grafana Cloud instance, with no plugins.

## Full frosted-glass skin (optional, one signed plugin)

Grafana Cloud sanitizes `<style>` out of the native Text panel, so the hidden
injector tile (`id 999`) is a **no-op on Cloud** and only skins self-hosted
Grafana. To get the full frosted-glass DOM restyle on Cloud:

1. Install the signed **Business Text** panel
   (`marcusolsson-dynamictext-panel`, Volkov Labs) — one-click from the Grafana
   catalog, allowed on Cloud.
2. Replace the hidden `text` injector with a Business Text panel and move the
   CSS (the `<style id="lb-glass">…</style>` block, minus the tags) into its
   **After Content Ready (`afterRender`)** JavaScript, appending it to
   `document.head`:

   ```js
   const s = document.createElement('style');
   s.id = 'lb-glass';
   s.textContent = `/* paste the CSS body here */`;
   document.head.appendChild(s);
   ```

   That runs *after* Grafana's sanitizer, so the cascade lands — frosted panels,
   black canvas, SF typography, uppercase section eyebrows.

The board is beautiful without it; this is the extra 10%.

## Regenerating

The JSON is the source of truth (edit in Grafana, export, commit). It was
originally emitted by a generator that encodes the Apple palette + panel plan;
keep the datasource UID (`grafanacloud-prom`), `schemaVersion` (39), and the
semantic threshold steps if you hand-edit.

## Preview

A rendered Liquid Glass mockup of this board (what the full skin looks like)
was shared as an artifact in the build session.
