// Read-only export of local PITO CMS concepts for the separate loopback preview.
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const assert = require('node:assert/strict');

async function main() {
  const [strapiDir, outputDir] = process.argv.slice(2);
  if (!strapiDir || !outputDir) throw Error('Strapi-map en uitvoermap zijn verplicht.');
  const req = createRequire(path.resolve(strapiDir, 'package.json'));
  const env = req('dotenv').parse(fs.readFileSync(path.join(strapiDir, '.env')));
  assert.ok(['127.0.0.1', 'localhost', '::1'].includes(env.DATABASE_HOST));
  const { Client } = req('pg');
  const client = new Client({host:env.DATABASE_HOST, port:Number(env.DATABASE_PORT || 5432),
    database:env.DATABASE_NAME, user:env.DATABASE_USERNAME, password:env.DATABASE_PASSWORD});
  await client.connect();
  try {
    await client.query('BEGIN READ ONLY');
    const result = await client.query(`select a.*, coalesce((
      select json_agg(m.slug order by ac."order") from pito_news_articles_cmps ac
      join components_pito_news_municipalities m on m.id=ac.cmp_id
      where ac.entity_id=a.id and ac.component_type='pito-news.municipality' and ac.field='municipalities'
    ),'[]'::json) as places from pito_news_articles a
      where a.published_at is null and a.review_status='needs_review' order by a.document_id limit 5001`);
    assert.ok(result.rows.length > 0 && result.rows.length <= 5000);
    const articles = result.rows.map(a => {
      const legacy = a.origin === 'import';
      return {id:a.document_id, documentId:a.document_id, title:a.title, slug:a.slug,
        summary:a.summary, body:a.body, category:a.category, municipalities:a.places,
        provinceWide:a.province_wide, sourceBased:a.source_based,
        sourceUrl:a.source_url, sourceName:a.source_name,
        sourcePublishedAt:a.source_published_at ? a.source_published_at.toISOString() : '',
        eventDate:a.event_date || '', dateNote:a.date_note || '', rights:a.rights,
        ranking:a.ranking || {}, imageKey:a.image_key || '', imageTopics:a.image_topics || [],
        reviewStatus:a.review_status, publicationStatus:'draft', humanReviewed:false,
        authorType:a.author_type, authorName:legacy ? 'PITO · lokaal testconcept uit bestaande dataset' : 'PITO · AI-schrijfconcept (Codex)',
        authorship:{kind:'automated'}, testOrigin:legacy ? 'existing-local-article' : 'saved-firecrawl-source'};
    });
    const state = await client.query(`select count(*) filter (where published_at is null)::int as drafts,
      count(*) filter (where published_at is not null)::int as published from pito_news_articles`);
    const snapshot = {savedFrom:'local-strapi-database-readback', checkedAt:new Date().toISOString(),
      description:'Lokale concepttest met nieuw opgehaalde bronberichten en bestaande voorbeeldartikelen. Het nieuwsoverzicht gebruikt de oorspronkelijke bronpublicatiedatum.', articles};
    fs.mkdirSync(outputDir, {recursive:true, mode:0o700});
    const file = path.join(outputDir, 'strapi-preview.json');
    fs.writeFileSync(file+'.tmp', JSON.stringify(snapshot,null,2), {mode:0o600});
    fs.renameSync(file+'.tmp',file);
    await client.query('ROLLBACK');
    console.log(JSON.stringify({previewConcepts:articles.length, cms:state.rows[0],
      newestSourceDate:articles.map(a=>a.sourcePublishedAt).sort().at(-1)}));
  } finally { await client.end(); }
}
main().catch(() => { console.error('Lokale concept-export niet voltooid; configuratie en database controleren.'); process.exitCode=1; });
