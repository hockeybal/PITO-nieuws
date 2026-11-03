import { createHash } from 'node:crypto';

export const NEWS_UID = 'api::pito-news-article.pito-news-article';
export const MUNICIPALITIES = new Set(['amersfoort', 'baarn', 'bunnik', 'bunschoten', 'de-bilt', 'de-ronde-venen', 'eemnes', 'houten', 'ijsselstein', 'leusden', 'lopik', 'montfoort', 'nieuwegein', 'oudewater', 'renswoude', 'rhenen', 'soest', 'stichtse-vecht', 'utrecht', 'utrechtse-heuvelrug', 'veenendaal', 'vijfheerenlanden', 'wijk-bij-duurstede', 'woerden', 'woudenberg', 'zeist']);
export const CATEGORIES = new Set(['Bestuur', 'Veiligheid', 'Verkeer', 'Wonen', 'Samenleving', 'Sport']);
export const POPULATE = { municipalities: true, additionalSources: true, image: true, author: { fields: ['username', 'first_name', 'last_name'] } };

export function digest(value: any): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

// PostgreSQL JSONB may reorder object keys while preserving the evidence.
export function evidenceDigest(value: any): string {
  const canonical = (item: any): any => Array.isArray(item) ? item.map(canonical) :
    item && typeof item === 'object' ? Object.fromEntries(Object.keys(item).sort().map(key => [key, canonical(item[key])])) : item;
  return digest(canonical(value));
}

export function municipalitySlugs(article: any): string[] {
  return (article.municipalities || []).map((item: any) => typeof item === 'string' ? item : item?.slug);
}

export function publicHttps(value: any): boolean {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    return url.protocol === 'https:' && !url.username && !url.password && !url.hash &&
      host.includes('.') && !host.endsWith('.local') && !host.endsWith('.localhost') &&
      !host.endsWith('.internal') && !/^\d+(\.\d+){3}$/.test(host) && !host.includes(':');
  } catch { return false; }
}

export function slugify(title: string): string {
  return String(title || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 160).replace(/-$/g, '');
}

// The review is bound to the exact saved content, never to a client-provided flag.
export function reviewFingerprint(article: any): string {
  const keys = ['title', 'slug', 'summary', 'body', 'category', 'provinceWide', 'provinceWideReason',
    'sourceBased', 'sourceUrl', 'sourceName', 'sourcePublishedAt', 'eventDate', 'dateNote', 'verifiedAt',
    'reviewNote', 'rights', 'sensitive', 'impact', 'ranking', 'imageKey', 'imageTopics', 'imageAlt',
    'imageCredit', 'imageRights', 'imageWebUsageApproved', 'authorName', 'authorType', 'origin', 'reviewKind', 'automaticReview'];
  const content = Object.fromEntries(keys.map(key => [key, article[key] ?? null]));
  content.municipalities = municipalitySlugs(article);
  content.additionalSources = (article.additionalSources || []).map(({ name, url }) => ({ name, url }));
  content.image = article.image ? { id: article.image.id, url: article.image.url } : null;
  content.author = article.author ? { documentId: article.author.documentId, username: article.author.username } : null;
  return digest(content);
}

