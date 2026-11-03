import { AsyncLocalStorage } from 'node:async_hooks';
import { automaticErrors, automaticRecord, automaticPublicationEnabled } from './automatic';
import { sourceSnapshot } from '../pito-news-sources';
import { timingSafeEqual } from 'node:crypto';
import { errors } from '@strapi/utils';
import { NEWS_UID, POPULATE, digest, evidenceDigest, publicArticle, publicationErrors, reviewFingerprint, slugify } from './domain';
import { installNewsAdminDefaults, initializeNewsAdminConfiguration } from './admin-config';
import { installNewsAuditCompatibility } from './audit-compat';
import { REVIEWER, reviewerConfigured, validateReviewerConfiguration, reviewerArticle, reviewerVersion,
  reviewQueueParameters, validateReviewDecision, matchingReviewSources, ReviewConflictError } from './reviewer';

const { ValidationError, ForbiddenError } = errors;
const TABLES = { state: 'pito_news_state', ledger: 'pito_news_ledger', slugs: 'pito_news_slugs', audit: 'pito_news_audit', ingress: 'pito_news_ingress' };
const scope = new AsyncLocalStorage<any>();
const queues = new WeakMap<object, Promise<any>>();
const mutations = new Set(['create', 'update', 'publish', 'unpublish', 'delete', 'discardDraft', 'clone']);
const protectedFields = ['reviewer', 'reviewFingerprint', 'reviewedByAdminId', 'firstPitoPublishedAt', 'lastPitoPublishedAt', 'firstPublishedAt', 'publishedAt', 'reviewKind', 'automaticReview'];

function table(strapi: any, trx: any, name: string) {
  const query = trx(name);
  const schema = strapi.db.getSchemaName();
  return schema ? query.withSchema(schema) : query;
}

// The persistent lock serializes *all* CMS mutations and snapshot reads across
// processes. The same transaction covers the Strapi rows and the durable ledger.
export async function withNewsTransaction(strapi: any, fn: (trx: any) => Promise<any>) {
  if (scope.getStore()?.trx) return fn(scope.getStore().trx);
  const locked = async (trx: any) => {
    await table(strapi, trx, TABLES.state).where({ id: 'lock' }).increment('revision', 1);
    return scope.run({ trx }, () => fn(trx));
  };
  // Content Manager wraps some sequential/bulk actions in its own transaction.
  // Queueing those behind an unrelated request could make that request wait for
  // our outer transaction while our next action waits for the queue: a deadlock.
  if (strapi.db.inTransaction()) {
    // The no-callback form returns the existing handle without creating another
    // Strapi ALS store. Its owner commits it. A nested callback would leave
    // deferred audit-plugin timers holding a stale, already-completed handle.
    const existing = await strapi.db.transaction();
    return locked(existing.get());
  }
  const run = () => strapi.db.transaction(({ trx }) => locked(trx));
  const previous = queues.get(strapi) || Promise.resolve();
  const result = previous.catch(() => {}).then(run);
  queues.set(strapi, result.catch(() => {}));
  return result;
}

async function editor(strapi: any) {
  const ctx = strapi.requestContext.get();
  if (ctx?.state?.auth?.strategy?.name !== 'admin' || !ctx?.state?.user?.id) return null;
  const user = await strapi.db.query('admin::user').findOne({ where: { id: ctx.state.user.id, isActive: true } });
  if (!user) return null;
  const name = [user.firstname, user.lastname].filter(Boolean).join(' ').trim() || user.username || user.email;
  return name ? { id: user.id, name } : null;
}

async function audit(strapi: any, trx: any, documentId: string, action: string, actor: any, detail: any = {}) {
  await table(strapi, trx, TABLES.audit).insert({ document_id: documentId, action, actor: actor ? String(actor.id) : 'draft-ingress', at: new Date().toISOString(), detail: JSON.stringify(detail) });
}

async function getDraft(strapi: any, documentId: string) {
  return strapi.documents(NEWS_UID).findOne({ documentId, status: 'draft', populate: POPULATE });
}

