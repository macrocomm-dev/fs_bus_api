#!/usr/bin/env node
/**
 * generate-api.mjs
 *
 * Fetches the protected OpenAPI spec from the running FS Bus API backend,
 * saves it locally, then uses openapi-typescript to generate TypeScript
 * types into src/app/api/generated/.
 *
 * Usage:
 *   node scripts/generate-api.mjs
 *
 * Required env vars (or set in .env.local):
 *   API_URL          Base URL of the backend  (default: http://127.0.0.1:8000)
 *   API_ADMIN_EMAIL  Admin email to authenticate with
 *   API_ADMIN_PASS   Admin password
 *
 * The script will load .env.local from the project root if present.
 */

import { readFileSync, mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { execSync } from 'node:child_process';

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------
const __dir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dir, '..');
const outDir = resolve(projectRoot, 'src/app/api/generated');
const specFile = resolve(outDir, 'openapi.json');
const typesFile = resolve(outDir, 'schema.d.ts');

// ---------------------------------------------------------------------------
// Load .env.local if present
// ---------------------------------------------------------------------------
const envLocalPath = resolve(projectRoot, '.env.local');
if (existsSync(envLocalPath)) {
  const lines = readFileSync(envLocalPath, 'utf8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed
      .slice(eqIdx + 1)
      .trim()
      .replace(/^["']|["']$/g, '');
    if (!(key in process.env)) process.env[key] = val;
  }
  console.log('[generate-api] Loaded .env.local');
}

const API_URL = (process.env['API_URL'] ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
const email = process.env['API_ADMIN_EMAIL'];
const password = process.env['API_ADMIN_PASS'];

if (!email || !password) {
  console.error(
    '[generate-api] ERROR: API_ADMIN_EMAIL and API_ADMIN_PASS must be set.\n' +
      '  Set them in .env.local or as environment variables.',
  );
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Step 1 — Authenticate
// ---------------------------------------------------------------------------
console.log(`[generate-api] Authenticating with ${API_URL}/auth/get_token …`);

const loginRes = await fetch(`${API_URL}/auth/get_token`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password }),
});

if (!loginRes.ok) {
  const body = await loginRes.text();
  console.error(`[generate-api] Auth failed (${loginRes.status}): ${body}`);
  process.exit(1);
}

const { access_token: token } = await loginRes.json();
console.log('[generate-api] Authenticated successfully.');

// ---------------------------------------------------------------------------
// Step 2 — Fetch OpenAPI spec
// ---------------------------------------------------------------------------
console.log(`[generate-api] Fetching spec from ${API_URL}/openapi.json …`);

const specRes = await fetch(`${API_URL}/openapi.json`, {
  headers: { Authorization: `Bearer ${token}` },
});

if (!specRes.ok) {
  const body = await specRes.text();
  console.error(`[generate-api] Failed to fetch spec (${specRes.status}): ${body}`);
  process.exit(1);
}

const spec = await specRes.json();

// ---------------------------------------------------------------------------
// Step 3 — Save spec to disk
// ---------------------------------------------------------------------------
mkdirSync(outDir, { recursive: true });
writeFileSync(specFile, JSON.stringify(spec, null, 2), 'utf8');
console.log(`[generate-api] Spec saved → ${specFile}`);

// ---------------------------------------------------------------------------
// Step 4 — Generate TypeScript types with openapi-typescript
// ---------------------------------------------------------------------------
console.log('[generate-api] Generating TypeScript types …');

try {
  execSync(`yarn openapi-typescript "${specFile}" -o "${typesFile}"`, {
    cwd: projectRoot,
    stdio: 'inherit',
  });
  console.log(`[generate-api] Types generated → ${typesFile}`);
} catch (err) {
  console.error('[generate-api] openapi-typescript failed:', err.message);
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Step 5 — Write a barrel index so components can import cleanly
// ---------------------------------------------------------------------------
const indexFile = resolve(outDir, 'index.ts');
writeFileSync(
  indexFile,
  `// Auto-generated — do not edit by hand. Run: yarn generate:api\nexport type * from './schema';\n`,
  'utf8',
);

console.log('[generate-api] Done.');
