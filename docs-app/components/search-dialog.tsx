'use client';

import { create } from '@orama/orama';
import { createTokenizer } from '@orama/tokenizers/mandarin';
import {
  SearchDialog,
  SearchDialogClose,
  SearchDialogContent,
  SearchDialogFooter,
  SearchDialogHeader,
  SearchDialogIcon,
  SearchDialogInput,
  SearchDialogList,
  SearchDialogOverlay,
  TagsList,
  TagsListItem,
} from 'fumadocs-ui/components/dialog/search';
import { useI18n } from 'fumadocs-ui/contexts/i18n';
import { useDocsSearch } from 'fumadocs-core/search/client';
import { useOnChange } from 'fumadocs-core/utils/use-on-change';
import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { DefaultSearchDialogProps } from 'fumadocs-ui/components/dialog/search-default';

const SEARCH_INDEX_PATH = '/docs/api/search';

function initSearchDatabase(locale?: string) {
  if (locale === 'zh') {
    return create({
      schema: { _: 'string' },
      components: { tokenizer: createTokenizer() },
    });
  }

  return create({
    schema: { _: 'string' },
    language: 'english',
  });
}

export function DocsSearchDialog({
  defaultTag,
  tags = [],
  delayMs,
  allowClear = false,
  links = [],
  footer,
  ...props
}: DefaultSearchDialogProps & { footer?: ReactNode }) {
  const { locale } = useI18n();
  const [tag, setTag] = useState(defaultTag);
  const { search, setSearch, query } = useDocsSearch({
    type: 'static',
    from: SEARCH_INDEX_PATH,
    initOrama: initSearchDatabase,
    locale,
    tag,
    delayMs,
  });

  const defaultItems = useMemo(() => {
    if (links.length === 0) return null;

    return links.map(([name, link]) => ({
      type: 'page' as const,
      id: name,
      content: name,
      url: link,
    }));
  }, [links]);

  useOnChange(defaultTag, (value) => {
    setTag(value);
  });

  return (
    <SearchDialog search={search} onSearchChange={setSearch} isLoading={query.isLoading} {...props}>
      <SearchDialogOverlay />
      <SearchDialogContent>
        <SearchDialogHeader>
          <SearchDialogIcon />
          <SearchDialogInput />
          <SearchDialogClose />
        </SearchDialogHeader>
        <SearchDialogList items={query.data !== 'empty' ? query.data : defaultItems} />
      </SearchDialogContent>
      <SearchDialogFooter>
        {tags.length > 0 && (
          <TagsList tag={tag} onTagChange={setTag} allowClear={allowClear}>
            {tags.map((tag) => (
              <TagsListItem key={tag.value} value={tag.value}>
                {tag.name}
              </TagsListItem>
            ))}
          </TagsList>
        )}
        {footer}
      </SearchDialogFooter>
    </SearchDialog>
  );
}
