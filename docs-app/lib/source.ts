import { docs } from 'collections/server';
import { loader } from 'fumadocs-core/source';
import { i18n } from '@/lib/i18n';

export const source = loader({
  i18n,
  baseUrl: '/',
  url(slugs, locale) {
    return '/' + [locale ?? 'zh', ...slugs].join('/');
  },
  source: docs.toFumadocsSource(),
});
