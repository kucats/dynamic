# Cloudflare Workers deployment

`wrangler.jsonc` publishes `public/` as Workers Static Assets at `dynamic.oke.jp`. No files from `project/`, `tools/`, or repository root are sent to the site. The app has no build step or external CDN dependency.

## Deploy

From a Cloudflare-authenticated environment with access to the `oke.jp` zone:

```sh
npx wrangler deploy --dry-run
npx wrangler deploy
```

Then check `https://dynamic.oke.jp/`, the Horn II, Horn III, and Trombone I reader pages, and the three linked PDFs. The custom domain must be in the active Cloudflare zone and must not have a conflicting CNAME record.

## Realtime audio direction

The current deployment is static-only and has no Worker entrypoint. When adding a Worker for a narrowly routed API or WebSocket signaling path, add an `ASSETS` binding then so the script can delegate ordinary requests back to static assets. The experimental score-following code under `tools/score_following/` is not part of the public deployment. Its Python/aiortc receiver and TURN service require a separate runtime; this site does not claim that WebRTC media processing runs inside the static Worker.

Keep WebSocket signaling and WebRTC media transport as separate concerns. Any future live audio feature needs a reviewed Worker/API boundary, authenticated session lifecycle, browser/device tests, and WAN/TURN validation before it is exposed from the public site.
