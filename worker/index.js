/* DYNAMIC Worker: Cloudflare Access login + per-user, per-part practice memos.
 *
 * Only /login, /logout and /api/* reach this script (see `assets.run_worker_first`
 * in wrangler.jsonc); everything else is served straight from public/.
 *
 * - /login is protected by a Cloudflare Access (Zero Trust) application. Access
 *   forwards the signed identity in `Cf-Access-Jwt-Assertion`; the Worker verifies
 *   it and keeps it in an HttpOnly cookie so the whole site shares the login.
 * - /api/me reports the login state without redirecting.
 * - /api/memos/<part> stores one JSON document per user and part in R2
 *   (`memos/v1/<user>/<part>.json`). The server stamps every save with UTC times.
 *
 * Without ACCESS_TEAM_DOMAIN, ACCESS_AUD and the MEMOS bucket the feature stays
 * disabled and the reader hides its memo controls.
 */

export const COOKIE = 'dyn_session';
export const MEMO_SCHEMA = 'dynamic-memos/1';
const PART_RE = /^[a-z0-9][a-z0-9-]{0,63}$/;
const ID_RE = /^[A-Za-z0-9_-]{8,40}$/;
const MVT_RE = /^[A-Za-z0-9]{1,8}$/;
const KINDS = ['note', 'issue', 'good'];
const MAX_TEXT = 2000;
const MAX_MEMOS = 500;
const JWKS_TTL_MS = 60 * 60 * 1000;

const enc = new TextEncoder();
let jwksCache = { url: '', at: 0, keys: [] };

// ---------- responses ----------
const SECURITY_HEADERS = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin' };
function json(body, status = 200, extra = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json; charset=utf-8', ...SECURITY_HEADERS, ...extra } });
}
const fail = (status, error) => json({ error }, status);
function redirect(location, cookie) {
  const h = new Headers({ Location: location, ...SECURITY_HEADERS });
  if (cookie) h.append('Set-Cookie', cookie);
  return new Response(null, { status: 302, headers: h });
}
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
}
function loginComplete(email, back, cookie) {
  const headers = new Headers({
    'Content-Type': 'text/html; charset=utf-8',
    ...SECURITY_HEADERS,
    'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
  });
  headers.append('Set-Cookie', cookie);
  const html = `<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0f7cf6"><title>ログインしました · DYNAMIC</title>
<style>
:root{color-scheme:light;font:16px/1.6 system-ui,-apple-system,"Hiragino Sans","Noto Sans CJK JP",sans-serif;color:#10233d;background:#f3f7fc}
*{box-sizing:border-box}body{min-height:100vh;margin:0;display:grid;place-items:center;padding:20px}
main{width:min(100%,460px);padding:32px;border:1px solid #d5e1ee;border-radius:20px;background:#fff;box-shadow:0 18px 55px #10233d18}
.brand{margin:0 0 24px;color:#0f7cf6;font-size:14px;font-weight:900;letter-spacing:.1em}
.ok{margin:0 0 4px;color:#2f7a5f;font-size:14px;font-weight:800}h1{margin:0 0 24px;font-size:28px;line-height:1.3}
.label{margin:0;color:#5b6f86;font-size:13px}.identity{display:block;margin:4px 0 24px;overflow-wrap:anywhere;font-size:17px}
a{display:block;padding:12px 18px;border-radius:12px;background:linear-gradient(120deg,#1b9bff,#0f7cf6 55%,#2fe3cf);color:#fff;text-align:center;text-decoration:none;font-weight:800}
</style></head><body><main><p class="brand">DYNAMIC</p><p class="ok">ログインしました</p><h1>ログインできました</h1>
<p class="label">ログイン中のアカウント</p><strong class="identity">${escapeHtml(email)}</strong>
<a href="${escapeHtml(back)}">続ける</a></main></body></html>`;
  return new Response(html, { status: 200, headers });
}

