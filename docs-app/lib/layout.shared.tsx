import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

export function baseOptions(lang: string): BaseLayoutProps {
  const isZh = lang === 'zh';
  const projectHomeLabel = isZh ? '项目首页' : 'Project Home';

  return {
    nav: {
      title: 'MiniCPM-o Docs',
    },
    links: [
      { text: isZh ? '首页' : 'Home', url: isZh ? '/zh' : '/en' },
      { text: isZh ? '切换 English' : 'Switch 中文', url: isZh ? '/en' : '/zh' },
      {
        type: 'custom',
        children: (
          <a
            className="relative flex flex-row items-center gap-2 rounded-lg p-2 text-start text-fd-muted-foreground wrap-anywhere transition-colors hover:bg-fd-accent/50 hover:text-fd-accent-foreground/80 hover:transition-none"
            href="/"
            style={{ paddingInlineStart: 'calc(2 * var(--spacing))' }}
          >
            {projectHomeLabel}
          </a>
        ),
      },
      { text: 'GitHub', url: 'https://github.com/OpenBMB/MiniCPM-o-Demo', external: true },
    ],
  };
}
