import { NEWS_UID } from './domain';

// Native Content Manager configuration, not a second editorial status system.
// Strapi's configuration service uses model.config only when generating missing
// settings/metadatas/layouts; saved administrator customizations take precedence.
export const NEWS_ADMIN_LABELS: Record<string, string> = {
  title: 'Titel', slug: 'Vaste URL-naam', summary: 'Intro', body: 'Artikeltekst', category: 'Rubriek',
  municipalities: 'Gemeenten', provinceWide: 'Provinciebreed', provinceWideReason: 'Onderbouwing provinciebreed',
  sourceBased: 'Gebaseerd op een bron', sourceUrl: 'Bronlink (HTTPS)', sourceName: 'Bronnaam', sourcePublishedAt: 'Publicatiedatum bron',
  eventDate: 'Gebeurtenisdatum', dateNote: 'Toelichting op datums', verifiedAt: 'Inhoudelijk gecontroleerd op',
  reviewStatus: 'Redactionele beoordeling', reviewer: 'Beoordeeld door', reviewNote: 'Beoordelings- of correctienotitie',
  rights: 'Onderbouwing tekst- en beeldrechten', sensitive: 'Gevoelige inhoud', additionalSources: 'Extra bronnen', impact: 'Gevolgen voor inwoners',
  image: 'Nieuwsbeeld', imageAlt: 'Beeldbeschrijving', imageCredit: 'Fotocredit', imageRights: 'Bewijs van beeldrechten', imageWebUsageApproved: 'Beeld vrijgegeven voor de website',
  author: 'Bestaande PITO-auteur', authorName: 'Publieke auteursnaam', authorType: 'Soort auteurschap', origin: 'Herkomst',
  ranking: 'Optionele rangschikking', imageKey: 'Bestaande beeldsleutel (geen rechtenbewijs)', imageTopics: 'Beeldonderwerpen',
  firstPitoPublishedAt: 'Eerste PITO-publicatie', lastPitoPublishedAt: 'Laatste gepubliceerde wijziging',
};

const HIDDEN = ['externalKey', 'eventKey', 'evidenceReference', 'privateEvidence', 'reviewFingerprint', 'reviewedByAdminId', 'reviewKind', 'automaticReview'];
const READONLY = ['reviewer', 'firstPitoPublishedAt', 'lastPitoPublishedAt', 'origin', 'authorType', 'verifiedAt'];
const row = (...names: string[]) => names.map(name => ({ name, size: names.length === 1 ? 12 : 6 }));

export function newsAdminDefaults(schema: any) {
  const metadatas: any = {};
  for (const [name, label] of Object.entries(NEWS_ADMIN_LABELS)) {
    const description = schema.attributes[name]?.description || '';
    metadatas[name] = { edit: { label, description, visible: true, editable: !READONLY.includes(name) }, list: { label } };
  }
  metadatas.reviewStatus.edit.description = 'Na schrijven opslaan. Controleer daarna de inhoud en kies approved; sla opnieuw op en klik Publish. Een opgeslagen correctie vraagt opnieuw beoordeling.';
  metadatas.verifiedAt.edit.description = 'Wordt bij jouw expliciete goedkeuring (approved + Save) automatisch door de server vastgelegd.';
  for (const name of HIDDEN) metadatas[name] = { edit: { visible: false, editable: false }, list: { label: name } };
  return {
    settings: { mainField: 'title', defaultSortBy: 'updatedAt', defaultSortOrder: 'DESC', pageSize: 25, searchable: true, filterable: true, bulkable: false },
    attributes: Object.fromEntries(HIDDEN.map(name => [name, { hidden: true }])),
    metadatas,
    layouts: {
      list: ['title', 'category', 'reviewStatus', 'firstPitoPublishedAt'],
      edit: [
        row('title'), row('slug'), row('summary'), row('body'), row('category', 'sensitive'),
        row('municipalities'), row('provinceWide'), row('provinceWideReason'),
        row('author'), row('authorName'), row('sourceBased'), row('sourceName'), row('sourceUrl'),
        row('sourcePublishedAt', 'eventDate'), row('dateNote'), row('additionalSources'), row('impact'),
        row('rights'), row('image'), row('imageAlt'), row('imageCredit'), row('imageRights'), row('imageWebUsageApproved'),
        row('verifiedAt'), row('reviewNote'), row('reviewStatus', 'reviewer'),
        row('firstPitoPublishedAt', 'lastPitoPublishedAt'), row('origin', 'authorType'),
      ],
    },
  };
}

export function installNewsAdminDefaults(strapi: any) {
  const model = strapi.contentType(NEWS_UID);
  model.config = { ...newsAdminDefaults(model), ...(model.config || {}) };
  for (const [uid, labels] of Object.entries({ 'pito-news.municipality': { slug: 'Gemeente' }, 'pito-news.source': { name: 'Bronnaam', url: 'Bronlink (HTTPS)' } })) {
    const component = strapi.components[uid];
    if (component) component.config = {
      settings: { mainField: uid.endsWith('municipality') ? 'slug' : 'name', defaultSortBy: uid.endsWith('municipality') ? 'slug' : 'name', defaultSortOrder: 'ASC', pageSize: 10, searchable: true, filterable: true, bulkable: false },
      metadatas: Object.fromEntries(Object.entries(labels).map(([name, label]) => [name, { edit: { label }, list: { label } }])),
      ...(component.config || {}),
    };
  }
}

export async function initializeNewsAdminConfiguration(strapi: any) {
  const service = strapi.plugin('content-manager').service('content-types');
  const model = service.findContentType(NEWS_UID);
  const existing = await service.findConfiguration(model);
  // Normally Strapi's own plugin bootstrap has already initialized this using
  // model.config. Only repair a genuinely missing configuration; never reset a
  // saved layout or labels chosen by the administrator.
  if (existing?.layouts?.edit?.length && existing.metadatas?.verifiedAt) {
    const edit = existing.metadatas.verifiedAt.edit || {};
    const description = newsAdminDefaults(strapi.contentType(NEWS_UID)).metadatas.verifiedAt.edit.description;
    if (edit.description !== description || edit.editable !== false) {
      await service.updateConfiguration(model, { settings: existing.settings, layouts: existing.layouts,
        metadatas: { ...existing.metadatas, verifiedAt: { ...existing.metadatas.verifiedAt, edit: { ...edit, description, editable: false } } } });
    }
  } else if (!existing?.layouts?.edit?.length) {
    const defaults = newsAdminDefaults(strapi.contentType(NEWS_UID));
    await service.updateConfiguration(model, { settings: defaults.settings, metadatas: defaults.metadatas, layouts: defaults.layouts });
  }
}
