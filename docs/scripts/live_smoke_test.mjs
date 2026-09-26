// End-to-end smoke test of the deployed Lexora backend through the public
// gateway, using the eleven test accounts from docs/SEED_TEST_DATA.md.
//
//   node docs/scripts/live_smoke_test.mjs                       # against https://lexora.duckdns.org
//   BASE=http://localhost:8083 node docs/scripts/live_smoke_test.mjs
//
// Read-only except for one admin round-trip on service-juridique (creates a
// direction centrale + direction + departement with a ZZT-<timestamp> code,
// checks the dashboard counters move, then deletes all three). Exit code 1 if
// any check fails. Needs Node 18+.
const BASE = (process.env.BASE || 'https://lexora.duckdns.org').replace(/\/$/, '');
const PW = 'Test1234!';

const ACCOUNTS = {
  admin: ['admin@sonatrach.dz', 'admin'],
  vp: ['vp@sonatrach.dz', 'vice_presedent'],
  dd: ['dd@sonatrach.dz', 'directeur_direction'],
  rd: ['rd@sonatrach.dz', 'responsable_departement'],
  agent: ['agent@lexora.test', 'agent'],
  dc: ['dc@lexora.test', 'directeur_centrale'],
  adc: ['adc@lexora.test', 'assistant_directeur_centrale'],
  dda: ['dda@lexora.test', 'directeur_direction_activite'],
  ddiv: ['ddiv@lexora.test', 'directeur_division_activite'],
  rdd: ['rdd@lexora.test', 'responsable_direction_division'],
  rdepd: ['rdepd@lexora.test', 'responsable_departement_division'],
};

const results = [];
const ok = (group, name, detail = '') => results.push({ group, name, pass: true, detail });
const ko = (group, name, detail = '') => results.push({ group, name, pass: false, detail });

async function call(method, path, { body, token } = {}) {
  const headers = {};
  if (body) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = 'Bearer ' + token;
  try {
    const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(25000) });
    const text = await res.text();
    let json; try { json = JSON.parse(text); } catch { json = { raw: text.slice(0, 200) }; }
    return { status: res.status, json };
  } catch (e) {
    return { status: 0, json: { error: e.message } };
  }
}
const short = (r) => `${r.status} ${JSON.stringify(r.json).slice(0, 140)}`;
const isGatewayDown = (r) => r.status === 503 && r.json && r.json.error === 'Service Unavailable';
const expect = (group, name, r, cond, extra = '') => (cond ? ok(group, name, extra) : ko(group, name, isGatewayDown(r) ? '503 from gateway: service not registered in Eureka' : short(r)));

