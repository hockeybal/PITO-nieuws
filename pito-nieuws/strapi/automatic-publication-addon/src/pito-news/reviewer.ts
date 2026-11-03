import { errors } from '@strapi/utils';
import { evidenceDigest } from './domain';

export const REVIEWER = { id: 'independent-reviewer', name: 'PITO onafhankelijke automatische controle' };
export const REVIEW_TOKEN = 'PITO_NEWS_REVIEW_TOKEN';
const { ValidationError } = errors;
const isObject = (value: any) => value && typeof value === 'object' && !Array.isArray(value);

export class ReviewConflictError extends Error {}

export function reviewerConfigured(environment: Record<string, string | undefined>): boolean {
  return (environment[REVIEW_TOKEN] || '').length >= 32;
}

export function validateReviewerConfiguration(environment: Record<string, string | undefined>) {
  const token = environment[REVIEW_TOKEN];
  if (!token) return;
  if (token.length < 32) throw new Error('PITO News controletoken moet minimaal 32 tekens bevatten.');
  for (const name of ['PITO_NEWS_DRAFT_TOKEN', 'PITO_NEWS_READ_TOKEN', 'PITO_NEWS_SOURCE_TOKEN', 'PITO_NEWS_SOURCE_IMPORT_TOKEN']) {
    if (token === environment[name]) throw new Error('PITO News controletoken moet van alle andere koppelsleutels verschillen.');
  }
}

// Deliberately omit reporting metadata: writing a hold note does not create a
// new article version. All content, evidence, authorship and approval identity
// remain bound to the version that the reviewer actually read.
const contentFields = ['externalKey', 'eventKey', 'title', 'slug', 'summary', 'body', 'category',
  'provinceWide', 'provinceWideReason', 'sourceBased', 'sourceUrl', 'sourceName', 'sourcePublishedAt',
  'eventDate', 'dateNote', 'rights', 'sensitive', 'impact', 'ranking', 'imageKey', 'imageTopics',
  'imageAlt', 'imageCredit', 'imageRights', 'imageWebUsageApproved', 'evidenceReference', 'privateEvidence',
  'origin', 'authorName', 'authorType'];

export function reviewerArticle(draft: any) {
  return {
    ...Object.fromEntries(contentFields.map(key => [key, draft[key] ?? null])),
    municipalities: (draft.municipalities || []).map(item => ({ slug: typeof item === 'string' ? item : item.slug })),
    additionalSources: (draft.additionalSources || []).map(({ name, url }) => ({ name, url })),
    image: draft.image ? { id: draft.image.id, url: draft.image.url } : null,
    author: draft.author ? { documentId: draft.author.documentId, username: draft.author.username } : null,
  };
}

export function reviewerVersion(draft: any): string {
  return evidenceDigest({ documentId: draft.documentId, article: reviewerArticle(draft),
    reviewStatus: draft.reviewStatus, reviewKind: draft.reviewKind, reviewedByAdminId: draft.reviewedByAdminId ?? null,
    reviewer: draft.reviewer ?? null, automaticReview: draft.automaticReview ?? null });
}

export function reviewQueueParameters(query: any) {
  if (!isObject(query) || Object.keys(query).some(key => !['cursor', 'limit'].includes(key))) throw new ValidationError('Gebruik alleen cursor en limit voor de controlewachtrij.');
  if (query.cursor !== undefined && (typeof query.cursor !== 'string' || !/^[a-zA-Z0-9]{1,64}$/.test(query.cursor))) throw new ValidationError('Ongeldige controlecursor.');
  if (query.limit !== undefined && (typeof query.limit !== 'string' || !/^(?:[1-9]|1[0-9]|20)$/.test(query.limit))) throw new ValidationError('limit moet 1 tot en met 20 zijn.');
  return { cursor: query.cursor || null, limit: query.limit ? Number(query.limit) : 20 };
}

export function validateReviewDecision(input: any) {
  if (!isObject(input) || Object.keys(input).some(key => !['documentId', 'version', 'decision', 'verification', 'evidence', 'note'].includes(key))) throw new ValidationError('Gebruik alleen documentId, version, decision, verification, evidence en note.');
  if (typeof input.documentId !== 'string' || !/^[a-zA-Z0-9]{1,64}$/.test(input.documentId) || typeof input.version !== 'string' || !/^[a-f0-9]{64}$/.test(input.version)) throw new ValidationError('Geldige documentId en version uit de controlewachtrij zijn verplicht.');
  if (!['publish', 'hold'].includes(input.decision)) throw new ValidationError('decision moet publish of hold zijn.');
  if (JSON.stringify(input).length > 2_000_000) throw new ValidationError('Controledossier is te groot.');
  if (input.decision === 'hold') {
    if (input.verification !== undefined || input.evidence !== undefined || typeof input.note !== 'string' || input.note.trim().length < 30 || input.note.length > 20000) throw new ValidationError('Een hold vereist alleen een concrete note van 30 tot en met 20000 tekens.');
  } else {
    if (input.note !== undefined || !isObject(input.verification) || Object.keys(input.verification).some(key => !['sourceKey', 'checkedAt', 'note', 'facts', 'municipalityEvidence'].includes(key))) throw new ValidationError('Een publicatie vereist verification met broncode, controletijd, notitie, feiten en gemeentebewijs.');
    for (const [field, allowed] of [['facts', ['statement', 'quote']], ['municipalityEvidence', ['slug', 'quote']]] as const) {
      if (Array.isArray(input.verification[field]) && input.verification[field].some(item => !isObject(item) || Object.keys(item).some(key => !(allowed as readonly string[]).includes(key)))) throw new ValidationError(`Onbekende of ongeldige velden in verification.${field}.`);
    }
    if (input.evidence !== undefined && (!isObject(input.evidence) || Object.keys(input.evidence).sort().join(',') !== 'fetchedAt,sourceText,sourceUrl' || Object.values(input.evidence).some(value => typeof value !== 'string'))) throw new ValidationError('Vernieuwd bewijs bevat uitsluitend sourceText, sourceUrl en fetchedAt.');
  }
}

export function matchingReviewSources(article: any, sources: any[]) {
  try {
    const url = new URL(article.sourceUrl);
    return sources.filter(source => source.active === true && source.discovery === 'rss' &&
      (source.articleHosts || []).includes(url.hostname) && url.pathname.startsWith(source.articlePathPrefix || '/'));
  } catch { return []; }
}
