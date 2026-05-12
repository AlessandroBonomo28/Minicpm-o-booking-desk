export default function DocsIndex() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center gap-6 p-8">
      <meta httpEquiv="refresh" content="0; url=/docs/zh/" />
      <h1 className="text-3xl font-semibold">MiniCPM-o Docs</h1>
      <p className="text-fd-muted-foreground">Choose a language to continue.</p>
      <div className="flex gap-3">
        <a className="text-fd-primary underline" href="/docs/zh/">中文</a>
        <a className="text-fd-primary underline" href="/docs/en/">English</a>
      </div>
    </main>
  );
}
