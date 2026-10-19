// Wstrzykiwane na początek bundla: (1) require() dla zależności CJS (domino) w ESM,
// (2) kompilator Angulara do dolinkowania bibliotek w formie "partial".
import '@angular/compiler';
import { createRequire } from 'node:module';

globalThis.require ??= createRequire(import.meta.url);
