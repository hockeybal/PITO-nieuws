#!/usr/bin/env node
'use strict';
// Install only the tested additive source model/endpoints. Keep a private DB
// dump and file backup before a real application's schema can be updated.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawnSync } = require('node:child_process');
const newsRoot = path.resolve(__dirname, '..');
const root = path.resolve(process.argv[2] || '/Users/michelvannoort/sites/website/pito/strapi');
const apply = process.argv.includes('--apply');
const addon = path.join(newsRoot, 'strapi/source-addon');
const dotenv = require(path.join(root, 'node_modules/dotenv'));
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? files(path.join(dir, e.name)) : [path.join(dir, e.name)]);
}
function main() {
  const version = require(path.join(root, 'package.json')).dependencies['@strapi/strapi'];
  if (version !== '5.50.2') throw new Error('This addon was verified against the existing Strapi 5.50.2 project.');
  if (!fs.existsSync(path.join(root, 'src/pito-news/index.ts'))) throw new Error('The existing PITO news endpoints are required.');
  const envPath = path.join(root, '.env');
  const configured = dotenv.parse(fs.readFileSync(envPath));
  const workerPath = path.join(newsRoot, '.env.pipeline.local');
  const workerConfig = dotenv.parse(fs.readFileSync(workerPath));
  const entries = files(path.join(addon, 'src'));
  if (!apply) { console.log(JSON.stringify({ strapiProject: root, files: entries.map(p => path.relative(addon, p)), databaseBackupRequired: true, applied: false })); return; }
  if (configured.DATABASE_URL || configured.DATABASE_CLIENT !== 'postgres' || !['localhost', '127.0.0.1', '::1'].includes(configured.DATABASE_HOST || 'localhost')) throw new Error('Only the existing explicit local PostgreSQL configuration is allowed.');
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backup = path.join(root, '.pito-news-backups', stamp);
  fs.mkdirSync(backup, { recursive: true, mode: 0o700 });
  const dump = path.join(backup, 'before-source-addon.dump');
  const result = spawnSync('/opt/homebrew/bin/pg_dump', ['--format=custom', '--host', configured.DATABASE_HOST || 'localhost',
    '--port', configured.DATABASE_PORT || '5432', '--username', configured.DATABASE_USERNAME || 'strapi',
    '--file', dump, configured.DATABASE_NAME || 'strapi'], {
      env: { ...process.env, PGPASSWORD: configured.DATABASE_PASSWORD || '' }, encoding: 'utf8', timeout: 120000
    });
  if (result.status !== 0) throw new Error('Database backup failed; no source code or settings changed.');
  fs.chmodSync(dump, 0o600);
  fs.copyFileSync(envPath, path.join(backup, '.env')); fs.chmodSync(path.join(backup, '.env'), 0o600);
  fs.copyFileSync(workerPath, path.join(backup, '.env.pipeline.local')); fs.chmodSync(path.join(backup, '.env.pipeline.local'), 0o600);
  const ignorePath = path.join(root, '.gitignore');
  fs.copyFileSync(ignorePath, path.join(backup, '.gitignore'));
  const serverAdds = [], workerAdds = [];
  const keys = ['PITO_NEWS_READ_TOKEN', 'PITO_NEWS_DRAFT_TOKEN', 'PITO_NEWS_SOURCE_TOKEN', 'PITO_NEWS_SOURCE_IMPORT_TOKEN'];
  for (const key of keys) {
    const value = configured[key] || workerConfig[key] || crypto.randomBytes(32).toString('hex');
    if (value.length < 32 || /\s/.test(value)) throw new Error('An existing integration token is invalid; it was not replaced.');
    if (configured[key] && workerConfig[key] && configured[key] !== workerConfig[key]) throw new Error('Existing integration tokens disagree; they were not replaced.');
    if (!configured[key]) serverAdds.push(key+'='+value);
    if (!workerConfig[key]) workerAdds.push(key+'='+value);
  }
  if (!workerConfig.PITO_STRAPI_URL) workerAdds.push('PITO_STRAPI_URL=http://127.0.0.1:1337');
  if (!workerConfig.PITO_LOCAL_TEST) workerAdds.push('PITO_LOCAL_TEST=1');
  for (const source of entries) {
    const relative = path.relative(addon, source), destination = path.join(root, relative);
    if (fs.existsSync(destination)) {
      const copy = path.join(backup, relative); fs.mkdirSync(path.dirname(copy), { recursive: true }); fs.copyFileSync(destination, copy);
    }
    fs.mkdirSync(path.dirname(destination), { recursive: true }); fs.copyFileSync(source, destination);
  }
  if (serverAdds.length) fs.appendFileSync(envPath, '\n# PITO news integrations; server-side only\n'+serverAdds.join('\n')+'\n');
  if (workerAdds.length) fs.appendFileSync(workerPath, '\n# Local Strapi connection; server-side only\n'+workerAdds.join('\n')+'\n');
  fs.chmodSync(envPath, 0o600); fs.chmodSync(workerPath, 0o600);
  if (!fs.readFileSync(ignorePath, 'utf8').split('\n').includes('.pito-news-backups/')) fs.appendFileSync(ignorePath, '\n# Private PITO integration recovery files\n.pito-news-backups/\n');
  const report = { installedAt: new Date().toISOString(), strapiProject: root, files: entries.map(p => path.relative(addon, p)),
    backupDirectory: backup, databaseBackupBytes: fs.statSync(dump).size, applied: true,
    databaseRestarted: false, importedSources: false, externalPublication: false };
  fs.writeFileSync(path.join(newsRoot, 'reports/firecrawl-install.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
}
try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
