#!/usr/bin/env node
'use strict';
// Actual Strapi 5 / PostgreSQL and Content Manager, in a disposable copy/database.
// External source, Firecrawl and model responses are controlled fixtures.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');

const newsRoot = path.resolve(__dirname, '..');
const root = path.resolve(process.argv[2] || '/Users/michelvannoort/sites/website/pito/strapi');
const modules = path.join(root, 'node_modules');
const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'pito-firecrawl-strapi-'));
const sessionFile = path.join(appDir, 'session.json');
const checks = [];
let app, maintenance, testDatabase;

async function check(name, fn) {
  await fn(); checks.push({ name, passed: true }); console.log('PASS '+name);
}
function python(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.env.PITO_TEST_PYTHON || 'python3', ['-B', ...args], { cwd: newsRoot, env: process.env });
    let output = '', errors = '';
    child.stdout.on('data', b => output += b); child.stderr.on('data', b => errors += b);
    child.on('error', reject);
    child.on('exit', code => {
      if (code !== 0) return reject(new Error('Python integration driver failed: '+errors.slice(-4000)+output.slice(-2000)));
      try { resolve(JSON.parse(output.trim().split('\n').at(-1))); } catch (error) { reject(error); }
    });
  });
}
async function main() {
  for (const folder of ['src', 'config', 'types', 'database']) {
    if (fs.existsSync(path.join(root, folder))) fs.cpSync(path.join(root, folder), path.join(appDir, folder), { recursive: true });
  }
  fs.cpSync(path.join(newsRoot, 'strapi/automatic-publication-addon/src'), path.join(appDir, 'src'), { recursive: true });
  for (const file of ['package.json', 'tsconfig.json']) fs.copyFileSync(path.join(root, file), path.join(appDir, file));
  fs.symlinkSync(modules, path.join(appDir, 'node_modules'), 'dir');
  fs.symlinkSync(path.join(root, 'resources'), path.join(appDir, 'resources'), 'dir');
  fs.mkdirSync(path.join(appDir, 'public/uploads'), { recursive: true });
  const envPath = path.join(appDir, '.env.test'); fs.writeFileSync(envPath, '', { mode: 0o600 });
  const configured = require(path.join(modules, 'dotenv')).parse(fs.readFileSync(path.join(root, '.env')));
  const host = configured.DATABASE_HOST || 'localhost';
  assert.ok(['localhost', '127.0.0.1', '::1'].includes(host), 'Only a local isolated PostgreSQL test database is allowed');
  maintenance = { host, port: Number(configured.DATABASE_PORT || 5432), user: configured.DATABASE_USERNAME || 'strapi',
                  password: configured.DATABASE_PASSWORD || undefined, database: 'postgres' };
  testDatabase = 'pito_firecrawl_e2e_'+crypto.randomBytes(8).toString('hex');
  const { Client } = require(path.join(modules, 'pg'));
  const client = new Client(maintenance); await client.connect();
  try { await client.query(`CREATE DATABASE "${testDatabase}"`); } finally { await client.end(); }
  const random = () => crypto.randomBytes(32).toString('hex');
  const port = Number(process.env.PITO_E2E_PORT || 1349);
  const session = { appDir, url: `http://127.0.0.1:${port}`, sourceToken: random(), sourceImportToken: random(),
                    readToken: random(), draftToken: random(), sourcePublishedAt: new Date(Date.now()-3600000).toISOString(),
                    email: 'firecrawl-test@example.invalid', password: random()+'!aA1' };
  fs.writeFileSync(sessionFile, JSON.stringify(session), { mode: 0o600 });
  Object.assign(process.env, {
    NODE_ENV: 'development', ENV_PATH: envPath, HOST: '127.0.0.1', PORT: String(port), PUBLIC_URL: session.url,
    DATABASE_CLIENT: 'postgres', DATABASE_HOST: host, DATABASE_PORT: String(maintenance.port), DATABASE_NAME: testDatabase,
    DATABASE_USERNAME: maintenance.user, DATABASE_PASSWORD: maintenance.password || '', DATABASE_SCHEMA: 'public', DATABASE_SSL: 'false',
    APP_KEYS: random()+','+random(), ADMIN_JWT_SECRET: random(), API_TOKEN_SALT: random(), TRANSFER_TOKEN_SALT: random(),
    JWT_SECRET: random(), ENCRYPTION_KEY: random(), CRON_ENABLED: 'false', STRAPI_TELEMETRY_DISABLED: 'true',
    STRAPI_HIDE_STARTUP_MESSAGE: 'true', BROWSER: 'false',
    PITO_NEWS_SOURCE_TOKEN: session.sourceToken, PITO_NEWS_SOURCE_IMPORT_TOKEN: session.sourceImportToken,
    PITO_NEWS_READ_TOKEN: session.readToken, PITO_NEWS_DRAFT_TOKEN: session.draftToken, PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL: '2020-01-01T00:00:00Z', PITO_NEWS_AUTOMATIC_PUBLISH_ENABLED: '1',
  });
  for (const key of ['DATABASE_URL', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'FIRECRAWL_API_KEY', 'OPENAI_API_KEY', 'PITO_WRITER_API_KEY', 'PITO_WRITER_MODEL', 'PITO_NEWS_REVIEW_TOKEN']) delete process.env[key];
  process.chdir(appDir);
  const { compileStrapi, createStrapi } = require(path.join(modules, '@strapi/strapi'));
  console.log('Isolated real Strapi: '+appDir);
  app = createStrapi({ ...await compileStrapi({ appDir }), serveAdminPanel: false });
  await app.load();
  assert.equal(app.config.get('database.connection.connection.database'), testDatabase);
  assert.equal(app.config.get('server.cron.enabled'), false);
  await app.admin.services.user.createFirstAdmin({ email: session.email, password: session.password, firstname: 'LOKALE TEST', lastname: 'REDACTEUR', isActive: true });
  await app.listen();
  const request = async (route, { token, method = 'GET', body } = {}) => {
    const response = await fetch(session.url+route, { method, headers: {
      ...(token ? { Authorization: 'Bearer '+token } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
    }, ...(body === undefined ? {} : { body: JSON.stringify(body) }), signal: AbortSignal.timeout(20000) });
    let data; try { data = await response.json(); } catch { data = null; }
    return { status: response.status, data };
  };
  const login = await request('/admin/login', { method: 'POST', body: { email: session.email, password: session.password } });
  assert.equal(login.status, 200); const adminToken = login.data.data.token;
  const source = { sourceKey: 'firecrawl-e2e-utrecht', name: 'AFZONDERLIJKE LOKALE TESTBRON', url: 'https://www.utrecht.nl/nieuws/',
    feed: 'https://www.utrecht.nl/test-feed', kind: 'Gemeente', active: true, reader: 'firecrawl', discovery: 'rss',
    articleHosts: ['www.utrecht.nl'], municipality: 'utrecht', coverageCandidates: ['utrecht'], articlePathPrefix: '/nieuws/', maxLinks: 5 };
  const imported = () => request('/api/pito-news/sources/import', { method: 'POST', token: session.sourceImportToken, body: { data: source } });
  let sourceDocument;
  await check('Source endpoints reject public, news-reader and worker-write credentials', async () => {
    for (const token of [undefined, session.readToken, session.draftToken, session.sourceImportToken]) {
      assert.equal((await request('/api/pito-news/sources', { token })).status, 401);
    }
    assert.equal((await request('/api/pito-news/sources/import', { method: 'POST', token: session.sourceToken, body: { data: source } })).status, 401);
    assert.equal((await request('/api/pito-news-sources')).status, 404);
  });
  await check('Source import creates one managed Strapi source and preserves it on retry', async () => {
    const first = await imported(); assert.equal(first.status, 201, JSON.stringify(first.data)); sourceDocument = first.data.data.documentId;
    const again = await imported(); assert.equal(again.status, 200); assert.equal(again.data.data.created, false);
    const result = await request('/api/pito-news/sources', { token: session.sourceToken });
    assert.equal(result.status, 200, JSON.stringify(result.data));
    assert.equal(result.data.meta.complete, true); assert.equal(result.data.meta.total, 1);
  });

  const now = new Date(Date.now()-1000).toISOString();
  const quote = 'De gemeente Utrecht opent op maandag een nieuwe wandelroute langs de singel.';
  const data = { externalKey: 'isolated-automatic-e2e', title: 'LOKALE TEST nieuwe wandelroute langs de singel',
    summary: 'In Utrecht komt een nieuwe wandelroute langs de singel beschikbaar voor inwoners.',
    body: 'Wandelaars in Utrecht kunnen binnenkort een route langs de singel volgen. De gemeente heeft de opening voor maandag aangekondigd.\n\nDe nieuwe route biedt inwoners een extra mogelijkheid om langs het water te wandelen.',
    category: 'Samenleving', municipalities: ['utrecht'], provinceWide: false, sensitive: false,
    sourceUrl: 'https://www.utrecht.nl/nieuws/wandelroute', sourceName: 'Gemeente Utrecht',
    sourcePublishedAt: session.sourcePublishedAt, sourceBased: true, origin: 'writer',
    rights: 'Eigen nieuwsbericht op basis van gecontroleerde feiten. Geen bronfoto overgenomen.',
    evidenceReference: 'isolated-test:utrecht', privateEvidence: { sourceUrl: 'https://www.utrecht.nl/nieuws/wandelroute',
      sourceText: quote + ' Aanvullende broninformatie over de route en het gebruik door inwoners.'.repeat(8), fetchedAt: now } };
  const verification = { sourceKey: source.sourceKey, checkedAt: now, note: 'Feiten, gemeente en bronpublicatiedatum gecontroleerd tegen de volledige brontekst.',
    facts: [{ statement: 'Utrecht opent een nieuwe wandelroute.', quote }], municipalityEvidence: [{ slug: 'utrecht', quote }] };
  const automatic = (body={data, verification}, token=session.draftToken) => request('/api/pito-news/automatic-publish', { method: 'POST', token, body });
  let document;
  await check('Unauthorized tokens, malformed evidence and protected client review fields cannot publish', async () => {
    assert.equal((await automatic(undefined, session.readToken)).status, 401);
    assert.equal((await automatic({ data, verification: {} })).status, 400);
    assert.equal((await automatic({ data: {...data, reviewKind: 'automatic'}, verification })).status, 400);
    assert.equal((await request('/api/pito-news/snapshot', {token:session.readToken})).data.meta.total, 0);
  });
  await check('Real Strapi atomically saves evidence, records machine review and publishes once', async () => {
    const result = await automatic(); assert.equal(result.status, 201, JSON.stringify(result.data));
    assert.equal(result.data.data.status, 'published'); document = result.data.data;
    const again = await automatic(); assert.equal(again.status, 200, JSON.stringify(again.data));
    assert.equal(again.data.data.documentId, document.documentId);
    const snapshot = await request('/api/pito-news/snapshot', {token:session.readToken});
    assert.equal(snapshot.status, 200, JSON.stringify(snapshot.data));
    assert.equal(snapshot.data.meta.total, 1);
    const row = snapshot.data.data.articles[0];
    assert.equal(row.humanReviewed, false); assert.equal(row.reviewKind, 'automatic'); assert.equal(row.authorType, 'automatic');
    assert.equal(row.author, 'PITO Nieuwsredactie');
    for(const field of ['privateEvidence','automaticReview','reviewer','reviewedByAdminId']) assert.ok(!(field in row));
    await python(['-c', `import sys,json,datetime; sys.path.insert(0,${JSON.stringify(newsRoot)}); import strapi_news; s=json.load(open(sys.argv[1])); r=strapi_news.request_json(s['url'],'/api/pito-news/snapshot',s['readToken']); a=strapi_news.validate_snapshot(r,datetime.datetime.now(datetime.timezone.utc)); assert len(a.articles)==1 and a.articles[0]['humanReviewed'] is False; print(json.dumps({'validatedAutomaticSnapshot':True}))`, sessionFile]);
  });
  const cm = '/content-manager/collection-types/api::pito-news-article.pito-news-article';
  await check('Withdrawn automatic articles are never resurrected by bot retries', async () => {
    const result = await request(cm+'/'+document.documentId+'/actions/unpublish', { token: adminToken, method: 'POST', body: {} });
    assert.equal(result.status, 200, JSON.stringify(result.data));
    const retry=await automatic(); assert.equal(retry.status,200); assert.equal(retry.data.data.status,'draft');
    assert.equal((await request('/api/pito-news/snapshot', {token:session.readToken})).data.meta.total,0);
  });
  await check('The original concept endpoint still cannot approve or publish', async () => {
    const draft=await request('/api/pito-news/drafts',{token:session.draftToken, method:'POST',body:{data:{...data,externalKey:'isolated-concept',slug:'afzonderlijk-concept'}}});
    assert.equal(draft.status,201,JSON.stringify(draft.data));
    assert.equal(draft.data.data.status,'draft');
    assert.equal((await request('/api/pito-news/snapshot',{token:session.readToken})).data.meta.total,0);
  });
  await check('A real editor explicitly approves without entering a date, then publishes', async () => {
    const lookup=await request(cm+'?page=1&pageSize=20',{token:adminToken});
    const doc=lookup.data.results.find(row=>row.slug==='afzonderlijk-concept');
    assert.ok(doc);
    const route=cm+'/'+doc.documentId;
    const direct=await request(route+'/actions/publish',{token:adminToken,method:'POST',body:{}});
    assert.equal(direct.status,400);assert.match(direct.data.error.message,/approved.*Save/);
    const missing=await request(route,{token:adminToken,method:'PUT',body:{reviewStatus:'approved'}});
    assert.equal(missing.status,400);assert.match(missing.data.error.message,/notitie/);
    const reviewed=await request(route,{token:adminToken,method:'PUT',body:{reviewStatus:'approved',reviewNote:'Werkelijke inhoudscontrole van deze geïsoleerde test door de testredacteur.'}});
    assert.equal(reviewed.status,200,JSON.stringify(reviewed.data));
    const approved=await request(route,{token:adminToken});
    assert.ok(Date.parse(approved.data.data.verifiedAt)<=Date.now());
    assert.equal(approved.data.data.reviewStatus,'approved');
    const published=await request(route+'/actions/publish',{token:adminToken,method:'POST',body:{}});
    assert.equal(published.status,200,JSON.stringify(published.data));
    const snapshot=await request('/api/pito-news/snapshot',{token:session.readToken});
    assert.equal(snapshot.data.data.articles.find(a=>a.documentId===doc.documentId).humanReviewed,true);
    const edited=await request(route,{token:adminToken,method:'PUT',body:{body:data.body+' Een gecontroleerde correctie.',reviewStatus:'approved'}});
    assert.equal(edited.status,200);assert.equal(edited.data.data.reviewStatus,'needs_review');
    assert.equal((await request(route+'/actions/publish',{token:adminToken,method:'POST',body:{}})).status,400);
    await request(route+'/actions/unpublish',{token:adminToken,method:'POST',body:{}});
  });
  await check('An identical untouched bot concept can publish later without creating a duplicate', async () => {
    const draftData={...data,externalKey:'untouched-promotion',slug:'untouched-promotion'};
    const saved=await request('/api/pito-news/drafts',{token:session.draftToken,method:'POST',body:{data:draftData}});
    assert.equal(saved.status,201);
    // JSON key order can change when the bot reloads its stored payload.
    const reordered=Object.fromEntries(Object.entries(draftData).reverse());
    const promoted=await automatic({data:reordered,verification});
    assert.equal(promoted.status,200,JSON.stringify(promoted.data));
    assert.equal(promoted.data.data.status,'published');
    assert.equal(promoted.data.data.documentId,saved.data.data.documentId);
    await request(cm+'/'+saved.data.data.documentId+'/actions/unpublish',{token:adminToken,method:'POST',body:{}});
    assert.equal((await automatic({data:draftData,verification})).data.data.status,'draft');
  });
  await check('Changed proposals and human-saved bot concepts cannot be auto-published', async () => {
    for(const humanSave of [false,true]) {
      const draftData={...data,externalKey:'preserved-'+humanSave,slug:'preserved-'+humanSave};
      const saved=await request('/api/pito-news/drafts',{token:session.draftToken,method:'POST',body:{data:draftData}});
      assert.equal(saved.status,201);
      if(humanSave) assert.equal((await request(cm+'/'+saved.data.data.documentId,{token:adminToken,method:'PUT',body:{summary:'Een handmatig aangepaste intro door de testredacteur.'}})).status,200);
      const result=await automatic({data:humanSave?draftData:{...draftData,title:'Een ander voorgesteld artikel'},verification});
      assert.equal(result.status,200,JSON.stringify(result.data));
      assert.equal(result.data.data.status,'draft');
    }
  });
  await check('Existing dashboard layout is preserved while the approval date becomes server-managed', async () => {
    const module=require(path.join(appDir,'dist/src/pito-news/admin-config.js'));
    const service=app.plugin('content-manager').service('content-types');
    const model=service.findContentType('api::pito-news-article.pito-news-article');
    const config=await service.findConfiguration(model);
    config.metadatas.verifiedAt.edit.description='Oude datumhulp';
    config.metadatas.verifiedAt.edit.editable=true;
    config.metadatas.body.edit.label='Mijn eigen artikellabel';
    await service.updateConfiguration(model,{settings:config.settings,metadatas:config.metadatas,layouts:config.layouts});
    await module.initializeNewsAdminConfiguration(app);
    const updated=await service.findConfiguration(model);
    assert.equal(updated.metadatas.verifiedAt.edit.editable,false);
    assert.match(updated.metadatas.verifiedAt.edit.description,/automatisch/);
    assert.equal(updated.metadatas.body.edit.label,'Mijn eigen artikellabel');
    assert.deepEqual(updated.layouts,config.layouts);
  });
  // Enable the independent reviewer only after exercising the legacy deployment.
  // The writer and reviewer now have separate capabilities on the same real API.
  const reviewToken=random();
  process.env.PITO_NEWS_REVIEW_TOKEN=reviewToken;
  const queue=(query='',token=reviewToken)=>request('/api/pito-news/review-queue'+query,{token});
  const decision=(body,token=reviewToken)=>request('/api/pito-news/review-decision',{token,method:'POST',body});
  const freshEvidence=()=>({...data.privateEvidence,fetchedAt:new Date(Date.now()-2000).toISOString()});
  const freshVerification=()=>({...verification,checkedAt:new Date(Date.now()-1000).toISOString()});
  const reviewerDrafts=new Map();
  const oldFetch=new Date(Date.now()-3*86400000).toISOString();
  const oldPublication=new Date(Date.now()-15*86400000).toISOString();
  for(const key of ['refresh','hold','stale','human','old-source']) {
    const article={...data,externalKey:'reviewer-'+key,slug:'reviewer-'+key,
      ...(key==='refresh'?{privateEvidence:{...data.privateEvidence,fetchedAt:oldFetch}}:{}),
      ...(key==='old-source'?{sourcePublishedAt:oldPublication}:{})};
    const saved=await request('/api/pito-news/drafts',{token:session.draftToken,method:'POST',body:{data:article}});
    assert.equal(saved.status,201,JSON.stringify(saved.data));
    reviewerDrafts.set(key,{article,documentId:saved.data.data.documentId});
  }
  const allQueued=async(limit=2)=>{
    let cursor,rows=[];const seen=new Set();
    for(let page=0;page<100;page++) {
      const result=await queue('?limit='+limit+(cursor?'&cursor='+encodeURIComponent(cursor):''));
      assert.equal(result.status,200,JSON.stringify(result.data));
      assert.ok(Array.isArray(result.data.data));assert.ok(result.data.data.length<=limit);
      for(const row of result.data.data) {
        assert.ok(!seen.has(row.documentId),'Pagination must not repeat a draft');
        seen.add(row.documentId);rows.push(row);
      }
      const next=result.data.meta.nextCursor;
      if(!next) {assert.equal(result.data.meta.complete,true);return rows;}
      assert.equal(result.data.meta.complete,false);
      assert.notEqual(next,cursor);cursor=next;
    }
    throw new Error('Review queue pagination did not terminate');
  };
  let initialQueue;
  await check('Reviewer credentials are separate and writer can only submit concepts',async()=>{
    for(const token of [null,session.draftToken,session.sourceToken,session.readToken,session.sourceImportToken]) {
      assert.equal((await queue('',token)).status,401);
      assert.equal((await decision({documentId:'unknown',version:'unknown',decision:'hold',note:'Deze geïsoleerde controle laat het artikel voorlopig als concept staan.'},token)).status,401);
    }
    assert.equal((await automatic({data:{...data,externalKey:'writer-bypass',slug:'writer-bypass'},verification})).status,403);
    assert.equal((await request('/api/pito-news/drafts',{token:reviewToken,method:'POST',body:{data}})).status,401);
    assert.equal((await request('/api/pito-news/snapshot',{token:reviewToken})).status,401);
  });
  await check('The reviewer queue paginates exact saved versions with source configuration',async()=>{
    assert.equal((await queue('?limit=21')).status,400);
    assert.equal((await queue('?populate=*')).status,400);
    assert.equal((await queue('?limit=2&limit=3')).status,400);
    assert.equal((await queue('?cursor=invalid%2Fcursor')).status,400);
    initialQueue=await allQueued();
    assert.deepEqual(initialQueue.map(row=>row.documentId),initialQueue.map(row=>row.documentId).sort());
    for(const [key,fixture] of reviewerDrafts) {
      const row=initialQueue.find(row=>row.documentId===fixture.documentId);
      assert.ok(row,'Queued reviewer fixture: '+key);assert.equal(row.eligible,true);
      assert.match(row.version,/^[a-f0-9]{64}$/);
      assert.equal(row.article.body,fixture.article.body);assert.equal(row.article.sourceUrl,fixture.article.sourceUrl);
      assert.ok(row.sources.some(item=>item.sourceKey===source.sourceKey));
      assert.equal(row.alreadyChecked,false);assert.equal(row.lastReview,null);
      fixture.queued=row;
    }
    // A previous human save is visible for the reviewer but cannot be published.
    const protectedRow=initialQueue.find(row=>row.article.externalKey==='preserved-true');
    assert.ok(protectedRow);assert.equal(protectedRow.eligible,false);assert.ok(protectedRow.reasons.length);
    assert.ok(!initialQueue.some(row=>row.documentId===document.documentId),'Withdrawals are excluded from the queue');
  });
  await check('Reviewer publication requires current evidence and cannot replace stored article text',async()=>{
    const fixture=reviewerDrafts.get('refresh');
    const base={documentId:fixture.documentId,version:fixture.queued.version,decision:'publish'};
    assert.equal((await decision(base)).status,400);
    assert.equal((await decision({...base,verification:freshVerification()})).status,400,'Stale original fetch cannot be reused as fresh evidence');
    assert.equal((await decision({...base,verification:freshVerification(),evidence:{...freshEvidence(),sourceUrl:'https://www.utrecht.nl/nieuws/ander-bericht'}})).status,400);
    assert.equal((await decision({...base,verification:freshVerification(),evidence:{...freshEvidence(),fetchedAt:new Date(Date.now()+3600000).toISOString()}})).status,400);
    assert.equal((await decision({...base,verification:freshVerification(),evidence:freshEvidence(),data:{title:'Door reviewer overschreven'}})).status,400);
    assert.equal((await decision({...base,verification:{...freshVerification(),facts:[{statement:'Een verzonnen conclusie zonder bronbewijs.',quote:'Dit letterlijke fragment komt helemaal niet voor in de bron.'}]},evidence:freshEvidence()})).status,400);
    const stored=await request(cm+'/'+fixture.documentId,{token:adminToken});
    assert.equal(stored.status,200);assert.equal(stored.data.data.body,fixture.article.body);
    assert.equal(stored.data.data.reviewStatus,'needs_review');
  });
  await check('A hold records the control report while preserving the original concept',async()=>{
    const fixture=reviewerDrafts.get('hold');
    const note='De volledige brontekst geeft onvoldoende zekerheid over de openingsdatum; daarom blijft dit artikel een concept.';
    const result=await decision({documentId:fixture.documentId,version:fixture.queued.version,decision:'hold',note});
    assert.equal(result.status,200,JSON.stringify(result.data));assert.equal(result.data.data.status,'draft');
    const row=(await allQueued()).find(row=>row.documentId===fixture.documentId);
    assert.ok(row);assert.equal(row.alreadyChecked,true);assert.equal(row.lastReview.decision,'hold');assert.equal(row.lastReview.note,note);
    assert.equal(row.version,fixture.queued.version,'A hold report must not invalidate the content version');
    const stored=await request(cm+'/'+fixture.documentId,{token:adminToken});
    assert.equal(stored.data.data.reviewStatus,'needs_review');assert.equal(stored.data.data.body,fixture.article.body);
    assert.equal(stored.data.data.reviewNote,note);
  });
  await check('Reviewer decisions reject changed versions and preserve human-saved drafts',async()=>{
    const fixture=reviewerDrafts.get('stale');
    const edited=await request(cm+'/'+fixture.documentId,{token:adminToken,method:'PUT',body:{summary:'Door een werkelijk aangemelde redacteur gewijzigde samenvatting.'}});
    assert.equal(edited.status,200,JSON.stringify(edited.data));
    const stale=await decision({documentId:fixture.documentId,version:fixture.queued.version,decision:'publish',verification:freshVerification(),evidence:freshEvidence()});
    assert.equal(stale.status,409,JSON.stringify(stale.data));
    const row=(await allQueued()).find(row=>row.documentId===fixture.documentId);
    assert.ok(row);assert.notEqual(row.version,fixture.queued.version);assert.equal(row.eligible,false);
    const current=await decision({documentId:fixture.documentId,version:row.version,decision:'publish',verification:freshVerification(),evidence:freshEvidence()});
    assert.equal(current.status,403,JSON.stringify(current.data));
    const other=reviewerDrafts.get('human');
    assert.equal((await request(cm+'/'+other.documentId,{token:adminToken,method:'PUT',body:{body:other.article.body,reviewNote:'Eigen inhoudelijke opmerking van de menselijke testredacteur.'}})).status,200);
    const savedOnly=(await allQueued()).find(row=>row.documentId===other.documentId);
    assert.ok(savedOnly);assert.equal(savedOnly.eligible,false,'An editor Save protects even unchanged article text');
    assert.equal((await decision({documentId:other.documentId,version:savedOnly.version,decision:'publish',verification:freshVerification(),evidence:freshEvidence()})).status,403);
    const hold=await decision({documentId:other.documentId,version:savedOnly.version,decision:'hold',note:'De controlebot laat de menselijke bewerking staan en vraagt de redacteur deze te beoordelen.'});
    assert.equal(hold.status,200,JSON.stringify(hold.data));
    const afterHold=await request(cm+'/'+other.documentId,{token:adminToken});
    assert.equal(afterHold.data.data.reviewNote,'Eigen inhoudelijke opmerking van de menselijke testredacteur.');
  });
  await check('A fresh reviewer fetch cannot disguise an out-of-window source publication date',async()=>{
    const fixture=reviewerDrafts.get('old-source');
    const result=await decision({documentId:fixture.documentId,version:fixture.queued.version,decision:'publish',verification:freshVerification(),evidence:freshEvidence()});
    assert.equal(result.status,400,JSON.stringify(result.data));
    const stored=await request(cm+'/'+fixture.documentId,{token:adminToken});
    assert.equal(Date.parse(stored.data.data.sourcePublishedAt),Date.parse(oldPublication));
    assert.equal(stored.data.data.reviewStatus,'needs_review');
  });
  let reviewerPublishedBody;
  await check('The reviewer publishes an existing concept using fresh proof, without changing identity or text',async()=>{
    const fixture=reviewerDrafts.get('refresh');
    reviewerPublishedBody={documentId:fixture.documentId,version:fixture.queued.version,decision:'publish',verification:freshVerification(),evidence:freshEvidence()};
    const published=await decision(reviewerPublishedBody);
    assert.equal(published.status,200,JSON.stringify(published.data));assert.equal(published.data.data.documentId,fixture.documentId);
    assert.equal(published.data.data.status,'published');assert.equal(published.data.data.newlyPublished,true);
    const retried=await decision(reviewerPublishedBody);
    assert.equal(retried.status,200,JSON.stringify(retried.data));assert.equal(retried.data.data.documentId,fixture.documentId);
    assert.equal(retried.data.data.newlyPublished,false);
    assert.equal((await decision({...reviewerPublishedBody,version:'0'.repeat(64)})).status,409,'Published state must not make an unrelated stale decision succeed');
    const snapshot=await request('/api/pito-news/snapshot',{token:session.readToken});
    assert.equal(snapshot.status,200,JSON.stringify(snapshot.data));
    const row=snapshot.data.data.articles.find(item=>item.documentId===fixture.documentId);
    assert.ok(row);assert.equal(row.body,fixture.article.body);assert.equal(row.title,fixture.article.title);
    assert.equal(row.humanReviewed,false);assert.equal(row.reviewKind,'automatic');assert.equal(row.authorType,'automatic');
    for(const field of ['privateEvidence','automaticReview','reviewer','reviewedByAdminId','lastReview']) assert.ok(!(field in row));
    assert.ok(!(await allQueued()).some(row=>row.documentId===fixture.documentId),'Published articles leave the reviewer queue');
    await python(['-c', `import sys,json,datetime; sys.path.insert(0,${JSON.stringify(newsRoot)}); import strapi_news; s=json.load(open(sys.argv[1])); r=strapi_news.request_json(s['url'],'/api/pito-news/snapshot',s['readToken']); a=strapi_news.validate_snapshot(r,datetime.datetime.now(datetime.timezone.utc)); assert any(x['humanReviewed'] is False and x['body']==${JSON.stringify(fixture.article.body)} for x in a.articles); print(json.dumps({'validatedReviewerSnapshot':True}))`,sessionFile]);
  });
  await check('Reviewer retries cannot resurrect a manually withdrawn article',async()=>{
    const fixture=reviewerDrafts.get('refresh');
    const unpublished=await request(cm+'/'+fixture.documentId+'/actions/unpublish',{token:adminToken,method:'POST',body:{}});
    assert.equal(unpublished.status,200,JSON.stringify(unpublished.data));
    const replay=await decision(reviewerPublishedBody);
    assert.equal(replay.status,409,JSON.stringify(replay.data));
    assert.ok(!(await allQueued()).some(row=>row.documentId===fixture.documentId));
    const snapshot=await request('/api/pito-news/snapshot',{token:session.readToken});
    assert.ok(!snapshot.data.data.articles.some(row=>row.documentId===fixture.documentId));
  });
  const result={testedAt:new Date().toISOString(),actualStrapi:true,isolatedDatabase:testDatabase,checks};
  fs.writeFileSync(path.join(newsRoot,'reports/reviewer-strapi-e2e-20261029.json'),JSON.stringify(result,null,2));
  console.log(`Real automatic Strapi integration: ${checks.length} checks passed.`);
}
main().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (app) await app.destroy();
  if (testDatabase && maintenance) {
    const { Client } = require(path.join(modules, 'pg')); const client = new Client(maintenance);
    try { await client.connect(); await client.query(`DROP DATABASE IF EXISTS "${testDatabase}" WITH (FORCE)`); } finally { await client.end(); }
  }
  process.exit(process.exitCode || 0);
});
