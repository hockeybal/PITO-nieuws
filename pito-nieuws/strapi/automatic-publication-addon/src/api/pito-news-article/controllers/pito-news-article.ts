import { newsSnapshot, receiveDraft, receiveAutomaticPublication, newsReviewQueue, receiveReviewDecision, requireToken } from '../../../pito-news';
import { REVIEW_TOKEN, ReviewConflictError } from '../../../pito-news/reviewer';

export default {
  async snapshot(ctx) {
    requireToken(ctx, 'PITO_NEWS_READ_TOKEN');
    ctx.set('Cache-Control', 'no-store');
    ctx.body = await newsSnapshot(strapi);
  },
  async drafts(ctx) {
    requireToken(ctx, 'PITO_NEWS_DRAFT_TOKEN');
    const body = ctx.request.body;
    if (!body || Object.keys(body).some(key => key !== 'data') || Object.keys(ctx.query || {}).length) return ctx.badRequest('Gebruik alleen { data: concept } zonder queryparameters.');
    ctx.set('Cache-Control', 'no-store');
    ctx.body = await receiveDraft(strapi, body.data);
    ctx.status = ctx.body.data.created ? 201 : 200;
  },
  async automaticPublish(ctx) {
    requireToken(ctx, 'PITO_NEWS_DRAFT_TOKEN');
    const body = ctx.request.body;
    if (!body || Object.keys(body).some(key => !['data', 'verification'].includes(key)) || Object.keys(ctx.query || {}).length) return ctx.badRequest('Gebruik alleen { data: artikel, verification: broncontrole } zonder queryparameters.');
    ctx.set('Cache-Control', 'no-store');
    ctx.body = await receiveAutomaticPublication(strapi, body.data, body.verification);
    ctx.status = ctx.body.data.created ? 201 : 200;
  },
  async reviewQueue(ctx) {
    ctx.set('Cache-Control', 'no-store');
    requireToken(ctx, REVIEW_TOKEN);
    // The host app's general GET middleware injects populate into ctx.query.
    // Validate the caller's original query string instead; this endpoint owns
    // its population and still rejects client-supplied populate/duplicates.
    const params = new URLSearchParams(ctx.request.querystring || '');
    const entries = [...params.entries()];
    if (new Set(entries.map(([key]) => key)).size !== entries.length) return ctx.badRequest('Dubbele controleparameters zijn niet toegestaan.');
    ctx.body = await newsReviewQueue(strapi, Object.fromEntries(entries));
  },
  async reviewDecision(ctx) {
    ctx.set('Cache-Control', 'no-store');
    requireToken(ctx, REVIEW_TOKEN);
    if (Object.keys(ctx.query || {}).length) return ctx.badRequest('De controlebeslissing accepteert geen queryparameters.');
    try {
      ctx.body = await receiveReviewDecision(strapi, ctx.request.body);
      ctx.status = 200;
    } catch (error) {
      if (error instanceof ReviewConflictError) return ctx.throw(409, error.message);
      throw error;
    }
  },
};
