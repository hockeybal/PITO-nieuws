import { evidenceDigest, MUNICIPALITIES, publicHttps } from './domain';

export const AUTOMATIC_POLICY = 'pito-news-automatic-v1';
const normalized = (value: string) => value.normalize('NFKC').replace(/\s+/g, ' ').trim();

export function automaticPublicationEnabled(environment: Record<string, string | undefined>, now = Date.now()): boolean {
  if (environment.PITO_NEWS_AUTOMATIC_PUBLISH_ENABLED === '1') return true;
  const until = Date.parse(environment.PITO_NEWS_AUTOMATIC_PUBLISH_UNTIL || '');
  return Number.isFinite(until) && until > now;
}

// Structural/evidence checks, not a claim of independent human fact checking.
// The source catalogue and the permission window are controlled by the CMS.
export function automaticErrors(input: any, verification: any, sources: any[], now = new Date()): string[] {
  const errors: string[] = [];
  if (!input || !verification || typeof verification !== 'object') return ['data en verification zijn verplicht'];
  const source = sources.find(row => row.sourceKey === verification.sourceKey);
  if (!source || source.active !== true || source.discovery !== 'rss') errors.push('Bron is geen actieve RSS-bron in live Strapi');
  if (!publicHttps(input.sourceUrl)) errors.push('Een openbare HTTPS-bron is verplicht');
  else if (source) {
    const url = new URL(input.sourceUrl);
    if (!(source.articleHosts || []).includes(url.hostname) || !url.pathname.startsWith(source.articlePathPrefix || '/')) errors.push('Artikel valt buiten de ingestelde bronhosts of het bronpad');
  }
  const evidence = input.privateEvidence;
  const text = typeof evidence?.sourceText === 'string' ? normalized(evidence.sourceText) : '';
  if (text.length < 300 || text.length > 1_500_000 || evidence?.sourceUrl !== input.sourceUrl) errors.push('Volledige broninhoud met overeenkomende sourceUrl ontbreekt');
  const checked = Date.parse(verification.checkedAt);
  const fetched = Date.parse(evidence?.fetchedAt);
  const published = Date.parse(input.sourcePublishedAt);
  for (const [name, stamp, maxAge] of [['checkedAt', checked, 86400000], ['fetchedAt', fetched, 86400000], ['sourcePublishedAt', published, 14 * 86400000]] as const) {
    if (!Number.isFinite(stamp) || stamp > now.getTime() || now.getTime() - stamp > maxAge) errors.push(`${name} ontbreekt of valt buiten de toegestane periode`);
  }
  if (Number.isFinite(checked) && Number.isFinite(fetched) && checked < fetched) errors.push('Broncontrole kan niet vóór het ophalen liggen');
  if (typeof verification.note !== 'string' || verification.note.trim().length < 30) errors.push('Concrete broncontrole in verification.note ontbreekt');
  const facts = verification.facts;
  if (!Array.isArray(facts) || facts.length < 1 || facts.length > 100) errors.push('Controleerbare feiten met letterlijke bewijsfragmenten ontbreken');
  else for (const fact of facts) {
    if (typeof fact?.statement !== 'string' || fact.statement.trim().length < 10 || typeof fact?.quote !== 'string' || normalized(fact.quote).length < 20 || !text.includes(normalized(fact.quote))) errors.push('Een feit heeft geen terugvindbaar bewijsfragment in de volledige brontekst');
  }
  const municipalities = (Array.isArray(input.municipalities) ? input.municipalities : []).map(value => typeof value === 'string' ? value : value?.slug);
  if (!Array.isArray(input.municipalities) || !municipalities.length || municipalities.some(slug => !MUNICIPALITIES.has(slug))) errors.push('Onderbouwde gemeenten zijn verplicht voor automatische publicatie');
  if (input.provinceWide === true) errors.push('Provinciebrede artikelen blijven ter beoordeling als concept');
  for (const slug of municipalities) {
    const proof = (Array.isArray(verification.municipalityEvidence) ? verification.municipalityEvidence : []).find(item => item.slug === slug);
    if (!proof || typeof proof.quote !== 'string' || normalized(proof.quote).length < 10 || !text.includes(normalized(proof.quote))) errors.push(`Gemeentebewijs ontbreekt: ${slug}`);
  }
  if (input.sensitive !== false) errors.push('Gevoelige of niet geclassificeerde artikelen blijven concept');
  if (input.sourceBased !== true || input.origin !== 'writer') errors.push('Automatische publicatie vereist een brongebaseerd writer-artikel');
  if (typeof input.rights !== 'string' || input.rights.trim().length < 30) errors.push('Onderbouwing eigen tekst en rechten ontbreekt');
  if (typeof input.evidenceReference !== 'string' || !input.evidenceReference.trim()) errors.push('evidenceReference ontbreekt');
  if (typeof input.body !== 'string' || input.body.trim().length < 150 || typeof input.summary !== 'string' || input.summary.trim().length < 30) errors.push('Artikeltekst of samenvatting is onvolledig');
  if (typeof input.body === 'string' && normalized(input.body).length >= 150 && text.includes(normalized(input.body))) errors.push('Artikeltekst is geheel uit de bron gekopieerd');
  return [...new Set(errors)];
}

export function automaticRecord(input: any, verification: any, now = new Date()) {
  return { policy: AUTOMATIC_POLICY, sourceKey: verification.sourceKey, checkedAt: verification.checkedAt,
    validatedAt: now.toISOString(), evidenceHash: evidenceDigest(input.privateEvidence), note: verification.note,
    facts: verification.facts, municipalityEvidence: verification.municipalityEvidence };
}
