// Unit tests for worker/index.js: `node --test tests/worker/`
import assert from 'node:assert/strict';
import { test, beforeEach } from 'node:test';
import { handle, verifyAccessJwt, safeReturn, cleanMemo, resetJwksCache, COOKIE } from '../../worker/index.js';

const TEAM = 'example.cloudflareaccess.com';
const AUD = 'aud-tag-123';
const ORIGIN = 'https://dynamic.oke.jp';
const NOW = Date.parse('2026-09-24T12:00:00Z');
const enc = new TextEncoder();
const b64url = (bytes) => Buffer.from(bytes).toString('base64url');

const pair = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const other = await crypto.subtle.generateKey({ name: 'RSASSA-PKCS1-v1_5', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, true, ['sign', 'verify']);
const jwk = { ...(await crypto.subtle.exportKey('jwk', pair.publicKey)), kid: 'k1' };
let certFetches = 0;
const fetcher = async (url) => {
  certFetches++;
  assert.equal(url, `https://${TEAM}/cdn-cgi/access/certs`);
  return new Response(JSON.stringify({ keys: [jwk] }));
};

async function sign(claims = {}, { key = pair.privateKey, kid = 'k1' } = {}) {
  const sec = Math.floor(NOW / 1000);
  const body = { aud: [AUD], iss: `https://${TEAM}`, sub: 'user-1', email: 'player@example.com', iat: sec, exp: sec + 3600, ...claims };
  const head = b64url(enc.encode(JSON.stringify({ alg: 'RS256', kid })));
  const payload = b64url(enc.encode(JSON.stringify(body)));
  const sig = await crypto.subtle.sign('RSASSA-PKCS1-v1_5', key, enc.encode(`${head}.${payload}`));
  return `${head}.${payload}.${b64url(new Uint8Array(sig))}`;
}

class FakeR2 {
  constructor() { this.store = new Map(); this.n = 0; }
  async get(key) {
    const v = this.store.get(key); if (!v) return null;
    return { etag: v.etag, json: async () => JSON.parse(v.body) };
  }
  async put(key, body, opt = {}) {
    const cur = this.store.get(key);
    if (opt.onlyIf?.etagMatches && (!cur || cur.etag !== opt.onlyIf.etagMatches)) return null;
    const etag = `e${++this.n}`; this.store.set(key, { body, etag }); return { etag };
  }
}
const assets = { fetch: async (u) => (String(u.url || u).endsWith('/reader/parts.json') ? new Response(JSON.stringify({ parts: [{ id: 'dvorak8-trombone1' }, { id: 'dvorak8-horn2' }] })) : new Response('static')) };

let env;
beforeEach(() => { resetJwksCache(); certFetches = 0; env = { ACCESS_TEAM_DOMAIN: TEAM, ACCESS_AUD: AUD, MEMO_PARTS: 'dvorak8-trombone1', MEMOS: new FakeR2(), ASSETS: assets }; });
const opts = { fetcher, now: NOW };
function req(path, { method = 'GET', token, body, origin = ORIGIN, headers = {} } = {}) {
  const h = { ...headers };
  if (token) h.Cookie = `other=1; ${COOKIE}=${token}`;
  if (origin && method !== 'GET') h.Origin = origin;
  if (body !== undefined) h['Content-Type'] = 'application/json';
  return new Request(ORIGIN + path, { method, headers: h, body: body === undefined ? undefined : JSON.stringify(body) });
}
const memo = { text: '練習記号Cで息が足りなかった', rehearsal: 'C', kind: 'issue', anchor: { mvt: 'IV', bar: 26, page: 4, sys: 2, x: 812.4, y: 150, note: 700 } };

test('verifies a valid Access token and rejects tampered, expired, foreign ones', async () => {
  const ok = await verifyAccessJwt(await sign(), env, opts);
  assert.equal(ok.email, 'player@example.com');
  assert.equal(await verifyAccessJwt(await sign({ exp: Math.floor(NOW / 1000) - 1 }), env, opts), null);
  assert.equal(await verifyAccessJwt(await sign({ aud: ['someone-else'] }), env, opts), null);
  assert.equal(await verifyAccessJwt(await sign({ iss: 'https://evil.cloudflareaccess.com' }), env, opts), null);
  assert.equal(await verifyAccessJwt(await sign({}, { key: other.privateKey }), env, opts), null);
  const [h, p, s] = (await sign()).split('.');
  const forged = b64url(enc.encode(JSON.stringify({ ...JSON.parse(Buffer.from(p, 'base64url')), email: 'admin@example.com' })));
  assert.equal(await verifyAccessJwt(`${h}.${forged}.${s}`, env, opts), null);
  assert.equal(await verifyAccessJwt('not.a.jwt', env, opts), null);
  assert.equal(await verifyAccessJwt(await sign(), { ...env, ACCESS_AUD: '' }, opts), null);
});

test('unknown key ids trigger one JWKS refresh', async () => {
  await verifyAccessJwt(await sign(), env, opts);
  assert.equal(certFetches, 1);
  assert.equal(await verifyAccessJwt(await sign({}, { kid: 'rotated' }), env, opts), null);
  assert.equal(certFetches, 2);
});

test('/login stores the Access assertion in a site-wide HttpOnly cookie', async () => {
  const token = await sign();
  const res = await handle(new Request(`${ORIGIN}/login?return=${encodeURIComponent('/reader/?part=dvorak8-trombone1')}`, { headers: { 'Cf-Access-Jwt-Assertion': token } }), env, opts);
  assert.equal(res.status, 302);
  assert.equal(res.headers.get('Location'), '/reader/?part=dvorak8-trombone1');
  const cookie = res.headers.get('Set-Cookie');
  assert.match(cookie, new RegExp(`^${COOKIE}=${token.replace(/\./g, '\\.')}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600$`));
  const bad = await handle(new Request(`${ORIGIN}/login`), env, opts);
  assert.equal(bad.status, 401);
});

test('post-login redirects stay on this site', () => {
  assert.equal(safeReturn('/reader/?part=x#m'), '/reader/?part=x#m');
  for (const v of ['https://evil.example/', '//evil.example/', '/\\evil.example', 'javascript:alert(1)', '', null]) assert.equal(safeReturn(v), '/reader/');
});

test('/api/me reports configuration and login state', async () => {
  assert.deepEqual(await (await handle(req('/api/me'), { ASSETS: assets }, opts)).json(), { enabled: false });
  const anon = await (await handle(req('/api/me'), env, opts)).json();
  assert.equal(anon.enabled, true); assert.equal(anon.loggedIn, false);
  const me = await (await handle(req('/api/me', { token: await sign() }), env, opts)).json();
  assert.equal(me.loggedIn, true); assert.equal(me.email, 'player@example.com'); assert.deepEqual(me.memoParts, ['dvorak8-trombone1']);
});

test('memo create, read, update, delete with server timestamps', async () => {
  const token = await sign();
  const created = await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: { ...memo, id: 'client-id', createdAt: '1999-01-01T00:00:00Z' } }), env, opts);
  assert.equal(created.status, 201);
  const m = await created.json();
  assert.notEqual(m.id, 'client-id');
  assert.equal(m.createdAt, '2026-09-24T12:00:00.000Z'); assert.equal(m.updatedAt, m.createdAt);
  assert.equal(m.rehearsal, 'C'); assert.equal(m.kind, 'issue'); assert.deepEqual(m.anchor, memo.anchor);

  const doc = await (await handle(req('/api/memos/dvorak8-trombone1', { token }), env, opts)).json();
  assert.equal(doc.schema, 'dynamic-memos/1'); assert.equal(doc.part, 'dvorak8-trombone1');
  assert.equal(doc.user.email, 'player@example.com'); assert.equal(doc.memos.length, 1);
  const [key] = env.MEMOS.store.keys();
  assert.match(key, /^memos\/v1\/[0-9a-f]{32}\/dvorak8-trombone1\.json$/);
  assert.ok(!key.includes('player@example.com'));

  const later = { ...opts, now: NOW + 60_000 };
  const upd = await (await handle(req(`/api/memos/dvorak8-trombone1/${m.id}`, { method: 'PUT', token, body: { ...memo, text: 'Cは前で吸えばOK', kind: 'good' } }), env, later)).json();
  assert.equal(upd.createdAt, m.createdAt); assert.equal(upd.updatedAt, '2026-09-24T12:01:00.000Z'); assert.equal(upd.kind, 'good');

  const del = await handle(req(`/api/memos/dvorak8-trombone1/${m.id}`, { method: 'DELETE', token }), env, opts);
  assert.equal(del.status, 200);
  assert.equal((await (await handle(req('/api/memos/dvorak8-trombone1', { token }), env, opts)).json()).memos.length, 0);
  assert.equal((await handle(req(`/api/memos/dvorak8-trombone1/${m.id}`, { method: 'DELETE', token }), env, opts)).status, 404);
});

