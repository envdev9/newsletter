import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/** HTML wyrenderowany PRAWDZIWYM SSR-em w osobnym procesie Node (`npm run ssr:check`). */
export function loadFixture(name: 'taken' | 'free' | 'taken-nocache'): string {
  const file = resolve(process.cwd(), 'dist/ssr/fixtures', `${name}.html`);
  if (!existsSync(file)) {
    throw new Error(`Brak ${file}. Najpierw: npm run ssr:build && npm run ssr:check (albo npm run verify).`);
  }
  return readFileSync(file, 'utf8');
}
