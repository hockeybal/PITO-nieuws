// Explicit integration routes only. Content Manager remains the only generic
// editing API; the independent reviewer cannot submit or rewrite article text.
export default {
  routes: [
    { method: 'GET', path: '/pito-news/snapshot', handler: 'pito-news-article.snapshot', config: { auth: false, policies: [], middlewares: [] } },
    { method: 'POST', path: '/pito-news/drafts', handler: 'pito-news-article.drafts', config: { auth: false, policies: [], middlewares: [] } },
    { method: 'POST', path: '/pito-news/automatic-publish', handler: 'pito-news-article.automaticPublish', config: { auth: false, policies: [], middlewares: [] } },
    { method: 'GET', path: '/pito-news/review-queue', handler: 'pito-news-article.reviewQueue', config: { auth: false, policies: [], middlewares: [] } },
    { method: 'POST', path: '/pito-news/review-decision', handler: 'pito-news-article.reviewDecision', config: { auth: false, policies: [], middlewares: [] } },
  ]
};