export function publicationErrors(article: any, now = new Date()): string[] {
  const errors: string[] = [];
  const required = ['title', 'slug', 'summary', 'body', 'sourceName', 'rights', 'reviewNote', 'authorName'];
  for (const key of required) {
    if (typeof article[key] !== 'string' || !article[key].trim()) errors.push(`${key} ontbreekt`);
  }
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(article.slug || '')) errors.push('slug moet een geldige URL-naam zijn');
  if (!CATEGORIES.has(article.category)) errors.push('Kies een geldige rubriek');
  for (const key of ['title', 'summary', 'body', 'impact']) {
    if (article[key] && /<\/?[a-z][^>]*>/i.test(article[key])) errors.push(`${key} moet gewone tekst zonder HTML zijn`);
  }
  const municipalities = municipalitySlugs(article);
  if (municipalities.some(slug => !MUNICIPALITIES.has(slug))) errors.push('Onbekende gemeente');
  if (new Set(municipalities).size !== municipalities.length) errors.push('Gemeente is dubbel gekozen');
  if (article.provinceWide === true) {
    if (!article.provinceWideReason?.trim()) errors.push('Onderbouw provinciebrede relevantie in provinceWideReason');
  } else if (!municipalities.length) errors.push('Kies minimaal één gemeente of onderbouw provinceWide');
  if (article.sourceBased !== false && !publicHttps(article.sourceUrl)) errors.push('sourceUrl moet een openbare HTTPS-bron zijn');
  if (article.sourceBased !== false && !article.sourcePublishedAt && !article.dateNote?.trim()) errors.push('Leg de brondatum vast, of licht de ontbrekende datum toe in dateNote');
  if (article.sourcePublishedAt && (!Number.isFinite(Date.parse(article.sourcePublishedAt)) || Date.parse(article.sourcePublishedAt) > now.getTime())) errors.push('Ongeldige of toekomstige brondatum');
  if (article.eventDate && (!/^\d{4}-\d{2}-\d{2}$/.test(article.eventDate) || !Number.isFinite(Date.parse(article.eventDate)) || new Date(article.eventDate).toISOString().slice(0, 10) !== article.eventDate)) errors.push('Ongeldige gebeurtenisdatum');
  if (article.eventDate && article.sourcePublishedAt && article.eventDate !== article.sourcePublishedAt.slice(0, 10) && !article.dateNote?.trim()) errors.push('Licht het verschil tussen bron- en gebeurtenisdatum toe');
  const verified = Date.parse(article.verifiedAt);
  if (!Number.isFinite(verified) || verified > now.getTime()) errors.push('verifiedAt moet een echte inhoudelijke controledatum zijn, niet in de toekomst');
  if ((article.additionalSources || []).some(source => !source.name?.trim() || !publicHttps(source.url))) errors.push('Extra bronnen moeten een naam en openbare HTTPS-link hebben');
  if (article.imageWebUsageApproved === true && (!article.image || !article.imageCredit?.trim() || !article.imageRights?.trim() || !article.imageAlt?.trim())) errors.push('Vrijgegeven beeld vereist een foto, alt-tekst, credit en rechtenonderbouwing');
  if (article.reviewKind === 'automatic') {
    const review = article.automaticReview;
    if (article.reviewStatus !== 'approved' || article.authorType !== 'automatic' || article.reviewedByAdminId || !article.reviewer?.trim() ||
        review?.policy !== 'pito-news-automatic-v1' || !review.sourceKey || !review.note ||
        !Number.isFinite(Date.parse(review.validatedAt)) || !article.privateEvidence || review.evidenceHash !== evidenceDigest(article.privateEvidence)) errors.push('Geldig automatisch publicatiebewijs ontbreekt');
  } else if (article.reviewStatus !== 'approved' || !article.reviewer?.trim() || !article.reviewedByAdminId) errors.push('Goedkeuring door een werkelijk aangemelde redacteur ontbreekt');
  if (article.reviewFingerprint !== reviewFingerprint(article)) errors.push('De opgeslagen inhoud is niet in deze versie beoordeeld; keur opnieuw goed');
  return errors;
}

export function publicArticle(article: any, ledger: any): any {
  if (!article.publishedAt || article.reviewStatus !== 'approved') throw new Error('Niet-gepubliceerd of onbeoordeeld artikel in snapshot');
  const errors = publicationErrors(article);
  if (errors.length || !ledger?.first_published_at || !ledger?.last_published_at) throw new Error('Ongeldige publicatie; snapshot blijft ongewijzigd');
  const keys = ['title', 'slug', 'summary', 'body', 'category', 'sourceUrl', 'sourceName', 'sourcePublishedAt', 'eventDate',
    'dateNote', 'verifiedAt', 'reviewStatus', 'sensitive', 'impact', 'ranking', 'publishedAt'];
  const result = Object.fromEntries(keys.map(key => [key, article[key] ?? null]));
  return {
    id: article.documentId, documentId: article.documentId, ...result,
    municipalities: municipalitySlugs(article), provinceWide: article.provinceWide === true, sourceBased: article.sourceBased !== false,
    additionalSources: (article.additionalSources || []).map(({ name, url }) => ({ name, url })),
    author: article.authorName, authorType: article.authorType === 'automatic' ? 'automatic' : 'human', humanReviewed: article.reviewKind !== 'automatic', reviewKind: article.reviewKind || 'human',
    // A legacy library key carries no rights evidence. Only explicitly cleared media is exported.
    imageKey: null, imageTopics: article.imageTopics || [],
    image: article.imageWebUsageApproved && article.image ? { url: article.image.url, alt: article.imageAlt, credit: article.imageCredit, web_usage_approved: true } : null,
    firstPublishedAt: ledger.first_published_at, lastPublishedAt: ledger.last_published_at,
    updatedAt: ledger.last_published_at,
  };
}