async function ensureSlug(strapi: any, trx: any, documentId: string, slug: string) {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug || '')) throw new ValidationError('Gebruik een geldige slug met kleine letters, cijfers en streepjes.');
  const reserved = await table(strapi, trx, TABLES.slugs).where({ slug }).first();
  if (reserved && reserved.document_id !== documentId) throw new ValidationError('Deze slug is al in gebruik of gereserveerd voor een bestaande redirect.');
  const other = await strapi.db.query(NEWS_UID).findOne({ where: { slug, documentId: { $ne: documentId } } });
  if (other) throw new ValidationError('Deze slug hoort bij een ander nieuwsartikel.');
}

async function saveReview(strapi: any, draft: any, approvalRequested: boolean, actor: any, previous: any) {
  if (!draft) return draft;
  const data: any = {};
  if (!draft.authorName && actor) {
    const selectedAuthor = draft.author && ([draft.author.first_name, draft.author.last_name].filter(Boolean).join(' ').trim() || draft.author.username);
    data.authorName = selectedAuthor || actor.name;
  }
  Object.assign(draft, data);
  const changedApprovedVersion = previous?.reviewStatus === 'approved' && previous.reviewFingerprint !== reviewFingerprint(draft);
  if (changedApprovedVersion && draft.reviewStatus === 'approved') {
    // Content Manager sends the current selector value on Save. Merely retaining
    // "approved" while editing must not silently approve a correction.
    data.reviewStatus = 'needs_review';
    data.reviewer = null;
    data.reviewedByAdminId = null;
    data.reviewFingerprint = null;
  } else if (approvalRequested) {
    if (!actor) throw new ForbiddenError('Alleen een werkelijk aangemelde redacteur kan een artikel goedkeuren.');
    if (typeof draft.reviewNote !== 'string' || !draft.reviewNote.trim()) throw new ValidationError('Vul de Beoordelings- of correctienotitie in voordat je het artikel goedkeurt. Sla daarna op en kies Publish.');
    data.reviewStatus = 'approved';
    data.reviewKind = 'human';
    data.automaticReview = null;
    // Selecting approved is the editor's explicit review action. Its actual
    // timestamp comes from the server, avoiding an empty/future date picker.
    data.verifiedAt = new Date().toISOString();
    data.reviewer = actor.name;
    data.reviewedByAdminId = actor.id;
    data.reviewFingerprint = reviewFingerprint({ ...draft, ...data });
  } else if (draft.reviewStatus === 'approved' && (!previous || previous.reviewFingerprint !== reviewFingerprint(draft))) {
    data.reviewStatus = 'needs_review';
    data.reviewer = null;
    data.reviewedByAdminId = null;
    data.reviewFingerprint = null;
  }
  if (Object.keys(data).length) await strapi.db.query(NEWS_UID).update({ where: { id: draft.id }, data });
  return { ...draft, ...data };
}

async function publishDocument(strapi: any, trx: any, context: any, next: any, actor: any) {
  const documentId = context.params.documentId;
  const draft = await getDraft(strapi, documentId);
  if (!draft) throw new ValidationError('Nieuwsconcept niet gevonden.');
  const validation = publicationErrors(draft);
  if (validation.length) throw new ValidationError(`Publicatie geblokkeerd: ${validation.join('; ')}. Vul bij handmatige beoordeling de Beoordelings- of correctienotitie in, kies approved bij Redactionele beoordeling en klik Save. Klik daarna op Publish.`);
  await ensureSlug(strapi, trx, documentId, draft.slug);
  const existing = await table(strapi, trx, TABLES.ledger).where({ document_id: documentId }).first();
  const now = new Date().toISOString();
  const first = existing?.first_published_at || now;
  // Always derive timestamps server-side. This survives unpublish and deletion.
  await strapi.db.query(NEWS_UID).update({ where: { id: draft.id }, data: { firstPitoPublishedAt: first, lastPitoPublishedAt: now } });
  const result = await next();
  const values = { first_published_at: first, last_published_at: now, current_slug: draft.slug, deleted: false };
  if (existing) await table(strapi, trx, TABLES.ledger).where({ document_id: documentId }).update(values);
  else await table(strapi, trx, TABLES.ledger).insert({ document_id: documentId, ...values });
  if (!await table(strapi, trx, TABLES.slugs).where({ slug: draft.slug }).first()) await table(strapi, trx, TABLES.slugs).insert({ slug: draft.slug, document_id: documentId });
  await audit(strapi, trx, documentId, 'publish', actor, { slug: draft.slug, previousSlug: existing?.current_slug || null, firstPublishedAt: first, reviewFingerprint: draft.reviewFingerprint });
  return result;
}

