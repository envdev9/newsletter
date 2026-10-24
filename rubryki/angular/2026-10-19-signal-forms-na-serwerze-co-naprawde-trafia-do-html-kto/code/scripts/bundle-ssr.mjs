// Składa skompilowany przez ngc (AOT) kod SSR w jeden plik .mjs dla Node.
// Dlaczego własny bundle, a nie `ng build` z outputMode "server": builder Angulara 22 wymaga
// do wyciągania tras `module.registerHooks` (Node >= 22.15), a ta sesja miała Node 22.14.
// Jeden bundle = jedna kopia @angular/core w procesie (dwie kopie psują DI i adapter DOM).
import { build } from 'esbuild';

await build({
  entryPoints: ['out-tsc/ssr/ssr/render.js'],
  outfile: 'dist/ssr/render.mjs',
  bundle: true,
  platform: 'node',
  format: 'esm',
  target: 'node22',
  sourcemap: false,
  define: { ngServerMode: 'true' },
  // @angular/compiler: biblioteki Angulara są w npm w formie "partial" - bez linkera bundlera
  // trzeba je dolinkować w locie (JIT), a do tego potrzebny jest kompilator w runtime.
  inject: ['scripts/ssr-shim.mjs'],
});
console.log('dist/ssr/render.mjs gotowy');