(async () => {
  // ---------- 1. auth: every account logs in with the shared password ----------
  const tok = {};
  const user = {};
  for (const [key, [email, role]] of Object.entries(ACCOUNTS)) {
    const r = await call('POST', '/auth/login/', { body: { email, password: PW } });
    if (r.status === 200 && r.json.status === 'success' && r.json.access) {
      tok[key] = r.json.access; user[key] = r.json;
      expect('auth', `login ${email}`, r, r.json.role === role, `role=${r.json.role} id=${r.json.user_id}`);
    } else ko('auth', `login ${email}`, short(r));
  }
  if (!tok.admin || !tok.rd) { report(); process.exit(1); }

  let r = await call('POST', '/auth/login/', { body: { email: ACCOUNTS.rd[0], password: 'wrong' } });
  expect('auth', 'wrong password rejected', r, r.status === 401);
  r = await call('GET', '/auth/users/me/', { token: tok.ddiv });
  expect('auth', 'GET /auth/users/me/ (ddiv) carries structure + division ids', r, r.status === 200 && r.json.data?.structure_id && r.json.data?.division_activite_id);
  r = await call('GET', '/auth/all_users/', { token: tok.admin });
  expect('auth', 'admin GET /auth/all_users/ lists >= 11 users', r, r.status === 200 && r.json.count >= 11, `count=${r.json.count}`);
  r = await call('GET', '/auth/all_users/', { token: tok.rd });
  expect('auth', 'non-admin GET /auth/all_users/ is refused', r, r.status === 403 || r.status === 401);
  r = await call('GET', '/auth/all_users/5/', { token: tok.rd });
  expect('auth', 'profile lookup used by Node middleware works for non-admin', r, r.status === 200 && r.json.email);

  // ---------- 2. CLM: contract visibility per role ----------
  const expectTotal = { rd: 2, dd: 2, admin: 2, agent: 2, vp: 0, dc: 0 };
  for (const [key, total] of Object.entries(expectTotal)) {
    r = await call('GET', '/clm/contrats/', { token: tok[key] });
    expect('clm', `${key} sees ${total} contract(s)`, r, r.status === 200 && r.json.total === total, `total=${r.json.total}`);
  }
  r = await call('GET', '/clm/contrats/1/', { token: tok.rd });
  // detail envelope: { success, contrat, metadonnees, risques: { total, non_resolus, ... }, escalade, ... }
  expect('clm', 'rd contract 1 detail: 2 risks + penalites metadata', r,
    r.status === 200 && r.json?.risques?.total === 2 && r.json?.metadonnees?.penalites_retard,
    `risques.total=${r.json?.risques?.total}`);
  r = await call('GET', '/clm/contrats/1/', { token: tok.dc });
  expect('clm', 'dc cannot open a contract outside its direction centrale', r, r.status === 403 || r.status === 404, `status=${r.status}`);

  // ---------- 3. affectation ----------
  r = await call('GET', '/affectation/users/directeurs-activite/non-affectes/', { token: tok.admin });
  expect('affectation', 'vp listed among directeurs sans activité', r, r.status === 200 && JSON.stringify(r.json).includes('vp@sonatrach.dz'));
  r = await call('GET', '/affectation/users/directeurs-centrale/affectes/', { token: tok.admin });
  expect('affectation', 'dc listed among directeurs centrale affectés', r, r.status === 200 && JSON.stringify(r.json).includes('dc@lexora.test'));

  // ---------- 4. service-juridique: org structure + dashboard (admin round-trip) ----------
  r = await call('GET', '/juridique/directions-centrales', { token: tok.admin });
  const jurUp = r.status === 200;
  expect('juridique', 'GET /juridique/directions-centrales', r, jurUp, `count=${r.json.count}`);
  if (jurUp) {
    r = await call('GET', '/juridique/dashboard/counters', { token: tok.rd });
    const base = r.json?.data;
    expect('juridique', 'dashboard counters (non-admin can read)', r, r.status === 200 && base && Object.keys(base).length === 8, JSON.stringify(base));
    r = await call('POST', '/juridique/directions-centrales', { token: tok.rd, body: { code: 'ZZT-FORBIDDEN', nom: 'x' } });
    expect('juridique', 'non-admin POST refused (403)', r, r.status === 403);

    const stamp = Date.now().toString(36).toUpperCase();
    let dcId, dirId, depId;
    r = await call('POST', '/juridique/directions-centrales', { token: tok.admin, body: { code: `ZZT-DC-${stamp}`, nom: 'Smoke test DC' } });
    dcId = r.json?.data?._id; expect('juridique', 'admin creates direction centrale', r, r.status === 201 && dcId);
    if (dcId) {
      r = await call('POST', '/juridique/directions', { token: tok.admin, body: { code: `ZZT-DIR-${stamp}`, nom: 'Smoke test direction', directionCentrale: dcId } });
      dirId = r.json?.data?._id; expect('juridique', 'admin creates direction under it', r, r.status === 201 && dirId);
    }
    if (dirId) {
      r = await call('POST', '/juridique/departements', { token: tok.admin, body: { code: `ZZT-DEP-${stamp}`, nom: 'Smoke test departement', direction: dirId } });
      depId = r.json?.data?._id; expect('juridique', 'admin creates departement under it', r, r.status === 201 && depId);
    }
    if (base && depId) {
      r = await call('GET', '/juridique/dashboard/counters', { token: tok.admin });
      const d = r.json?.data || {};
      expect('juridique', 'dashboard counters moved by +1/+1/+1', r,
        d.directionsCentrales === base.directionsCentrales + 1 && d.directions === base.directions + 1 && d.departements === base.departements + 1,
        JSON.stringify(d));
      r = await call('GET', '/juridique/dashboard/directions-par-direction-centrale', { token: tok.admin });
      const row = (r.json?.data || []).find((x) => String(x.directionCentraleId) === String(dcId));
      expect('juridique', 'dashboard grouping shows the new DC with count 1 + name', r, row && row.count === 1 && row.nom === 'Smoke test DC', JSON.stringify(row));
      r = await call('GET', `/juridique/directions-centrales/${dcId}/organigramme`, { token: tok.dd });
      expect('juridique', 'organigramme of the new DC (non-admin read)', r, r.status === 200);
    }
    // cleanup (order matters: departement -> direction -> direction centrale)
    if (depId) { r = await call('DELETE', `/juridique/departements/${depId}`, { token: tok.admin }); expect('juridique', 'cleanup departement', r, r.status === 200); }
    if (dirId) { r = await call('DELETE', `/juridique/directions/${dirId}`, { token: tok.admin }); expect('juridique', 'cleanup direction', r, r.status === 200); }
    if (dcId) { r = await call('DELETE', `/juridique/directions-centrales/${dcId}`, { token: tok.admin }); expect('juridique', 'cleanup direction centrale', r, r.status === 200); }
    if (base) {
      r = await call('GET', '/juridique/dashboard/counters', { token: tok.admin });
      const d = r.json?.data || {};
      expect('juridique', 'dashboard counters back to baseline', r,
        d.directionsCentrales === base.directionsCentrales && d.directions === base.directions && d.departements === base.departements, JSON.stringify(d));
    }
    r = await call('GET', '/juridique/dashboard/activites-breakdown', { token: tok.dda });
    expect('juridique', 'dashboard activites-breakdown', r, r.status === 200 && r.json.data && 'divisions' in r.json.data);
    r = await call('GET', '/juridique/dashboard/counters');
    expect('juridique', 'dashboard without token -> 401', r, r.status === 401);
  }

  // ---------- 5. bib-juridique ----------
  r = await call('GET', '/bib/documents', { token: tok.rd });
  expect('bib', 'GET /bib/documents (rd)', r, r.status === 200);
  r = await call('GET', '/bib/documents');
  expect('bib', 'GET /bib/documents without token -> 401', r, r.status === 401);
  r = await call('GET', '/uploads/');
  expect('bib', '/uploads/ reachable through gateway (not 503)', r, r.status !== 503 && r.status !== 0, `status=${r.status}`);

  // ---------- 6. service-notification ----------
  r = await call('GET', '/notifications/conversations', { token: tok.rd });
  expect('notifications', 'GET /notifications/conversations (rd)', r, r.status === 200 && Array.isArray(r.json));
  r = await call('GET', '/notifications/unread/count', { token: tok.agent });
  expect('notifications', 'GET /notifications/unread/count (agent)', r, r.status === 200);
  r = await call('GET', '/notifications/conversations');
  expect('notifications', 'without token -> 401', r, r.status === 401);
  r = await call('GET', '/notifications/risk-alerts/summary/1');
  expect('notifications', 'risk-alerts summary for contract 1 (public route)', r, r.status === 200);

  report();
  process.exit(results.some((x) => !x.pass) ? 1 : 0);
})();

function report() {
  let group = '';
  for (const x of results) {
    if (x.group !== group) { group = x.group; console.log(`\n[${group}]`); }
    console.log(`  ${x.pass ? 'PASS' : 'FAIL'}  ${x.name}${x.detail ? '   ' + x.detail : ''}`);
  }
  const failed = results.filter((x) => !x.pass).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed against ${BASE}`);
}