// ---------- JWT (Cloudflare Access, RS256) ----------
function b64urlBytes(s) {
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
const b64urlJson = (s) => JSON.parse(new TextDecoder().decode(b64urlBytes(s)));
export const teamOrigin = (env) => `https://${String(env.ACCESS_TEAM_DOMAIN || '').replace(/^https?:\/\//, '').replace(/\/+$/, '')}`;

async function jwks(env, fetcher, refresh = false) {
  const url = `${teamOrigin(env)}/cdn-cgi/access/certs`;
  if (!refresh && jwksCache.url === url && Date.now() - jwksCache.at < JWKS_TTL_MS) return jwksCache.keys;
  const res = await fetcher(url);
  if (!res.ok) throw new Error(`certs ${res.status}`);
  const { keys = [] } = await res.json();
  jwksCache = { url, at: Date.now(), keys };
  return keys;
}
export function resetJwksCache() { jwksCache = { url: '', at: 0, keys: [] }; }

/** Returns the verified claims, or null for any invalid, expired or foreign token. */
export async function verifyAccessJwt(token, env, { fetcher = fetch, now = Date.now() } = {}) {
  if (!token || !env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD) return null;
  const parts = token.split('.');
  if (parts.length !== 3) return null;
  let header, claims;
  try { header = b64urlJson(parts[0]); claims = b64urlJson(parts[1]); } catch { return null; }
  if (header.alg !== 'RS256' || !header.kid) return null;
  let keys = await jwks(env, fetcher);
  let jwk = keys.find((k) => k.kid === header.kid);
  if (!jwk) { keys = await jwks(env, fetcher, true); jwk = keys.find((k) => k.kid === header.kid); }
  if (!jwk) return null;
  const key = await crypto.subtle.importKey('jwk', { kty: jwk.kty, n: jwk.n, e: jwk.e, alg: 'RS256', ext: true },
    { name: 'RSASSA-PKCS1-v1_5', hash: 'SHA-256' }, false, ['verify']);
  const ok = await crypto.subtle.verify('RSASSA-PKCS1-v1_5', key, b64urlBytes(parts[2]), enc.encode(`${parts[0]}.${parts[1]}`));
  if (!ok) return null;
  const sec = Math.floor(now / 1000);
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!aud.includes(env.ACCESS_AUD)) return null;
  if (claims.iss !== teamOrigin(env)) return null;
  if (typeof claims.exp !== 'number' || claims.exp <= sec) return null;
  if (typeof claims.nbf === 'number' && claims.nbf > sec + 60) return null;
  if (!claims.sub || !claims.email) return null;
  return claims;
}

function readCookie(request, name) {
  for (const part of (request.headers.get('Cookie') || '').split(';')) {
    const i = part.indexOf('=');
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return '';
}
const sessionCookie = (token, maxAge) => `${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${Math.max(0, maxAge)}`;

/** Only same-site relative paths are accepted as a post-login destination. */
export function safeReturn(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) return '/reader/';
  try {
    const u = new URL(value, 'https://dynamic.invalid');
    return u.origin === 'https://dynamic.invalid' ? u.pathname + u.search + u.hash : '/reader/';
  } catch { return '/reader/'; }
}

const memoParts = (env) => String(env.MEMO_PARTS || '').split(',').map((s) => s.trim()).filter(Boolean);
// Fail closed when no parts are explicitly enabled; an empty deployment setting
// must never silently widen the API to every catalog entry.
const configured = (env) => Boolean(env.ACCESS_TEAM_DOMAIN && env.ACCESS_AUD && env.MEMOS && memoParts(env).length);

async function currentUser(request, env, opts) {
  return verifyAccessJwt(readCookie(request, COOKIE), env, opts);
}

// ---------- routes: login ----------
async function login(request, env, opts) {
  const url = new URL(request.url);
  const back = safeReturn(url.searchParams.get('return'));
  if (!configured(env)) return redirect(back);
  const token = request.headers.get('Cf-Access-Jwt-Assertion') || '';
  const claims = await verifyAccessJwt(token, env, opts);
  // Access should never let an unauthenticated request reach /login; refuse rather than loop.
  if (!claims) return fail(401, 'Cloudflare Access の認証情報を確認できませんでした。');
  const maxAge = claims.exp - Math.floor((opts.now ?? Date.now()) / 1000);
  return loginComplete(claims.email, back, sessionCookie(token, maxAge));
}

