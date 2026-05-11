import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

export function baseOptions(lang: string): BaseLayoutProps {
  const isZh = lang === 'zh';

  return {
    nav: {
      title: 'MiniCPM-o Docs',
    },
    links: [
      { text: isZh ? '首页' : 'Home', url: isZh ? '/zh' : '/en' },
      { text: isZh ? '切换 English' : 'Switch 中文', url: isZh ? '/en' : '/zh' },
      { text: isZh ? '项目首页' : 'Project Home', url: '/' },
      { text: 'GitHub', url: 'https://github.com/OpenBMB/MiniCPM-o-Demo', external: true },
    ],
  };
}
