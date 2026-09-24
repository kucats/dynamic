# Repository setup record

This generated repository has been customized as the Dynamic Score Reading Catalog.

- Project identity, scope, architecture, and local validation commands are documented in `AGENTS.md`, `README.md`, `docs/architecture/README.md`, and `docs/testing.md`.
- Public catalog paths are rooted at `public/`; reusable code is under `tools/`; work-specific scripts and note data are under `project/<composer>/<work>/<part>/`.
- GitHub Pages is not configured. Cloudflare Workers serves only `public/`, using `wrangler.jsonc` and the `dynamic.oke.jp` custom domain.
- Worker deployment steps and the future realtime-audio boundary are documented in `docs/deployment/cloudflare-workers.md`.
- No license has been selected. Do not infer reuse rights from public repository visibility.