function logout(request, env) {
  const target = env.ACCESS_TEAM_DOMAIN ? '/cdn-cgi/access/logout' : '/reader/';
  return redirect(target, sessionCookie('', 0));
}

// ---------- routes: memos ----------
function sameOrigin(request) {
  const origin = request.headers.get('Origin');
  return origin === new URL(request.url).origin;
}
async function knownPart(env, part, request) {
  if (!env.ASSETS) return true;
  const res = await env.ASSETS.fetch(new URL('/reader/parts.json', request.url));
  if (!res.ok) return false;
  const data = await res.json();
  return (data.parts || data).some((p) => p.id === part);
}
async function userKey(claims) {
  const digest = await crypto.subtle.digest('SHA-256', enc.encode(`access:${claims.sub}`));
  return [...new Uint8Array(digest)].slice(0, 16).map((b) => b.toString(16).padStart(2, '0')).join('');
}
export const memoKey = (user, part) => `memos/v1/${user}/${part}.json`;

function emptyDoc(part, claims, user) {
  return { schema: MEMO_SCHEMA, part, user: { key: user, email: claims.email }, updatedAt: null, memos: [] };
}

const clampNum = (v, lo, hi) => (Number.isFinite(v) && v >= lo && v <= hi ? Math.round(v * 10) / 10 : null);
/** Validates client input; returns [memoFields, error]. Timestamps and ids never come from the client. */
export function cleanMemo(body) {
  if (!body || typeof body !== 'object') return [null, 'JSON が必要です。'];
  const text = typeof body.text === 'string' ? body.text.replace(/\r\n?/g, '\n').trim() : '';
  if (!text) return [null, 'メモを入力してください。'];
  if (text.length > MAX_TEXT) return [null, `メモは${MAX_TEXT}文字までです。`];
  const rehearsal = typeof body.rehearsal === 'string' ? body.rehearsal.trim().slice(0, 8) : '';
  const kind = KINDS.includes(body.kind) ? body.kind : 'note';
  const a = body.anchor || {};
  const mvt = typeof a.mvt === 'string' && MVT_RE.test(a.mvt) ? a.mvt : null;
  const bar = Number.isInteger(a.bar) && a.bar >= 0 && a.bar <= 9999 ? a.bar : null;
  if (!mvt) return [null, '楽章が不正です。'];
  const anchor = {
    mvt, bar,
    page: Number.isInteger(a.page) && a.page > 0 && a.page < 1000 ? a.page : null,
    sys: Number.isInteger(a.sys) && a.sys > 0 && a.sys < 100 ? a.sys : null,
    x: clampNum(a.x, 0, 20000), y: clampNum(a.y, -2000, 20000),
    note: Number.isInteger(a.note) && a.note > 0 ? a.note : null,
  };
  return [{ text, rehearsal, kind, anchor }, null];
}

async function loadDoc(env, key) {
  const obj = await env.MEMOS.get(key);
  if (!obj) return [null, null];
  return [await obj.json(), obj.etag];
}

/** Read-modify-write guarded by the R2 etag so two tabs cannot silently drop each other's memo. */
async function mutate(env, key, fresh, change) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const [stored, etag] = await loadDoc(env, key);
    const doc = stored || fresh();
    const result = change(doc);
    if (result.error) return result;
    doc.updatedAt = result.at;
    const body = JSON.stringify(doc, null, 1);
    const put = await env.MEMOS.put(key, body, {
      httpMetadata: { contentType: 'application/json; charset=utf-8' },
      // Use a create-only precondition for the first save, then compare-and-swap.
      ...(etag ? { onlyIf: { etagMatches: etag } } : { onlyIf: { etagDoesNotMatch: '*' } }),
    });
    if (put) return { doc, memo: result.memo };
  }
  return { error: [409, '他の端末と同時に保存されました。もう一度お試しください。'] };
}

