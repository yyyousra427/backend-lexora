// Creates one test account per role that is still missing on the deployed
// Lexora backend, sets its password to the shared test password, and attaches
// the fake-but-valid org ids each role is scoped by. Idempotent: existing
// accounts are only re-checked / re-patched.
const BASE = process.env.BASE || 'https://lexora.duckdns.org';
const PW = 'Test1234!';
const ADMIN = { email: 'admin@sonatrach.dz', password: PW };

const IDS = {
  DEP: '64a000000000000000000001',   // departement  (rd)
  DIR: '64a000000000000000000002',   // direction    (dd, rd)
  ACT: '64a000000000000000000003',   // activite     (dd)
  DC: '64a000000000000000000004',    // direction centrale
  DA: '64a000000000000000000005',    // direction d'activite
  DIVA: '64a000000000000000000006',  // division d'activite
  STRUCT: '64a000000000000000000007' // structure
};

const ACCOUNTS = [
  { email: 'agent@lexora.test', nom: 'Bouzid', prenom: 'Lina', role: 'agent',
    ids: { departement_id: IDS.DEP, direction_id: IDS.DIR } },
  { email: 'dc@lexora.test', nom: 'Cherif', prenom: 'Amine', role: 'directeur_centrale',
    ids: { direction_centrale_id: IDS.DC } },
  { email: 'adc@lexora.test', nom: 'Kaci', prenom: 'Nadia', role: 'assistant_directeur_centrale',
    ids: { direction_centrale_id: IDS.DC } },
  { email: 'dda@lexora.test', nom: 'Ziani', prenom: 'Rachid', role: 'directeur_direction_activite',
    ids: { activite_id: IDS.ACT, direction_activite_id: IDS.DA } },
  { email: 'ddiv@lexora.test', nom: 'Toumi', prenom: 'Samir', role: 'directeur_division_activite',
    ids: { structure_id: IDS.STRUCT, division_activite_id: IDS.DIVA } },
  { email: 'rdd@lexora.test', nom: 'Brahimi', prenom: 'Leila', role: 'responsable_direction_division',
    ids: { structure_id: IDS.STRUCT } },
  { email: 'rdepd@lexora.test', nom: 'Saidi', prenom: 'Mourad', role: 'responsable_departement_division',
    ids: { structure_id: IDS.STRUCT } },
];

async function call(method, path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = 'Bearer ' + token;
  const res = await fetch(BASE + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let json = null;
  const text = await res.text();
  try { json = JSON.parse(text); } catch { json = { raw: text.slice(0, 300) }; }
  return { status: res.status, json };
}

async function login(email, password) {
  const r = await call('POST', '/auth/login/', { email, password });
  return r.status === 200 && r.json.status === 'success' ? r.json : null;
}

const ID_FIELDS = ['activite_id', 'direction_id', 'departement_id', 'direction_centrale_id',
  'structure_id', 'direction_activite_id', 'division_activite_id'];

function summary(u) {
  const ids = ID_FIELDS.filter(f => u[f]).map(f => `${f}=${u[f]}`).join(' ');
  return `role=${u.role} ${ids || '(no org ids)'}`;
}

(async () => {
  const admin = await login(ADMIN.email, ADMIN.password);
  if (!admin) { console.error('admin login failed'); process.exit(1); }
  const AT = admin.access;

  const all = await call('GET', '/auth/all_users/', null, AT);
  if (all.status !== 200) { console.error('all_users failed', all); process.exit(1); }
  const byEmail = new Map(all.json.users.map(u => [u.email, u]));
  console.log(`server has ${all.json.count} users before run`);

  const results = [];
  for (const a of ACCOUNTS) {
    const line = { email: a.email, role: a.role };
    let existing = byEmail.get(a.email);
    let id;
    if (!existing) {
      const c = await call('POST', '/auth/users/create/', { email: a.email, nom: a.nom, prenom: a.prenom, role: a.role }, AT);
      if (c.status !== 201) { line.error = `create ${c.status} ${JSON.stringify(c.json).slice(0, 200)}`; results.push(line); continue; }
      id = c.json.user.id;
      const temp = c.json.credentials.generated_password;
      const fresh = await login(a.email, temp);
      if (!fresh) { line.error = 'login with generated password failed'; results.push(line); continue; }
      const ch = await call('POST', '/auth/password/change/', { old_password: temp, new_password: PW }, fresh.access);
      if (ch.status !== 200) { line.error = `password change ${ch.status} ${JSON.stringify(ch.json).slice(0, 200)}`; results.push(line); continue; }
      line.created = true;
    } else {
      id = existing.id;
      line.created = false;
    }
    line.id = id;

    // ensure role + org ids (PATCH is idempotent)
    const patch = await call('PATCH', `/auth/users/${id}/update/`, { role: a.role, ...a.ids }, AT);
    if (patch.status !== 200) line.patch_error = `${patch.status} ${JSON.stringify(patch.json).slice(0, 200)}`;

    // final check: login with the shared test password
    const chk = await login(a.email, PW);
    if (!chk) { line.error = 'final login with Test1234! FAILED'; results.push(line); continue; }
    line.login_ok = true;
    line.summary = summary(chk);
    results.push(line);
  }

  console.log('\nRESULTS');
  for (const r of results) {
    console.log(`${r.login_ok ? 'OK ' : 'ERR'} ${r.email.padEnd(20)} id=${String(r.id ?? '-').padEnd(3)} ${r.created ? 'created' : 'existed'} ${r.summary || ''} ${r.error || ''} ${r.patch_error ? 'PATCH: ' + r.patch_error : ''}`);
  }
  const after = await call('GET', '/auth/all_users/', null, AT);
  console.log(`\nserver has ${after.json.count} users after run`);
  process.exit(results.some(r => !r.login_ok) ? 2 : 0);
})();
