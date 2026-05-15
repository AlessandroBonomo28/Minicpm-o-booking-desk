'use client';

import { DocsSearchDialog } from '@/components/search-dialog';
import { RootProvider } from 'fumadocs-ui/provider/next';
import type { ReactNode } from 'react';

export function Provider({ children }: { children: ReactNode }) {
  return (
    <RootProvider search={{ SearchDialog: DocsSearchDialog }}>
      {children}
    </RootProvider>
  );
}