function newId() {
  const b = crypto.getRandomValues(new Uint8Array(12));
  return btoa(String.fromCharCode(...b)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function memos(request, env, opts, part, id) {
  if (!configured(env)) return fail(404, 'メモ機能は無効です。');
  if (!PART_RE.test(part) || (id && !ID_RE.test(id))) return fail(404, '見つかりません。');
  const allowed = memoParts(env);
  if (!allowed.includes(part)) return fail(403, 'このパートではメモを使えません。');
  const claims = await currentUser(request, env, opts);
  if (!claims) return fail(401, 'ログインが必要です。');
  const method = request.method;
  if (method !== 'GET' && !sameOrigin(request)) return fail(403, '別サイトからの送信は受け付けません。');
  if (!(await knownPart(env, part, request))) return fail(404, 'パートが見つかりません。');
  const user = await userKey(claims);
  const key = memoKey(user, part);
  const fresh = () => emptyDoc(part, claims, user);
  const now = () => new Date(opts.now ?? Date.now()).toISOString();

  if (method === 'GET' && !id) {
    const [doc] = await loadDoc(env, key);
    return json(doc || fresh());
  }
  let body = null;
  if (method === 'POST' || method === 'PUT') {
    if (!(request.headers.get('Content-Type') || '').startsWith('application/json')) return fail(415, 'JSON で送信してください。');
    try { body = await request.json(); } catch { return fail(400, 'JSON を読めませんでした。'); }
  }
  let out;
  if (method === 'POST' && !id) {
    const [fields, err] = cleanMemo(body);
    if (err) return fail(400, err);
    out = await mutate(env, key, fresh, (doc) => {
      if (doc.memos.length >= MAX_MEMOS) return { error: [409, `メモは1パート${MAX_MEMOS}件までです。`] };
      const at = now();
      const memo = { id: newId(), createdAt: at, updatedAt: at, ...fields };
      doc.memos.push(memo);
      doc.user.email = claims.email;
      return { at, memo };
    });
    if (!out.error) return json(out.memo, 201);
  } else if (method === 'PUT' && id) {
    const [fields, err] = cleanMemo(body);
    if (err) return fail(400, err);
    out = await mutate(env, key, fresh, (doc) => {
      const memo = doc.memos.find((m) => m.id === id);
      if (!memo) return { error: [404, 'メモが見つかりません。'] };
      const at = now();
      Object.assign(memo, fields, { updatedAt: at });
      return { at, memo };
    });
    if (!out.error) return json(out.memo);
  } else if (method === 'DELETE' && id) {
    out = await mutate(env, key, fresh, (doc) => {
      const i = doc.memos.findIndex((m) => m.id === id);
      if (i < 0) return { error: [404, 'メモが見つかりません。'] };
      const [memo] = doc.memos.splice(i, 1);
      return { at: now(), memo };
    });
    if (!out.error) return json({ deleted: id });
  } else {
    return fail(405, '許可されていない操作です。');
  }
  return fail(...out.error);
}

// ---------- entry ----------
export async function handle(request, env, opts = {}) {
  const url = new URL(request.url);
  const path = url.pathname;
  if (path === '/login') return login(request, env, opts);
  if (path === '/logout') return logout(request, env);
  if (path === '/api/me') {
    if (!configured(env)) return json({ enabled: false });
    const claims = await currentUser(request, env, opts);
    return json({ enabled: true, loggedIn: Boolean(claims), email: claims?.email || null, memoParts: memoParts(env), expiresAt: claims ? new Date(claims.exp * 1000).toISOString() : null });
  }
  const m = path.match(/^\/api\/memos\/([^/]+)(?:\/([^/]+))?$/);
  if (m) return memos(request, env, opts, m[1], m[2]);
  if (path.startsWith('/api/')) return fail(404, '見つかりません。');
  return env.ASSETS.fetch(request);
}

export default {
  async fetch(request, env) {
    try { return await handle(request, env); } catch (e) { console.error(e); return fail(500, 'サーバーでエラーが起きました。'); }
  },
};
