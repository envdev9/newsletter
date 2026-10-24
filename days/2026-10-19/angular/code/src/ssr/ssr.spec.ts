import { loadFixture } from './fixtures';

// Te testy czytają HTML wyrenderowany w osobnym procesie Node przez scripts/ssr-check.mjs.
// (Renderowania nie robimy w Vitest: runner wnosi własną platformę przeglądarkową i drugą
// kopię @angular/common, przez co platformServer dostaje zły adapter DOM.)
describe('HTML z renderApplication (fixtures z prawdziwego SSR)', () => {
  it('zawiera wartości szkicu jako atrybut value i atrybuty walidatorów', () => {
    const html = loadFixture('taken');
    expect(html).toMatch(/<input id="name"[^>]*required=""[^>]*value="Anna"/);
    expect(html).toMatch(/<input id="code"[^>]*required=""[^>]*value="TAKEN"/);
  });

  it('serwer poczekał na walidację asynchroniczną i wyrenderował błąd', () => {
    expect(loadFixture('taken')).toContain('<p class="error">Kod jest zajęty</p>');
    expect(loadFixture('free')).not.toContain('Kod jest zajęty');
  });

  it('HTML niesie znaczniki hydracji i stan do przeniesienia', () => {
    const html = loadFixture('taken');
    expect(html).toMatch(/<app-root[^>]* ngh="/);
    expect(html).toContain('<!--nghm-->');
    expect(html).toContain('"coupon-taken:TAKEN":true');
  });

  it('bez TransferState w HTML nie ma wyniku walidacji', () => {
    expect(loadFixture('taken-nocache')).not.toContain('coupon-taken');
  });

  it('efekty przeglądarkowe (afterNextRender) nie wykonały się na serwerze', () => {
    expect(loadFixture('taken')).toContain('<p id="mode">tylko HTML</p>');
  });
});
