import './global.css';
import { Provider } from './provider';
import type { ReactNode } from 'react';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html:
              "document.documentElement.lang=location.pathname.startsWith('/docs/en')?'en':'zh-CN';",
          }}
        />
      </head>
      <body className="flex min-h-screen flex-col">
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
