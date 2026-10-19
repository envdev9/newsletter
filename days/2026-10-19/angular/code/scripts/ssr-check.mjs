// Prawdziwy SSR w czystym Node: renderApplication() z bundla zbudowanego przez `npm run ssr:build`.
// Sprawdza asercjami (node:assert) i drukuje linie MEASURE; zapisuje HTML do dist/ssr/fixtures,
// z których korzystają testy hydracji (jsdom) w `ng test`.
import assert from 'node:assert/strict';
import { mkdirSync, renameSync, writeFileSync } from 'node:fs';
import { AVAILABILITY_LATENCY_MS, DRAFT, USE_TRANSFER_STATE, render } from '../dist/ssr/render.mjs';

const outDir = new URL('../dist/ssr/fixtures/', import.meta.url);
mkdirSync(outDir, { recursive: true });
const save = (name, html) => {
  const tmp = new URL(`${name}.html.tmp`, outDir);
  writeFileSync(tmp, html);
  renameSync(tmp, new URL(`${name}.html`, outDir)); // atomowo - test nie zobaczy pół pliku
};
const measure = (name, value) => console.log(`MEASURE ${name}: ${JSON.stringify(value)}`);
const draft = (name, code) => ({ provide: DRAFT, useValue: { name, code } });
const stateOf = (html) => JSON.parse(/<script id="ng-state" type="application\/json">(.*?)<\/script>/s.exec(html)[1]);

// 1. Zajęty kod w szkicu: serwer czeka na walidację async i renderuje błąd.
const taken = await render();
save('taken', taken.html);
measure('taken', {
  serverRequests: taken.serverRequests,
  elapsedMs: taken.elapsedMs,
  hasErrorText: taken.html.includes('Kod jest zajęty'),
  mode: /id="mode">([^<]*)</.exec(taken.html)[1],
  transferState: stateOf(taken.html)['coupon-taken:TAKEN'],
  hydrationMarkers: /<app-root[^>]* ngh="/.test(taken.html),
  valueAttr: /id="code"[^>]*value="TAKEN"/.test(taken.html),
});
assert.deepEqual(taken.serverRequests, ['TAKEN']);
assert.ok(taken.html.includes('Kod jest zajęty'));
assert.equal(stateOf(taken.html)['coupon-taken:TAKEN'], true);
assert.ok(taken.elapsedMs >= 200, 'SSR musi poczekać na walidację async');

// 2. Wolny kod: brak błędu.
const free = await render([draft('Anna', 'FREE')]);
save('free', free.html);
measure('free', { serverRequests: free.serverRequests, hasErrorText: free.html.includes('Kod jest zajęty') });
assert.deepEqual(free.serverRequests, ['FREE']);
assert.ok(!free.html.includes('Kod jest zajęty'));

// 3. Bez TransferState: ten sam HTML, ale klient nie dostanie wyniku.
const noCache = await render([{ provide: USE_TRANSFER_STATE, useValue: false }]);
save('taken-nocache', noCache.html);
measure('no-transfer-state', { stateKeys: Object.keys(stateOf(noCache.html)).filter((k) => k.startsWith('coupon')) });
assert.ok(!('coupon-taken:TAKEN' in stateOf(noCache.html)));

// 4. SSR czeka na NAJWOLNIEJSZĄ walidację: opóźnienie backendu 800 ms = >= 800 ms renderu.
const slow = await render([{ provide: AVAILABILITY_LATENCY_MS, useValue: 800 }]);
measure('slow-backend', { elapsedMs: slow.elapsedMs, hasErrorText: slow.html.includes('Kod jest zajęty') });
assert.ok(slow.elapsedMs >= 800);
assert.ok(slow.html.includes('Kod jest zajęty'));

// 5. Pusty kod: żadnego zapytania, ale błąd `required` jest w HTML zanim ktokolwiek dotknął pola.
const empty = await render([draft('', '')]);
measure('empty-draft', {
  serverRequests: empty.serverRequests,
  errorParagraphs: (empty.html.match(/<p class="error"/g) ?? []).length,
  form: /<form>.*<\/form>/s.exec(empty.html)[0],
});
assert.deepEqual(empty.serverRequests, []);

// 6. Złośliwa wartość w szkicu: nie może wyjść jako znacznik.
const evil = await render([draft('"><script>alert(1)</script>', 'FREE')]);
const bodyWithoutState = evil.html.replace(/<script id="ng-state".*?<\/script>/s, '');
measure('xss', {
  rawScriptInBody: bodyWithoutState.includes('<script>alert(1)'),
  nameAttr: /id="name"[^>]*value="([^"]*)"/.exec(evil.html)?.[1],
});
assert.ok(!bodyWithoutState.includes('<script>alert(1)'));

// 7. Dwa równoległe rendery w jednym procesie: bez przecieku stanu.
const [a, b] = await Promise.all([
  render([draft('Ala', 'TAKEN')]),
  render([draft('Bob', 'FREE')]),
]);
measure('parallel', {
  a: { hasAla: a.html.includes('value="Ala"'), hasBob: a.html.includes('value="Bob"'), requests: a.serverRequests },
  b: { hasAla: b.html.includes('value="Ala"'), hasBob: b.html.includes('value="Bob"'), requests: b.serverRequests },
});
assert.ok(a.html.includes('value="Ala"') && !a.html.includes('value="Bob"'));
assert.ok(b.html.includes('value="Bob"') && !b.html.includes('value="Ala"'));
assert.deepEqual(a.serverRequests, ['TAKEN']);
assert.deepEqual(b.serverRequests, ['FREE']);

// 8. Atrybut name pola pochodzi z globalnego licznika formularzy w procesie (ng.formN.pole):
//    ten sam formularz w kolejnych żądaniach dostaje kolejne numery.
const nameOf = (html) => /id="code" name="([^"]*)"/.exec(html)[1];
const names = [taken, free, noCache, slow, empty, evil, a, b].map((r) => nameOf(r.html));
measure('name-counter', names);
assert.notEqual(names[0], names[names.length - 1]);

console.log('ssr-check: wszystkie asercje przeszły');