test('memos are separated per user', async () => {
  await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token: await sign(), body: memo }), env, opts);
  const b = await (await handle(req('/api/memos/dvorak8-trombone1', { token: await sign({ sub: 'user-2', email: 'b@example.com' }) }), env, opts)).json();
  assert.equal(b.memos.length, 0);
});

test('memo API rejects anonymous, cross-site, disabled-part and invalid requests', async () => {
  const token = await sign();
  assert.equal((await handle(req('/api/memos/dvorak8-trombone1'), env, opts)).status, 401);
  assert.equal((await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: memo, origin: 'https://evil.example' }), env, opts)).status, 403);
  assert.equal((await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: memo, origin: null }), env, opts)).status, 403);
  assert.equal((await handle(req('/api/memos/dvorak8-horn2', { token }), env, opts)).status, 403);
  assert.equal((await handle(req('/api/memos/..%2Fsecret', { token }), env, opts)).status, 404);
  assert.equal((await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: { ...memo, text: '  ' } }), env, opts)).status, 400);
  assert.equal((await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: { ...memo, text: 'x'.repeat(2001) } }), env, opts)).status, 400);
  const plain = new Request(`${ORIGIN}/api/memos/dvorak8-trombone1`, { method: 'POST', headers: { Cookie: `${COOKIE}=${token}`, Origin: ORIGIN, 'Content-Type': 'text/plain' }, body: JSON.stringify(memo) });
  assert.equal((await handle(plain, env, opts)).status, 415);
  const noParts = { ...env, MEMO_PARTS: '' };
  assert.equal((await handle(req('/api/memos/not-a-part', { token }), noParts, opts)).status, 404);
});