export function registerPitoNews({ strapi }: any) {
  installNewsAdminDefaults(strapi);
  strapi.documents.use(async (context: any, next: any) => {
    if (context.uid !== NEWS_UID || !mutations.has(context.action)) return next();
    return withNewsTransaction(strapi, async trx => {
      const ingress = scope.getStore()?.ingress === true;
      const automatic = context.action === 'publish' && scope.getStore()?.automaticDocumentId === context.params.documentId;
      const actor = automatic ? (scope.getStore()?.automaticActor || { id: 'automatic-publisher', name: 'PITO automatische broncontrole' }) : ingress ? null : await editor(strapi);
      if (!ingress && !actor) throw new ForbiddenError('PITO-nieuws wijzigen vereist een aangemelde CMS-redacteur. Gebruik voor aanvoer uitsluitend de conceptingang.');
      if (ingress && (context.action !== 'create' || context.params.status === 'published')) throw new ForbiddenError('Conceptaanvoer mag nooit publiceren of bestaande CMS-inhoud wijzigen.');
      if (context.action === 'clone') throw new ValidationError('Maak een nieuw nieuwsconcept; het kopiëren van invoer- en bewijsidentiteiten is niet toegestaan.');
      if (context.action === 'publish') return publishDocument(strapi, trx, context, next, actor);
      if (context.action === 'create' || context.action === 'update') {
        const data = context.params.data || {};
        if (context.params.status === 'published') throw new ValidationError('Sla eerst het concept op en beoordeel het; publiceer daarna via de publicatieactie.');
        const approvalRequested = data.reviewStatus === 'approved';
        for (const key of protectedFields) delete data[key];
        const previous = context.params.documentId ? await getDraft(strapi, context.params.documentId) : null;
        if (previous) {
          // Identity, evidence and the original publication date never come from a client edit.
          data.externalKey = previous.externalKey;
          data.eventKey = previous.eventKey;
          data.firstPitoPublishedAt = previous.firstPitoPublishedAt;
          data.lastPitoPublishedAt = previous.lastPitoPublishedAt;
          if (!data.slug) data.slug = previous.slug;
        } else {
          data.slug = data.slug || slugify(data.title);
          data.reviewStatus = approvalRequested ? 'approved' : 'needs_review';
        }
        if (ingress) {
          data.reviewStatus = 'needs_review';
          data.authorType = 'automatic';
          data.authorName = 'PITO automatische conceptaanvoer';
        }
        if (previous) await ensureSlug(strapi, trx, previous.documentId, data.slug);
        context.params.data = data;
        context.params.status = 'draft';
        const result = await next();
        const documentId = result?.documentId;
        if (!documentId) throw new ValidationError('Concept kon niet worden opgeslagen.');
        const draft = await getDraft(strapi, documentId);
        await ensureSlug(strapi, trx, documentId, draft.slug);
        const reviewed = await saveReview(strapi, draft, !ingress && approvalRequested, actor, previous);
        await audit(strapi, trx, documentId, ingress ? 'ingress.create' : 'draft.save', actor, { fingerprint: reviewFingerprint(reviewed), evidenceReference: reviewed.evidenceReference || null });
        // Keep the original selection/populate contract for Content Manager.
        return { ...result, reviewStatus: reviewed.reviewStatus, reviewer: reviewed.reviewer, authorName: reviewed.authorName };
      }
      const result = await next();
      if (context.action === 'delete') await table(strapi, trx, TABLES.ledger).where({ document_id: context.params.documentId }).update({ deleted: true });
      await audit(strapi, trx, context.params.documentId, context.action, actor);
      return result;
    });
  });
}

