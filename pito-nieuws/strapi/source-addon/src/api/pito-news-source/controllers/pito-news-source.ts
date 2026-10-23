import { requireToken } from '../../../pito-news';
import { importSource, sourceSnapshot } from '../../../pito-news-sources';

export default {
  async snapshot(ctx) {
    requireToken(ctx, 'PITO_NEWS_SOURCE_TOKEN');
    // The existing global populate middleware adds internal ctx.query fields.
    // Only reject actual caller query parameters, not those internal defaults.
    if (ctx.request.querystring) return ctx.badRequest('Het bronnenregister wordt alleen volledig opgehaald.');
    ctx.set('Cache-Control', 'no-store');
    ctx.body = await sourceSnapshot(strapi);
  },
  async importSource(ctx) {
    requireToken(ctx, 'PITO_NEWS_SOURCE_IMPORT_TOKEN');
    const body = ctx.request.body;
    if (!body || Object.keys(body).some(key => key !== 'data') || ctx.request.querystring) return ctx.badRequest('Gebruik alleen { data: bron }.');
    ctx.set('Cache-Control', 'no-store');
    ctx.body = await importSource(strapi, body.data);
    ctx.status = ctx.body.data.created ? 201 : 200;
  },
};
