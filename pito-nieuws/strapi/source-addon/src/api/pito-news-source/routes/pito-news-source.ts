// Editing sources belongs to Content Manager. Integration import never updates
// an existing source, and its credential is separate from the worker reader.
export default {
  routes: [
    { method: 'GET', path: '/pito-news/sources', handler: 'pito-news-source.snapshot', config: { auth: false, policies: [], middlewares: [] } },
    { method: 'POST', path: '/pito-news/sources/import', handler: 'pito-news-source.importSource', config: { auth: false, policies: [], middlewares: [] } }
  ]
};
