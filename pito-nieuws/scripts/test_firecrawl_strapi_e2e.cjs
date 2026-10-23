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
  fs.cpSync(path.join(newsRoot, 'strapi/source-addon/src'), path.join(appDir, 'src'), { recursive: true });
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
  const port = Number(process.env.PITO_E2E_PORT || 1347);
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
    PITO_NEWS_READ_TOKEN: session.readToken, PITO_NEWS_DRAFT_TOKEN: session.draftToken,
  });
  for (const key of ['DATABASE_URL', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'FIRECRAWL_API_KEY', 'OPENAI_API_KEY', 'PITO_WRITER_API_KEY', 'PITO_WRITER_MODEL']) delete process.env[key];
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
  const driver = () => python([path.join(newsRoot, 'tests/firecrawl_strapi_driver.py'), sessionFile, 'pipeline']);
  let document;
  const cm = '/content-manager/collection-types/api::pito-news-article.pito-news-article';
  await check('Real Strapi source -> controlled Firecrawl -> saved source archive -> real Strapi draft', async () => {
    const report = await driver(); assert.deepEqual(report.statuses, { drafted: 1 }); assert.equal(report.draftSync.synced, 1);
    assert.equal(report.firecrawlRequests, 1); assert.equal(report.publishedLocally, 0);
    assert.equal(report.archivedDocuments, 1); assert.equal(report.writerFirecrawlRequests, 0);
    const result = await request(cm+'?page=1&pageSize=10', { token: adminToken });
    assert.equal(result.status, 200, JSON.stringify(result.data));
    const rows = result.data.results || result.data.data; assert.equal(rows.length, 1); document = rows[0];
    assert.equal(document.reviewStatus, 'needs_review'); assert.equal(document.publishedAt, null);
    assert.equal((await request('/api/pito-news/snapshot', { token: session.readToken })).data.data.articles.length, 0);
  });
  await check('A second pipeline run does not call Firecrawl or create another CMS article', async () => {
    const report = await driver(); assert.equal(report.firecrawlRequests, 0); assert.equal(report.draftSync.attempted, 0);
    assert.equal((await request(cm+'?page=1&pageSize=10', { token: adminToken })).data.results.length, 1);
  });
  await check('Worker credentials cannot publish the automatically created concept', async () => {
    assert.equal((await request('/api/pito-news/automatic-publish', { token: session.draftToken, method: 'POST', body: {} })).status, 403);
    assert.equal((await request(cm+'/'+document.documentId+'/actions/publish', { token: adminToken, method: 'POST', body: {} })).status, 400);
  });
  await check('CMS editor review and Publish expose the article through the real news adapter', async () => {
    const reviewed = await request(cm+'/'+document.documentId, { token: adminToken, method: 'PUT', body: {
      reviewStatus: 'approved', verifiedAt: new Date(Date.now()-1000).toISOString(), reviewNote: 'Technische controle van gelabelde testinhoud in een afzonderlijke database.',
      dateNote: 'Alle datums horen bij deze lokale technische test.', authorName: 'Lokale testredactie'
    } }); assert.equal(reviewed.status, 200, JSON.stringify(reviewed.data));
    const published = await request(cm+'/'+document.documentId+'/actions/publish', { token: adminToken, method: 'POST', body: {} });
    assert.equal(published.status, 200, JSON.stringify(published.data));
    const snapshot = await request('/api/pito-news/snapshot', { token: session.readToken });
    assert.equal(snapshot.data.data.articles.length, 1);
    await python(['-c', `import sys,json,datetime; sys.path.insert(0,${JSON.stringify(newsRoot)}); import strapi_news; s=json.load(open(sys.argv[1])); r=strapi_news.request_json(s['url'],'/api/pito-news/snapshot',s['readToken']); a=strapi_news.validate_snapshot(r,datetime.datetime.now(datetime.timezone.utc)); assert len(a.articles)==1; print(json.dumps({'validatedRealSnapshot':True}))`, sessionFile]);
  });
  await check('Actual PITO website displays the Strapi article through location, topic, search, period and sort filters', async () => {
    const report=await python([path.join(newsRoot,'tests/firecrawl_strapi_driver.py'),sessionFile,'website']);
    assert.equal(report.actualWebsiteRenderers,true);assert.equal(report.positiveFilterChecks,9);assert.equal(report.negativeFilterChecks,3);
  });
  await check('Unpublish removes the automatic article from the public CMS snapshot', async () => {
    const result = await request(cm+'/'+document.documentId+'/actions/unpublish', { token: adminToken, method: 'POST', body: {} });
    assert.equal(result.status, 200, JSON.stringify(result.data));
    assert.equal((await request('/api/pito-news/snapshot', { token: session.readToken })).data.data.articles.length, 0);
  });
  await check('Disabling and editing a CMS source takes effect and an import preserves the change', async () => {
    const route = '/content-manager/collection-types/api::pito-news-source.pito-news-source/'+sourceDocument;
    assert.equal((await request(route, { token: adminToken, method: 'PUT', body: { active: false, name: 'BEWERKT DOOR REDACTEUR' } })).status, 200);
    await imported();
    const row = (await request('/api/pito-news/sources', { token: session.sourceToken })).data.data[0];
    assert.equal(row.active, false); assert.equal(row.name, 'BEWERKT DOOR REDACTEUR');
    const report = await driver(); assert.equal(report.firecrawlRequests, 0);
  });
  await check('All existing 205 sources import into real Strapi without duplicates on repetition', async () => {
    const report = await python([path.join(newsRoot, 'tests/firecrawl_strapi_driver.py'), sessionFile, 'catalog']);
    assert.equal(report.records, 205); assert.equal(report.created, 205); assert.equal(report.createdOnRepeat, 0);
    assert.equal((await request('/api/pito-news/sources', { token: session.sourceToken })).data.meta.total, 206);
  });
  const result = { testedAt: new Date().toISOString(), strapiVersion: require(path.join(modules, '@strapi/strapi/package.json')).version,
    actualStrapi: true, isolatedDatabase: testDatabase, firecrawl: 'controlled response fixture; no live API key',
    writer: 'controlled response fixture; no live API key', checks };
  fs.writeFileSync(path.join(appDir, 'report.json'), JSON.stringify(result, null, 2));
  fs.mkdirSync(path.join(newsRoot, 'reports'), { recursive: true });
  fs.writeFileSync(path.join(newsRoot, 'reports/firecrawl-strapi-e2e.json'), JSON.stringify(result, null, 2));
  console.log(`Real Strapi integration: ${checks.length} checks passed. Report: ${path.join(newsRoot, 'reports/firecrawl-strapi-e2e.json')}`);
}
main().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => {
  if (app) await app.destroy();
  if (testDatabase && maintenance) {
    const { Client } = require(path.join(modules, 'pg')); const client = new Client(maintenance);
    try { await client.connect(); await client.query(`DROP DATABASE IF EXISTS "${testDatabase}" WITH (FORCE)`); } finally { await client.end(); }
  }
  process.exit(process.exitCode || 0);
});