export async function bootstrapPitoNews({ strapi }: any) {
  const schemaName = strapi.db.getSchemaName();
  const schema = () => schemaName ? strapi.db.connection.schema.withSchema(schemaName) : strapi.db.connection.schema;
  if (!await schema().hasTable(TABLES.state)) await schema().createTable(TABLES.state, t => { t.string('id').primary(); t.integer('revision').notNullable().defaultTo(0); });
  if (!await schema().hasTable(TABLES.ledger)) await schema().createTable(TABLES.ledger, t => { t.string('document_id').primary(); t.text('first_published_at'); t.text('last_published_at'); t.string('current_slug'); t.boolean('deleted').defaultTo(false); });
  if (!await schema().hasTable(TABLES.slugs)) await schema().createTable(TABLES.slugs, t => { t.string('slug').primary(); t.string('document_id').notNullable().index(); });
  if (!await schema().hasTable(TABLES.audit)) await schema().createTable(TABLES.audit, t => { t.increments('id').primary(); t.string('document_id').notNullable().index(); t.string('action').notNullable(); t.string('actor').notNullable(); t.text('at').notNullable(); t.text('detail').notNullable(); });
  if (!await schema().hasTable(TABLES.ingress)) await schema().createTable(TABLES.ingress, t => { t.string('external_key').primary(); t.string('event_key').index(); t.string('document_id').notNullable().index(); t.string('payload_hash').notNullable(); t.text('received_at').notNullable(); });
  await strapi.db.getConnection(TABLES.state).insert({ id: 'lock', revision: 0 }).onConflict('id').ignore();
  const persisted = await strapi.store.get({ type: 'core', key: 'persisted_tables' }) || [];
  const names = new Set(persisted.map(value => typeof value === 'string' ? value : value.name));
  await strapi.store.set({ type: 'core', key: 'persisted_tables', value: [...persisted, ...Object.values(TABLES).filter(name => !names.has(name))] });
  const read = process.env.PITO_NEWS_READ_TOKEN;
  const draft = process.env.PITO_NEWS_DRAFT_TOKEN;
  if (read && draft && read === draft) throw new Error('PITO News lees- en concepttokens moeten verschillend zijn.');
  validateReviewerConfiguration(process.env);
  await initializeNewsAdminConfiguration(strapi);
  installNewsAuditCompatibility(strapi);
  strapi.log.info('PITO Nieuws: conceptaanvoer en expliciet begrensde automatische publicatie beschikbaar.');
}

export function requireToken(ctx: any, variable: string) {
  const expected = process.env[variable];
  const received = ctx.get('authorization') || '';
  if (!expected || expected.length < 32) return ctx.throw(503, 'Deze PITO-koppeling is nog niet geconfigureerd.');
  const wanted = Buffer.from(`Bearer ${expected}`);
  const actual = Buffer.from(received);
  if (actual.length !== wanted.length || !timingSafeEqual(actual, wanted)) return ctx.throw(401, 'Ongeldige koppelingstoegang.');
}

export async function newsSnapshot(strapi: any) {
  return withNewsTransaction(strapi, async trx => {
    const records = await strapi.documents(NEWS_UID).findMany({ status: 'published', sort: ['documentId:asc'], populate: POPULATE, limit: -1 });
    const ledgers = await table(strapi, trx, TABLES.ledger).select('*');
    const byDocument = new Map<string, any>(ledgers.map(row => [row.document_id, row]));
    // Invalid publications fail the complete snapshot rather than looking like removals.
    const articles = records.map(record => publicArticle(record, byDocument.get(record.documentId)));
    const publicIds = new Set(articles.map(article => article.documentId));
    const aliases = await table(strapi, trx, TABLES.slugs).orderBy('slug').select('*');
    const redirects = aliases.filter(row => publicIds.has(row.document_id) && byDocument.get(row.document_id).current_slug !== row.slug)
      .map(row => ({ from: row.slug, to: byDocument.get(row.document_id).current_slug, documentId: row.document_id }));
    const data = { articles, redirects };
    return { data, meta: { schemaVersion: 1, revision: digest(data), generatedAt: new Date().toISOString(), complete: true, total: articles.length, articleCount: articles.length, redirectCount: redirects.length } };
  });
}

