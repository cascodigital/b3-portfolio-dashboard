/* Valida o painel gerado sem precisar de browser.
 *
 *   node check.js painel-acoes.html
 *
 * Executa o <script> do painel num DOM mínimo (vm + shim) e reporta erro de
 * execução com stack, o HTML que cada bloco gerou e um teste de undefined/NaN
 * na saída. Um erro de JS no template deixa a tela em branco em silêncio —
 * rode isto antes de publicar. */
const fs = require('fs'), vm = require('vm');
const file = process.argv[2];
const html = fs.readFileSync(file, 'utf8');
const code = html.match(/<script>([\s\S]*)<\/script>/)[1];

const store = {};
function el(id) {
  if (store[id]) return store[id];
  const e = {
    id, innerHTML: '', textContent: '', className: '', outerHTML: '',
    style: {}, dataset: {},
    addEventListener() {}, closest() { return null; },
    getBoundingClientRect: () => ({ width: 100, height: 50 }),
  };
  return (store[id] = e);
}
const document = {
  getElementById: el,
  querySelector: (s) => el('q:' + s),
  querySelectorAll: () => [],
  createElement: () => el('tmp'),
  addEventListener() {},
};
const sandbox = {
  document, console,
  window: {}, innerWidth: 1920, innerHeight: 1080,
  location: { pathname: '/x', replace() {} },
  setInterval: () => 0, setTimeout: () => 0,
  Date, Math, JSON, Object, Array, Number, String, Intl,
};
sandbox.window = sandbox;
try {
  vm.runInNewContext(code, sandbox, { filename: 'painel.js' });
} catch (e) {
  console.error('ERRO DE EXECUCAO:', e.stack);
  process.exit(1);
}
const strip = (s) => s.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
for (const id of ['desk', 'wl', 'pv', 'expv', 'ibv', 'ibchart', 'movers', 'posPanel']) {
  const h = store[id] ? store[id].innerHTML : '';
  console.log(`\n### ${id} (${h.length} chars)\n` + strip(h).slice(0, 700));
}
console.log('\n### rs-ref:', store['rs-ref'] && store['rs-ref'].textContent);
console.log('### undefined/NaN no output:',
  ['desk', 'wl', 'pv', 'expv', 'ibv', 'ibchart', 'movers', 'posPanel']
    .filter((id) => /undefined|NaN/.test(store[id] ? store[id].innerHTML : '')) .join(', ') || 'nenhum');
