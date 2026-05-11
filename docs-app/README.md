# MiniCPM-o Docs App

This directory contains the Fumadocs + Next.js documentation site for `/docs`.

## Development

Install dependencies once:

```bash
bun install
```

Start the local docs dev server:

```bash
bun run dev
```

By default it serves:

```text
http://localhost:3030/docs/zh/
http://localhost:3030/docs/en/
```

## Build

Build and publish the static documentation assets:

```bash
bun run build
```

The build output is copied to:

```text
../static/docs/
```

The Python gateway serves that directory at `/docs`.

## Content Layout

Documentation source lives under:

```text
content/docs/zh/
content/docs/en/
```

Realtime API pages are under:

```text
content/docs/zh/realtime-api/
content/docs/en/realtime-api/
```

Project documentation pages are migrated from the legacy `docs/zh` and `docs/en` trees.

## Runtime Integration

`start_all.sh` automatically runs this build before starting the gateway unless:

```bash
SKIP_DOCS_BUILD=1 bash start_all.sh
```

Use `SKIP_DOCS_BUILD=1` only for backend-only debugging.
