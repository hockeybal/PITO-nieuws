import { errors } from '@strapi/utils';
import { MUNICIPALITIES, publicHttps } from '../pito-news/domain';

const { ValidationError } = errors;
const UID = 'api::pito-news-source.pito-news-source' as any;
const fields = ['sourceKey', 'name', 'url', 'feed', 'kind', 'articleHosts', 'municipality', 'coverageCandidates', 'active', 'reader', 'discovery', 'articlePathPrefix', 'maxLinks'];

function validated(row: any) {
  if (!row || typeof row !== 'object' || Array.isArray(row)) throw new ValidationError('Bron ontbreekt.');
  for (const [key, max] of [['sourceKey', 180], ['name', 240], ['kind', 120], ['url', 4096]] as const) {
    if (typeof row[key] !== 'string' || !row[key].trim() || row[key].length > max) throw new ValidationError(`Ongeldig bronveld: ${key}.`);
  }
  if (!/^[A-Za-z0-9_-]{1,180}$/.test(row.sourceKey) || !publicHttps(row.url) || (row.feed && !publicHttps(row.feed))) throw new ValidationError('Gebruik geldige broncodes en publieke HTTPS-adressen.');
  if (typeof row.active !== 'boolean' || !['direct', 'firecrawl'].includes(row.reader) || !['rss', 'page', 'manual'].includes(row.discovery)) throw new ValidationError('Ongeldige bronverwerking.');
  if (row.discovery === 'rss' && !row.feed) throw new ValidationError('Een RSS-bron vereist een feedadres.');
  if (!Array.isArray(row.articleHosts) || !row.articleHosts.length || row.articleHosts.length > 20 || row.articleHosts.some((h: any) => typeof h !== 'string' || !/^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$/.test(h) || h.includes('..'))) throw new ValidationError('Leg de toegestane nieuwssites vast in articleHosts.');
  if (!row.articleHosts.includes(new URL(row.url).hostname)) throw new ValidationError('De bronpagina moet binnen articleHosts vallen.');
  const coverage = row.coverageCandidates || [];
  if (!Array.isArray(coverage) || coverage.some((m: any) => !MUNICIPALITIES.has(m)) || (row.municipality && !MUNICIPALITIES.has(row.municipality))) throw new ValidationError('Onbekende gemeente in bron.');
  const prefix = row.articlePathPrefix || '/';
  if (typeof prefix !== 'string' || !prefix.startsWith('/') || prefix.startsWith('//') || prefix.length > 500 || /[?#\\]/.test(prefix)) throw new ValidationError('Ongeldig artikelpad.');
  if (!Number.isInteger(row.maxLinks) || row.maxLinks < 1 || row.maxLinks > 20) throw new ValidationError('Kies een linklimiet van 1 tot en met 20.');
  return Object.fromEntries(fields.map(key => [key, key === 'coverageCandidates' ? coverage : key === 'articlePathPrefix' ? prefix : row[key] ?? null]));
}

export async function sourceSnapshot(strapi: any) {
  const rows = await strapi.db.query(UID).findMany({ orderBy: { sourceKey: 'asc' }, limit: 5001 });
  if (rows.length > 5000) throw new ValidationError('Bronnenregister overschrijdt de volledige snapshotlimiet.');
  const data = rows.map(validated);
  return { data, meta: { schemaVersion: 1, complete: true, total: data.length, generatedAt: new Date().toISOString() } };
}

export async function importSource(strapi: any, input: any) {
  if (!input || Object.keys(input).some(key => !fields.includes(key))) throw new ValidationError('Onbekende velden in bronimport.');
  const data = validated(input);
  const find = () => strapi.db.query(UID).findOne({ where: { sourceKey: data.sourceKey } });
  let existing = await find();
  if (existing) return { data: { sourceKey: existing.sourceKey, documentId: existing.documentId, created: false } };
  try {
    const row = await strapi.documents(UID).create({ data });
    return { data: { sourceKey: row.sourceKey, documentId: row.documentId, created: true } };
  } catch (error) {
    // Unique sourceKey also protects a retry after an ambiguous network timeout.
    existing = await find();
    if (existing) return { data: { sourceKey: existing.sourceKey, documentId: existing.documentId, created: false } };
    throw error;
  }
}
