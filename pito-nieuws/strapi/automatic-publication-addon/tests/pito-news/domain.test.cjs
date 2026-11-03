const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const ts = require('typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true } }).outputText, filename);
const domain = require('../../src/pito-news/domain.ts');
const { requireToken, receiveDraft, withNewsTransaction } = require('../../src/pito-news/index.ts');
const { newsAdminDefaults, installNewsAdminDefaults, initializeNewsAdminConfiguration } = require('../../src/pito-news/admin-config.ts');
const { installNewsAuditCompatibility } = require('../../src/pito-news/audit-compat.ts');
const NOW = new Date('2026-10-16T12:00:00.000Z');

function approved(changes = {}) {
  const article = {
    id: 17, documentId: 'stable-document', title: 'Testinhoud uitsluitend lokaal', slug: 'testinhoud-uitsluitend-lokaal',
    summary: 'Controle van de concept- en publicatieketen.', body: 'Dit is gelabelde testinhoud.\n\nAlleen voor een afzonderlijke testdatabase.',
    category: 'Bestuur', municipalities: [{ id: 4, slug: 'woerden' }], provinceWide: false,
    sourceBased: true, sourceUrl: 'https://www.woerden.nl/nieuws', sourceName: 'Gemeente Woerden', sourcePublishedAt: '2026-10-16T08:00:00.000Z',
    verifiedAt: '2026-10-16T11:00:00.000Z', rights: 'Eigen testtekst; geen beeld.', reviewNote: 'Getoetst aan de genoemde bron.',
    reviewStatus: 'approved', reviewer: 'Echte Testredacteur', reviewedByAdminId: 1, authorName: 'Testredactie', authorType: 'human', origin: 'manual',
    additionalSources: [], publishedAt: '2026-10-16T11:30:00.000Z', privateEvidence: { sourceText: 'PRIVE-BRONTEKST' }, evidenceReference: 'PRIVE-DOSSIER',
    ...changes,
  };
  article.reviewFingerprint = domain.reviewFingerprint(article);
  return article;
}

test('nieuw schema is apart, met Draft & Publish en gemeente-selectie', () => {
  const schema = require('../../src/api/pito-news-article/content-types/pito-news-article/schema.json');
  const municipality = require('../../src/components/pito-news/municipality.json');
  assert.equal(schema.info.displayName, 'PITO Nieuwsartikel');
  assert.equal(schema.options.draftAndPublish, true);
  assert.equal(schema.attributes.body.type, 'text');
  assert.equal(schema.attributes.municipalities.component, 'pito-news.municipality');
  assert.deepEqual([...domain.MUNICIPALITIES].sort(), [...municipality.attributes.slug.enum].sort());
  for (const field of ['externalKey', 'eventKey', 'evidenceReference', 'privateEvidence', 'reviewFingerprint', 'reviewedByAdminId']) assert.equal(schema.attributes[field].private, true);
});

test('handmatig artikel met echte controlegegevens voldoet zonder AI-bewijsformaat', () => {
  assert.deepEqual(domain.publicationErrors(approved(), NOW), []);
});

test('approved-flag en verzonnen reviewer leveren geen echte goedkeuring', () => {
  const article = approved({ reviewedByAdminId: null });
  assert.ok(domain.publicationErrors(article, NOW).some(error => error.includes('aangemelde redacteur')));
});

test('een inhoudswijziging maakt de bestaande goedkeuring ongeldig', () => {
  const article = approved();
  article.body = 'Een gewijzigde tekst zonder nieuwe controle.';
  assert.ok(domain.publicationErrors(article, NOW).some(error => error.includes('niet in deze versie beoordeeld')));
});

test('provincie Utrecht is alleen expliciet en onderbouwd provinciebreed', () => {
  assert.ok(domain.publicationErrors(approved({ municipalities: [] }), NOW).some(error => error.includes('minimaal')));
  assert.ok(domain.publicationErrors(approved({ municipalities: [], provinceWide: true }), NOW).some(error => error.includes('provinciebrede')));
  assert.deepEqual(domain.publicationErrors(approved({ municipalities: [], provinceWide: true, provinceWideReason: 'De provinciale regeling geldt voor alle 26 gemeenten.' }), NOW), []);
  assert.ok(domain.publicationErrors(approved({ municipalities: [{ slug: 'provincie-utrecht' }] }), NOW).some(error => error.includes('Onbekende')));
});

test('HTML, onbevestigde datums en onvolledige bronverwijzingen blokkeren publiceren', () => {
  for (const changes of [
    { body: '<script>alert(1)</script>' }, { verifiedAt: '2026-10-17T12:00:00Z' }, { sourceUrl: 'http://www.woerden.nl/nieuws' },
    { sourceUrl: 'https://127.0.0.1/a' }, { sourcePublishedAt: null }, { eventDate: '2026-10-15' },
    { additionalSources: [{ name: 'Onveilige bron', url: 'javascript:alert(1)' }] },
  ]) assert.ok(domain.publicationErrors(approved(changes), NOW).length, JSON.stringify(changes));
  assert.deepEqual(domain.publicationErrors(approved({ sourcePublishedAt: null, dateNote: 'De bron noemt geen publicatiedatum.' }), NOW), []);
});

test('onbekende beeldrechten exporteren geen foto of bibliotheeksleutel', () => {
  const article = approved({ image: { id: 9, url: '/uploads/test.jpg' }, imageKey: 'unreviewed-legacy-key', imageWebUsageApproved: false });
  const result = domain.publicArticle(article, { first_published_at: '2026-10-16T11:30:00Z', last_published_at: '2026-10-16T11:30:00Z' });
  assert.equal(result.image, null);
  assert.equal(result.imageKey, null);
  assert.equal(result.author, 'Testredactie');
  assert.equal(result.authorType, 'human');
  assert.equal(result.humanReviewed, true);
  assert.deepEqual(result.municipalities, ['woerden']);
});

test('vrijgegeven beeld vereist foto, alt-tekst, credit en rechtenonderbouwing', () => {
  assert.ok(domain.publicationErrors(approved({ imageWebUsageApproved: true }), NOW).some(error => error.includes('Vrijgegeven beeld')));
  const article = approved({ imageWebUsageApproved: true, image: { id: 9, url: '/uploads/test.jpg' }, imageAlt: 'Testfoto', imageCredit: 'Testfotograaf', imageRights: 'Schriftelijke toestemming voor publicatie.' });
  assert.deepEqual(domain.publicationErrors(article, NOW), []);
});

test('snapshot bevat geen bewijsdossiers, invoersleutels of interne reviewvelden', () => {
  const result = domain.publicArticle(approved({ externalKey: 'PRIVE-INVOER' }), { first_published_at: '2026-10-16T11:30:00Z', last_published_at: '2026-10-16T11:45:00Z' });
  const json = JSON.stringify(result);
  assert.ok(!json.includes('PRIVE-'));
  for (const field of ['privateEvidence', 'evidenceReference', 'externalKey', 'reviewFingerprint', 'reviewedByAdminId', 'reviewer', 'reviewNote', 'rights']) assert.ok(!(field in result), `${field} must remain internal`);
  assert.equal(result.updatedAt, '2026-10-16T11:45:00Z');
  assert.equal(result.firstPublishedAt, '2026-10-16T11:30:00Z');
});

test('snapshot kan geen draft of ongeldige publicatie maskeren als verwijdering', () => {
  assert.throws(() => domain.publicArticle(approved({ publishedAt: null }), {}));
  assert.throws(() => domain.publicArticle(approved({ reviewStatus: 'needs_review' }), {}));
  assert.throws(() => domain.publicArticle(approved(), {}));
});

test('conceptingang weigert publicatiestatus, auteurschap en vervalste goedkeuring vóór DB-toegang', async () => {
  for (const field of ['status', 'publishedAt', 'reviewStatus', 'reviewer', 'reviewFingerprint', 'verifiedAt', 'authorName', 'authorType']) {
    await assert.rejects(() => receiveDraft({}, { externalKey: 'test-1', [field]: 'approved' }), /mag deze velden niet instellen/);
  }
  await assert.rejects(() => receiveDraft({}, { title: 'Mist sleutel' }), /externalKey/);
});

test('lees- en concepttoken zijn niet uitwisselbaar; ontbrekende configuratie is expliciet', () => {
  const beforeRead = process.env.PITO_NEWS_READ_TOKEN;
  const beforeDraft = process.env.PITO_NEWS_DRAFT_TOKEN;
  try {
    process.env.PITO_NEWS_READ_TOKEN = 'read-' + 'a'.repeat(40);
    process.env.PITO_NEWS_DRAFT_TOKEN = 'draft-' + 'b'.repeat(40);
    const ctx = token => ({ get: () => `Bearer ${token}`, throw: (status, text) => { const error = new Error(text); error.status = status; throw error; } });
    requireToken(ctx(process.env.PITO_NEWS_READ_TOKEN), 'PITO_NEWS_READ_TOKEN');
    assert.throws(() => requireToken(ctx(process.env.PITO_NEWS_DRAFT_TOKEN), 'PITO_NEWS_READ_TOKEN'), error => error.status === 401);
    delete process.env.PITO_NEWS_READ_TOKEN;
    assert.throws(() => requireToken(ctx('anything'), 'PITO_NEWS_READ_TOKEN'), error => error.status === 503);
  } finally {
    if (beforeRead === undefined) delete process.env.PITO_NEWS_READ_TOKEN; else process.env.PITO_NEWS_READ_TOKEN = beforeRead;
    if (beforeDraft === undefined) delete process.env.PITO_NEWS_DRAFT_TOKEN; else process.env.PITO_NEWS_DRAFT_TOKEN = beforeDraft;
  }
});

test('native CMS-defaults geven Nederlandse selectievelden en houden servervelden onbewerkbaar', () => {
  const schema = require('../../src/api/pito-news-article/content-types/pito-news-article/schema.json');
  const config = newsAdminDefaults(schema);
  assert.equal(config.settings.mainField, 'title');
  assert.equal(config.metadatas.municipalities.edit.label, 'Gemeenten');
  assert.equal(config.metadatas.category.edit.label, 'Rubriek');
  for (const field of ['reviewer', 'firstPitoPublishedAt', 'lastPitoPublishedAt']) assert.equal(config.metadatas[field].edit.editable, false);
  for (const field of ['privateEvidence', 'reviewFingerprint', 'reviewedByAdminId']) {
    assert.equal(config.metadatas[field].edit.visible, false);
    assert.equal(config.attributes[field].hidden, true);
    assert.ok(!config.layouts.edit.flat().some(item => item.name === field));
  }
});

test('bootstrap behoudt een eerder door de beheerder ingestelde CMS-layout', async () => {
  let writes = 0;
  const service = { findContentType: () => ({ uid: domain.NEWS_UID }), findConfiguration: async () => ({ layouts: { edit: [[{ name: 'body', size: 12 }]] } }), updateConfiguration: async () => { writes++; } };
  await initializeNewsAdminConfiguration({ plugin: () => ({ service: () => service }) });
  assert.equal(writes, 0);
});

test('contenttype en beide componentdefaults voldoen aan de echte Strapi 5.50.2 configuratievalidator', async () => {
  const configurationSchema = require(path.join(path.dirname(require.resolve('@strapi/content-manager/package.json')), 'dist/server/controllers/validation/model-configuration.js'));
  const article = structuredClone(require('../../src/api/pito-news-article/content-types/pito-news-article/schema.json'));
  article.uid = domain.NEWS_UID;
  article.attributes.createdAt = { type: 'datetime' };
  article.attributes.updatedAt = { type: 'datetime' };
  const components = {
    'pito-news.municipality': structuredClone(require('../../src/components/pito-news/municipality.json')),
    'pito-news.source': structuredClone(require('../../src/components/pito-news/source.json')),
  };
  for (const [uid, component] of Object.entries(components)) { component.uid = uid; component.modelType = 'component'; component.attributes.id = { type: 'integer' }; }
  const original = global.strapi;
  const strapi = { components, contentType: () => article, getModel: uid => uid === article.uid ? article : components[uid] };
  global.strapi = strapi;
  try {
    installNewsAdminDefaults(strapi);
    for (const model of [article, ...Object.values(components)]) await configurationSchema(model, { allowUndefined: true }).validate(model.config);
  } finally { if (original === undefined) delete global.strapi; else global.strapi = original; }
});

test('Content Manager outer transactions raken niet geblokkeerd achter een procesqueue', { timeout: 1000 }, async () => {
  const trx = () => ({ where: () => ({ increment: async () => {} }) });
  let nestedCallbacks = 0;
  const strapi = { db: { inTransaction: () => true, getSchemaName: () => null, transaction: async callback => {
    if (callback) { nestedCallbacks++; return callback({ trx }); }
    return { get: () => trx };
  } } };
  let release;
  const secondDone = new Promise(resolve => { release = resolve; });
  const first = withNewsTransaction(strapi, async () => { await secondDone; return 'first'; });
  const second = withNewsTransaction(strapi, async () => { release(); return 'second'; });
  assert.deepEqual(await Promise.all([first, second]), ['first', 'second']);
  assert.equal(nestedCallbacks, 0, 'deferred audit callbacks must inherit the transaction owner context');
});

test('nieuwe snapshot- en schrijfacties in hetzelfde proces worden geserialiseerd', async () => {
  const trx = () => ({ where: () => ({ increment: async () => {} }) });
  const strapi = { db: { inTransaction: () => false, getSchemaName: () => null, transaction: async callback => callback({ trx }) } };
  const events = [];
  let release;
  const hold = new Promise(resolve => { release = resolve; });
  const first = withNewsTransaction(strapi, async () => { events.push('first-start'); await hold; events.push('first-end'); });
  const second = withNewsTransaction(strapi, async () => { events.push('second'); });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(events, ['first-start']);
  release();
  await Promise.all([first, second]);
  assert.deepEqual(events, ['first-start', 'first-end', 'second']);
});

test('deferred nieuws-audit verlaat de afgesloten transactiecontext met behoud van gebruiker en payload', async () => {
  const { AsyncLocalStorage } = require('node:async_hooks');
  const transactions = new AsyncLocalStorage();
  const calls = [];
  const service = {
    async logEvent(action, data, user) {
      await Promise.resolve();
      const transaction = transactions.getStore();
      if (transaction?.completed) throw new Error('Transaction query already complete');
      calls.push({ action, data, user, transaction, receiver: this });
      return { saved: true };
    },
  };
  installNewsAuditCompatibility({ plugin: () => ({ service: () => service }) });
  const wrapper = service.logEvent;
  installNewsAuditCompatibility({ plugin: () => ({ service: () => service }) });
  assert.equal(service.logEvent, wrapper, 'bootstrap must not wrap the service twice');
  const user = { id: 17, firstname: 'Werkelijke', lastname: 'Redacteur' };
  const data = { uid: domain.NEWS_UID, id: 'deleted-document', endpoint: '/content-manager/collection-types/news', data: { title: 'LOKALE TEST' } };
  const transaction = { completed: false };
  const result = await transactions.run(transaction, () => new Promise((resolve, reject) => {
    setTimeout(() => service.logEvent('entry.delete', data, user).then(resolve, reject), 0);
    transaction.completed = true;
  }));
  assert.deepEqual(result, { saved: true });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].transaction, undefined);
  assert.equal(calls[0].data, data);
  assert.equal(calls[0].user, user);
  assert.equal(calls[0].receiver, service);
  await transactions.run({ completed: false, marker: 'other-content' }, () => service.logEvent('entry.update', { uid: 'api::article.article' }, user));
  assert.equal(calls[1].transaction.marker, 'other-content', 'existing content types keep their original audit behavior');
});