const ingressFields = new Set(['externalKey', 'eventKey', 'title', 'slug', 'summary', 'body', 'category', 'municipalities', 'provinceWide', 'provinceWideReason', 'sourceBased', 'sourceUrl', 'sourceName', 'sourcePublishedAt', 'eventDate', 'dateNote', 'rights', 'sensitive', 'additionalSources', 'impact', 'ranking', 'imageKey', 'imageTopics', 'evidenceReference', 'privateEvidence', 'origin']);

function ingressData(input: any) {
  const data = { ...input, origin: input.origin || 'rss' };
  if (Array.isArray(data.municipalities)) data.municipalities = data.municipalities.map(value => typeof value === 'string' ? { slug: value } : { slug: value?.slug });
  if (Array.isArray(data.additionalSources)) data.additionalSources = data.additionalSources.map(value => ({ name: value?.name, url: value?.url }));
  return data;
}

export async function receiveDraft(strapi: any, input: any) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new ValidationError('data moet een conceptobject zijn.');
  const unsupported = Object.keys(input).filter(key => !ingressFields.has(key));
  if (unsupported.length) throw new ValidationError(`Conceptaanvoer mag deze velden niet instellen: ${unsupported.join(', ')}.`);
  if (typeof input.externalKey !== 'string' || !input.externalKey.trim() || input.externalKey.length > 240) throw new ValidationError('externalKey is verplicht (maximaal 240 tekens).');
  if (input.eventKey && (typeof input.eventKey !== 'string' || input.eventKey.length > 240)) throw new ValidationError('eventKey is ongeldig.');
  if (JSON.stringify(input).length > 2_000_000) throw new ValidationError('Concept en privédossier zijn te groot.');
  if (input.origin && !['rss', 'writer', 'import'].includes(input.origin)) throw new ValidationError('Conceptaanvoer vereist herkomst rss, writer of import.');
  const data = ingressData(input);
  return withNewsTransaction(strapi, async trx => {
    const lookup = table(strapi, trx, TABLES.ingress).where({ external_key: input.externalKey });
    if (input.eventKey) lookup.orWhere({ event_key: input.eventKey });
    const existing = await lookup.first();
    const hash = digest(data);
    if (existing) {
      const found = await getDraft(strapi, existing.document_id);
      if (existing.payload_hash !== hash) await audit(strapi, trx, existing.document_id, 'ingress.proposal', null, { externalKey: input.externalKey, payload: data });
      // Persist aliases as well, so replays with a second feed's key stay idempotent.
      if (!await table(strapi, trx, TABLES.ingress).where({ external_key: input.externalKey }).first()) await table(strapi, trx, TABLES.ingress).insert({ external_key: input.externalKey, event_key: input.eventKey || null, document_id: existing.document_id, payload_hash: hash, received_at: new Date().toISOString() });
      return { data: { documentId: existing.document_id, created: false, status: 'draft', reason: found ? 'existing_document_preserved' : 'deleted_document_not_recreated' } };
    }
    const result = await scope.run({ ...scope.getStore(), ingress: true }, () => strapi.documents(NEWS_UID).create({ data: structuredClone(data), status: 'draft' }));
    await table(strapi, trx, TABLES.ingress).insert({ external_key: input.externalKey, event_key: input.eventKey || null, document_id: result.documentId, payload_hash: hash, received_at: new Date().toISOString() });
    await audit(strapi, trx, result.documentId, 'ingress.evidence', null, { payload: data });
    return { data: { documentId: result.documentId, created: true, status: 'draft' } };
  });
}


