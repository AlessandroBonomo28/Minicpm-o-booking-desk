import { source } from '@/lib/source';

export const revalidate = false;

async function getText(page: ReturnType<typeof source.getPages>[number]) {
  const processed = await page.data.getText('processed');
  return `# ${page.data.title} (${page.url})\n\n${processed}`;
}

export async function GET() {
  const pages = source.getPages();
  const text = await Promise.all(pages.map(getText));
  return new Response(text.join('\n\n'));
}