test('cleanMemo drops unknown fields and bounds anchors', () => {
  const [m] = cleanMemo({ text: ' a\r\nb ', kind: 'weird', rehearsal: 'ABCDEFGHIJK', anchor: { mvt: 'I', bar: 3, x: 1e9, y: 'x', page: 1, sys: 2, evil: 1 }, owner: 'x' });
  assert.deepEqual(m, { text: 'a\nb', rehearsal: 'ABCDEFGH', kind: 'note', anchor: { mvt: 'I', bar: 3, page: 1, sys: 2, x: null, y: null, note: null } });
  assert.equal(cleanMemo({ text: 'a', anchor: { mvt: '<script>' } })[1], '楽章が不正です。');
});

test('concurrent saves do not drop memos', async () => {
  const token = await sign();
  await handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: memo }), env, opts);
  await Promise.all([1, 2, 3].map((i) => handle(req('/api/memos/dvorak8-trombone1', { method: 'POST', token, body: { ...memo, text: `t${i}` } }), env, opts)));
  const doc = await (await handle(req('/api/memos/dvorak8-trombone1', { token }), env, opts)).json();
  assert.equal(doc.memos.length, 4);
});

test('non-API paths fall through to static assets', async () => {
  assert.equal(await (await handle(req('/reader/'), env, opts)).text(), 'static');
  assert.equal((await handle(req('/api/nope'), env, opts)).status, 404);
});
