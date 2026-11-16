import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import ts from 'typescript';

function moduleAt(path, dependencies, globals = {}) {
  const source = readFileSync(new URL('../src/' + path, import.meta.url), 'utf8');
  const exports = {};
  vm.runInNewContext(ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText, {
    exports, require: name => {
      if (!(name in dependencies)) throw new Error(`Unexpected dependency ${name}`);
      return dependencies[name];
    }, Response, Headers, AbortSignal, Buffer, Date, process: { env: {} }, ...globals,
  });
  return exports;
}
const user = { id: 'user-1', username: 'test', email: 'test@example.invalid',
  is_active: true, email_verified_at: null, created_at: '2026-11-16', updated_at: '2026-11-16' };
const jwt = seconds => 'header.' + Buffer.from(JSON.stringify({ exp: Date.now() / 1000 + seconds })).toString('base64url') + '.signature';
const validUser = moduleAt('lib/auth/user-response.ts', {});
test('expired and malformed access-only cookies never become bearer tokens', async () => {
  for (const token of [jwt(-60), 'not-a-jwt', '']) {
    const session = moduleAt('lib/auth/session.ts', {
      'next/headers': { cookies: async () => ({
        get: name => name === 'aqlyra_access_token' && token ? { value: token } : undefined,
      }) },
      '@/lib/api/backend': { backendUrl: () => { throw new Error('Unexpected refresh call'); } },
    });
    assert.equal(await session.getAccessToken(), null);
  }
});
test('short-lived but unexpired access-only cookie remains usable', async () => {
  const token = jwt(20);
  const session = moduleAt('lib/auth/session.ts', {
    'next/headers': { cookies: async () => ({
      get: name => name === 'aqlyra_access_token' ? { value: token } : undefined,
    }) },
    '@/lib/api/backend': { backendUrl: () => { throw new Error('Unexpected refresh call'); } },
  });
  assert.equal(await session.getAccessToken(), token);
});

const backend = { backendUrl: path => 'https://backend.invalid' + path,
  readJson: async response => { try { return await response.json(); } catch { return null; } } };
const actualSession = moduleAt('lib/auth/session.ts', {
  'next/headers': { cookies: async () => { throw new Error('Unexpected cookie access'); } },
  '@/lib/api/backend': backend,
});
function harness(profile = user) {
  const mutations = []; let requests = 0;
  const session = { tokenRemainingSeconds: actualSession.tokenRemainingSeconds };
  for (const name of ['setAccessToken', 'setRefreshToken', 'clearRefreshToken', 'clearEmailVerificationToken']) {
    session[name] = async (...args) => mutations.push([name, ...args]);
  }
  const { completeAuthentication } = moduleAt('lib/auth/complete-authentication.ts', {
    'next/server': { NextResponse: Response }, '@/lib/api/backend': backend,
    '@/lib/auth/session': session, '@/lib/auth/user-response': validUser,
  }, { fetch: async () => { requests++; return Response.json(profile); } });
  return { mutations, requests: () => requests,
    run: (data, options, status = 200) => completeAuthentication(Response.json(data, { status }), 'Sign-in failed', options) };
}
for (const value of [null, 'string', [], 23, {}, { access_token: 123 }, { access_token: jwt(-10) }]) {
  test(`invalid token response ${JSON.stringify(value)} writes no cookies`, async () => {
    const h = harness(); const r = await h.run(value);
    assert.equal(r.status, 502); assert.equal(h.mutations.length, 0);
    assert.match(r.headers.get('cache-control'), /no-store/);
  });
}
for (const profile of [null, {}, { ...user, id: ' ' }, { ...user, is_active: false }, { ...user, email: null }]) {
  test(`invalid legacy profile ${JSON.stringify(profile)} writes no cookies`, async () => {
    const h = harness(profile); const r = await h.run({ access_token: jwt(300) });
    assert.equal(r.status, 502); assert.equal(h.mutations.length, 0);
  });
}
test('invalid embedded identity fails without legacy fallback', async () => {
  const h = harness(); const r = await h.run({ access_token: jwt(300), user: { id: 'x', username: 'x' } });
  assert.equal(r.status, 502); assert.equal(h.requests(), 0); assert.equal(h.mutations.length, 0);
});
for (const ticket of ['', 123, 'malformed', jwt(-10)]) {
  test('bad refresh ticket cannot leave a partial access session', async () => {
    const h = harness(); const r = await h.run({ access_token: jwt(300), refresh_token: ticket, user });
    assert.equal(r.status, 502); assert.equal(h.mutations.length, 0);
  });
}
test('valid modern login writes cookies but never exposes tokens', async () => {
  const h = harness(); const r = await h.run({ access_token: jwt(300), refresh_token: jwt(3600), user });
  assert.equal(r.status, 200); assert.equal(h.requests(), 0);
  assert.deepEqual(await r.json(), { user });
  assert.deepEqual(h.mutations.map(x => x[0]), ['setAccessToken', 'setRefreshToken', 'clearEmailVerificationToken']);
});
test('valid legacy login fetches identity before writing cookies', async () => {
  const h = harness(); const r = await h.run({ access_token: jwt(300) });
  assert.equal(r.status, 200); assert.equal(h.requests(), 1);
  assert.equal(h.mutations[0][0], 'setAccessToken');
});
test('remember false discards refresh ticket and maintains session-only login', async () => {
  const h = harness(); const r = await h.run({ access_token: jwt(300), refresh_token: 'unused', user }, { remember: false });
  assert.equal(r.status, 200); assert.equal(h.mutations[0][2].remember, false);
  assert.equal(h.mutations[1][0], 'clearRefreshToken');
});
test('upstream error cannot echo password inputs or bearer tokens', async () => {
  const h = harness(); const r = await h.run({ access_token: 'secret', detail: [{ input: 'password', msg: 'bad' }] }, {}, 422);
  assert.equal(r.status, 422); assert.deepEqual(await r.json(), { detail: 'Sign-in failed' });
  assert.match(r.headers.get('cache-control'), /no-store/); assert.equal(h.mutations.length, 0);
});
for (const route of ['login', 'google']) {
  for (const input of [null, [], 'text', {}, { email: 'x', password: 123 }, { credential: 123 }]) {
    test(`${route}: invalid JSON shape is 400 without forwarding credentials`, async () => {
      let calls = 0;
      const { POST } = moduleAt(`app/api/auth/${route}/route.ts`, {
        'next/server': { NextResponse: Response },
        '@/lib/security/origin': { hasTrustedRequestOrigin: () => true },
        '@/lib/security/request-body': { readBoundedJson: async () => input, RequestBodyTooLargeError: class extends Error {} },
        '@/lib/security/client-ip': { trustedProxyClientIp: () => null },
        '@/lib/api/backend': backend, '@/lib/auth/complete-authentication': {},
      }, { fetch: async () => { calls++; throw new Error('must not fetch'); } });
      const r = await POST(new Request('https://app.invalid', { method: 'POST' }));
      assert.equal(r.status, 400); assert.equal(calls, 0);
    });
  }
}
