import { AsyncResource } from 'node:async_hooks';
import { NEWS_UID } from './domain';

const installed = Symbol('pito-news-audit-compatibility');

/**
 * audit-logs 2.1.2 defers CRUD logging with setTimeout inside the Document Service
 * middleware. Such timers inherit the CMS transaction's async-local context and
 * can try to reuse that transaction after commit. Keep its normal log format,
 * redaction and explicit user attribution, but write this new collection's
 * auxiliary plugin log from the neutral bootstrap context. The transactional
 * pito_news_audit table remains the authoritative publication/audit ledger.
 */
export function installNewsAuditCompatibility(strapi: any) {
  const plugin = strapi.plugin('audit-logs');
  const service = plugin?.service('log');
  if (!service || typeof service.logEvent !== 'function' || service[installed]) return;
  const neutral = new AsyncResource('PITO_NEWS_AUDIT_COMPATIBILITY');
  const original = service.logEvent;
  service.logEvent = function (action: string, data: any, user: any) {
    if (data?.uid !== NEWS_UID) return original.call(this, action, data, user);
    return neutral.runInAsyncScope(original, this, action, data, user);
  };
  service[installed] = true;
}