// New submissions and identical untouched bot concepts may be published.
// Human saves, withdrawals, deleted documents and changed proposals are preserved.
export async function receiveAutomaticPublication(strapi: any, input: any, verification: any) {
  if (reviewerConfigured(process.env)) throw new ForbiddenError('Publiceren verloopt via de afzonderlijke controlebot. Bewaar dit artikel via de conceptingang; de schrijversleutel kan niet meer publiceren.');
  if (!automaticPublicationEnabled(process.env)) throw new ForbiddenError('Automatische publicatie is niet actief of het toegestane tijdvenster is verstreken.');
  const sources = await sourceSnapshot(strapi);
  const problems = automaticErrors(input, verification, sources.data);
  if (problems.length) throw new ValidationError(`Automatische publicatie geblokkeerd: ${problems.join('; ')}. Bewaar dit artikel via de conceptingang.`);
  return withNewsTransaction(strapi, async trx => {
    const result = await receiveDraft(strapi, input);
    const documentId = result.data.documentId;
    if (!result.data.created) {
      const published = await strapi.documents(NEWS_UID).findOne({ documentId, status: 'published', populate: POPULATE });
      if (published) return { data: { ...result.data, status: 'published', slug: published.slug } };
      const draft = await getDraft(strapi, documentId);
      const evidence = await table(strapi, trx, TABLES.audit).where({ document_id: documentId, action: 'ingress.evidence' }).first();
      let original;
      try { original = JSON.parse(evidence?.detail || 'null')?.payload; } catch { original = null; }
      const everPublished = await table(strapi, trx, TABLES.ledger).where({ document_id: documentId }).first();
      const humanSave = await table(strapi, trx, TABLES.audit).where({ document_id: documentId, action: 'draft.save' }).first();
      const proposed = ingressData(input);
      const originalInput = original && Object.fromEntries(Object.keys(proposed).map(key => [key, original[key]]));
      const untouched = draft && !everPublished && !humanSave && draft.externalKey === input.externalKey &&
        draft.origin === 'writer' && draft.authorType === 'automatic' && draft.reviewStatus === 'needs_review' &&
        !draft.reviewedByAdminId && !draft.reviewer && originalInput && evidenceDigest(originalInput) === evidenceDigest(proposed);
      if (!untouched) return { data: { ...result.data, status: 'draft', slug: null } };
    }
    const record = automaticRecord(input, verification);
    await strapi.db.query(NEWS_UID).update({ where: { documentId, publishedAt: null }, data: {
      authorType: 'automatic', authorName: 'PITO Nieuwsredactie', reviewKind: 'automatic',
      automaticReview: record, reviewStatus: 'approved', reviewer: 'PITO automatische broncontrole',
      reviewedByAdminId: null, verifiedAt: verification.checkedAt, reviewNote: verification.note,
    } });
    const draft = await getDraft(strapi, documentId);
    await strapi.db.query(NEWS_UID).update({ where: { id: draft.id }, data: { reviewFingerprint: reviewFingerprint(draft) } });
    await audit(strapi, trx, documentId, 'automatic.review', { id: 'automatic-publisher' }, { policy: record.policy, sourceKey: record.sourceKey, evidenceHash: record.evidenceHash });
    await scope.run({ ...scope.getStore(), automaticDocumentId: documentId }, () => strapi.documents(NEWS_UID).publish({ documentId }));
    return { data: { documentId, created: result.data.created, newlyPublished: true, status: 'published', slug: draft.slug, humanReviewed: false } };
  });
}

function auditDetail(row: any) {
  try { return JSON.parse(row?.detail || 'null'); } catch { return null; }
}