const { automaticErrors, automaticRecord } = require('../../src/pito-news/automatic.ts');
const { receiveAutomaticPublication } = require('../../src/pito-news/index.ts');
function automaticSubmission() {
  const quote = 'De gemeente Woerden opent op maandag een nieuwe wandelroute langs de singel.';
  const data = { externalKey: 'test-automatic', title: 'Nieuwe wandelroute langs de singel',
    summary: 'In Woerden komt een nieuwe wandelroute langs de singel beschikbaar voor inwoners.',
    body: 'Wandelaars in Woerden kunnen binnenkort een route langs de singel volgen. De gemeente heeft de opening voor maandag aangekondigd.\n\nDe nieuwe route biedt inwoners een extra mogelijkheid om langs het water te wandelen.',
    category: 'Samenleving', municipalities: ['woerden'], provinceWide: false, sensitive: false,
    sourceUrl: 'https://www.woerden.nl/nieuws/wandelroute', sourceName: 'Gemeente Woerden',
    sourcePublishedAt: '2026-10-16T08:00:00Z', sourceBased: true, origin: 'writer',
    rights: 'Eigen nieuwsbericht op basis van gecontroleerde feiten. Geen bronfoto overgenomen.',
    evidenceReference: 'test:woerden', privateEvidence: { sourceUrl: 'https://www.woerden.nl/nieuws/wandelroute',
      sourceText: quote + ' Aanvullende broninformatie over de route en het gebruik door inwoners.'.repeat(8), fetchedAt: '2026-10-16T10:00:00Z' } };
  const verification = { sourceKey: 'woerden', checkedAt: '2026-10-16T11:00:00Z', note: 'Feiten, gemeente en bronpublicatiedatum gecontroleerd tegen de volledige brontekst.',
    facts: [{ statement: 'Woerden opent een nieuwe wandelroute.', quote }], municipalityEvidence: [{ slug: 'woerden', quote }] };
  const source = { sourceKey: 'woerden', active: true, discovery: 'rss', articleHosts: ['www.woerden.nl'], articlePathPrefix: '/nieuws/' };
  return { data, verification, source };
}
test('automatisch bronbewijs toetst actieve bron, periode, quotes en gemeente', () => {
  const { data, verification, source } = automaticSubmission();
  assert.deepEqual(automaticErrors(data, verification, [source], NOW), []);
  for (const change of [{ sourceUrl: 'https://other.example/nieuws/a' }, { sensitive: true }, { privateEvidence: {} },
    { sourcePublishedAt: '2026-09-01T08:00:00Z' }, { provinceWide: true }, { municipalities: ['utrecht'] }, { municipalities: 'woerden' }]) {
    assert.ok(automaticErrors({ ...data, ...change }, verification, [source], NOW).length);
  }
  assert.ok(automaticErrors(data, { ...verification, facts: [{ statement: 'Verzonnen feit zonder bronbewijs', quote: 'Dit staat helemaal niet in de bron.' }] }, [source], NOW).length);
  assert.ok(automaticErrors(data, verification, [{ ...source, active: false }], NOW).length);
  assert.ok(automaticErrors(data, verification, [{ ...source, discovery: 'manual' }], NOW).length);
});
test('automatische publicatie krijgt expliciet machinebewijs en geen menselijke beoordeling', () => {
  const { data, verification } = automaticSubmission();
  const article = approved({ ...data, municipalities: [{ slug: 'woerden' }], authorName: 'PITO Nieuwsredactie', authorType: 'automatic',
    reviewKind: 'automatic', reviewer: 'PITO automatische broncontrole', reviewedByAdminId: null,
    automaticReview: automaticRecord(data, verification, NOW) });
  assert.deepEqual(domain.publicationErrors(article, NOW), []);
  const result = domain.publicArticle(article, { first_published_at: NOW.toISOString(), last_published_at: NOW.toISOString() });
  assert.equal(result.humanReviewed, false);
  assert.equal(result.reviewKind, 'automatic');
  assert.ok(!('automaticReview' in result));
  article.privateEvidence.sourceText += ' Gewijzigd bewijs.';
  assert.ok(domain.publicationErrors(article, NOW).length);
});
test('automatische ingang is standaard uit en sluit na het tijdvenster', async () => {
  const previous = process.env.PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL;
  try {
    for (const value of ['', 'invalid', '2020-01-01T00:00:00Z']) {
      process.env.PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL = value;
      await assert.rejects(() => receiveAutomaticPublication({}, {}, {}), /niet actief|verstreken/);
    }
  } finally {
    if (previous === undefined) delete process.env.PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL; else process.env.PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL = previous;
  }
});

test('doorlopende publicatie vereist expliciete inschakeling; verlopen venster opent niet vanzelf', () => {
  const { automaticPublicationEnabled } = require('../../src/pito-news/automatic.ts');
  const expired={PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL:'2020-01-01T00:00:00Z'};
  assert.equal(automaticPublicationEnabled({}),false);
  assert.equal(automaticPublicationEnabled(expired),false);
  assert.equal(automaticPublicationEnabled({...expired,PITO_NEWS_AUTOMATIC_PUBLISH_ENABLED:'1'}),true);
  assert.equal(automaticPublicationEnabled({...expired,PITO_NEWS_AUTOMATIC_PUBLISH_ENABLED:'0'}),false);
  assert.equal(automaticPublicationEnabled({PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL:'2099-01-01T00:00:00Z'}),true);
});