async function reviewerEligibility(strapi: any, trx: any, draft: any) {
  const reasons: string[] = [];
  if (draft.origin !== 'writer' || draft.authorType !== 'automatic' || !draft.externalKey) reasons.push('Geen oorspronkelijk automatisch schrijversconcept.');
  if (draft.reviewStatus !== 'needs_review' || draft.reviewedByAdminId || draft.reviewer) reasons.push('Dit concept heeft al een redactionele beoordeling.');
  if (await table(strapi, trx, TABLES.ledger).where({ document_id: draft.documentId }).first()) reasons.push('Dit artikel is eerder gepubliceerd of ingetrokken.');
  if (await table(strapi, trx, TABLES.audit).where({ document_id: draft.documentId, action: 'draft.save' }).first()) reasons.push('Een redacteur heeft dit concept opgeslagen; menselijke wijzigingen blijven beschermd.');
  const ingress = await table(strapi, trx, TABLES.ingress).where({ document_id: draft.documentId, external_key: draft.externalKey }).first();
  const original = auditDetail(await table(strapi, trx, TABLES.audit).where({ document_id: draft.documentId, action: 'ingress.evidence' }).orderBy('id', 'asc').first())?.payload;
  if (!ingress || !original) reasons.push('Oorspronkelijk aanvoerdossier ontbreekt.');
  else {
    // Check the saved content against its own original ingress, ignoring CMS
    // component IDs/defaults and equivalent datetime serialization only.
    const saved = reviewerArticle(draft);
    const normalizedOriginal = ingressData(original);
    const keys = Object.keys(normalizedOriginal).filter(key => ingressFields.has(key));
    const comparable = (row: any) => Object.fromEntries(keys.map(key => [key,
      key === 'sourcePublishedAt' && row[key] ? new Date(row[key]).toISOString() : row[key] ?? null]));
    if (evidenceDigest(comparable(saved)) !== evidenceDigest(comparable(normalizedOriginal))) reasons.push('De opgeslagen inhoud wijkt af van het oorspronkelijke schrijversconcept.');
  }
  return reasons;
}

export async function newsReviewQueue(strapi: any, query: any) {
  const { cursor, limit } = reviewQueueParameters(query);
  return withNewsTransaction(strapi, async trx => {
    const ledger = await table(strapi, trx, TABLES.ledger).select('document_id');
    const excluded = ledger.map(row => row.document_id);
    const documentFilter = { ...(cursor ? { $gt: cursor } : {}), ...(excluded.length ? { $notIn: excluded } : {}) };
    const rows = await strapi.documents(NEWS_UID).findMany({ status: 'draft', populate: POPULATE,
      filters: { reviewStatus: 'needs_review', ...(Object.keys(documentFilter).length ? { documentId: documentFilter } : {}) },
      sort: ['documentId:asc'], limit: limit + 1 });
    const sources = await sourceSnapshot(strapi);
    const data = [];
    for (const draft of rows.slice(0, limit)) {
      const version = reviewerVersion(draft);
      const reasons = await reviewerEligibility(strapi, trx, draft);
      const previous = auditDetail(await table(strapi, trx, TABLES.audit).where({ document_id: draft.documentId, action: 'reviewer.hold' }).orderBy('id', 'desc').first());
      const lastReview = previous ? { decision: 'hold', version: previous.version, note: previous.note, checkedAt: previous.checkedAt } : null;
      data.push({ documentId: draft.documentId, version, article: reviewerArticle(draft), eligible: reasons.length === 0,
        reasons, sources: matchingReviewSources(draft, sources.data), lastReview, alreadyChecked: lastReview?.version === version });
    }
    return { data, meta: { schemaVersion: 1, nextCursor: rows.length > limit ? data[data.length - 1].documentId : null,
      complete: rows.length <= limit, generatedAt: new Date().toISOString() } };
  });
}

export async function receiveReviewDecision(strapi: any, input: any) {
  validateReviewDecision(input);
  const requestHash = evidenceDigest(input);
  return withNewsTransaction(strapi, async trx => {
    const documentId = input.documentId;
    const published = await strapi.documents(NEWS_UID).findOne({ documentId, status: 'published', populate: POPULATE });
    if (published) {
      if (input.decision === 'publish' && published.automaticReview?.reviewedVersion === input.version && published.automaticReview?.requestHash === requestHash) {
        return { data: { documentId, status: 'published', decision: 'publish', newlyPublished: false, slug: published.slug, humanReviewed: false } };
      }
      throw new ReviewConflictError('Dit artikel is al gepubliceerd; deze controle mag de publicatie niet wijzigen.');
    }
    const draft = await getDraft(strapi, documentId);
    if (!draft) throw new errors.NotFoundError('Nieuwsconcept niet gevonden.');
    if (reviewerVersion(draft) !== input.version) throw new ReviewConflictError('Het concept is gewijzigd sinds het ophalen. Lees en beoordeel de actuele versie opnieuw.');
    const reasons = await reviewerEligibility(strapi, trx, draft);
    if (input.decision === 'hold') {
      const note = input.note.trim();
      const previous = auditDetail(await table(strapi, trx, TABLES.audit).where({ document_id: documentId, action: 'reviewer.hold' }).orderBy('id', 'desc').first());
      if (previous?.requestHash === requestHash) return { data: { documentId, status: 'draft', decision: 'hold', version: input.version, newlyPublished: false } };
      // Protected human content can receive an audit report, but even its note
      // must not be overwritten by a bot.
      if (!reasons.length) await strapi.db.query(NEWS_UID).update({ where: { id: draft.id }, data: { reviewNote: note } });
      await audit(strapi, trx, documentId, 'reviewer.hold', REVIEWER, { version: input.version, requestHash, note, checkedAt: new Date().toISOString(), protected: reasons.length > 0 });
      return { data: { documentId, status: 'draft', decision: 'hold', version: input.version, newlyPublished: false } };
    }
    if (reasons.length) throw new ForbiddenError(`Controlebot mag dit concept niet publiceren: ${reasons.join('; ')}`);
    if (!automaticPublicationEnabled(process.env)) throw new ForbiddenError('Automatische publicatie is niet actief of het toegestane tijdvenster is verstreken.');
    const evidence = input.evidence ? { ...(draft.privateEvidence || {}), ...input.evidence } : draft.privateEvidence;
    if (input.evidence && input.evidence.sourceUrl !== draft.sourceUrl) throw new ValidationError('Vernieuwd bronbewijs moet bij de bestaande sourceUrl horen.');
    const article = { ...reviewerArticle(draft), privateEvidence: evidence };
    const sources = await sourceSnapshot(strapi);
    const problems = automaticErrors(article, input.verification, sources.data);
    if (problems.length) throw new ValidationError(`Controlepublicatie geblokkeerd: ${problems.join('; ')}. Bewaar de beoordeling met decision hold.`);
    const record = { ...automaticRecord(article, input.verification), reviewerId: REVIEWER.id,
      reviewerName: REVIEWER.name, reviewedVersion: input.version, requestHash };
    await strapi.db.query(NEWS_UID).update({ where: { id: draft.id }, data: {
      privateEvidence: evidence, authorType: 'automatic', authorName: 'PITO Nieuwsredactie', reviewKind: 'automatic',
      automaticReview: record, reviewStatus: 'approved', reviewer: REVIEWER.name, reviewedByAdminId: null,
      verifiedAt: input.verification.checkedAt, reviewNote: input.verification.note,
    } });
    const reviewed = await getDraft(strapi, documentId);
    await strapi.db.query(NEWS_UID).update({ where: { id: reviewed.id }, data: { reviewFingerprint: reviewFingerprint(reviewed) } });
    await audit(strapi, trx, documentId, 'reviewer.publish', REVIEWER, { version: input.version, requestHash,
      policy: record.policy, sourceKey: record.sourceKey, evidenceHash: record.evidenceHash });
    await scope.run({ ...scope.getStore(), automaticDocumentId: documentId, automaticActor: REVIEWER }, () => strapi.documents(NEWS_UID).publish({ documentId }));
    return { data: { documentId, status: 'published', decision: 'publish', newlyPublished: true, slug: reviewed.slug, humanReviewed: false } };
  });
}
