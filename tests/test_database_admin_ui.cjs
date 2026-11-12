/* DOM isolado: nao abre navegador nem controla a tela do usuario.
 * JSDOM_MODULE deve apontar para uma instalacao de jsdom.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require(process.env.JSDOM_MODULE || 'jsdom');
const root = path.resolve(__dirname, '..');
let html = fs.readFileSync(path.join(root, 'templates/admin_tables.html'), 'utf8');
html = html.replace(/data-api="[^"]*"/, 'data-api="/admin/api/database"')
  .replace(/\{\{.*?\}\}/g, 'teste');
const columns = [
  {name: 'id', label: 'Identificador', type: 'bigint', udt: 'int8', pk: true, generated: true, nullable: false, default: null},
  {name: 'codigo', label: 'Código', type: 'text', udt: 'text', nullable: false, default: null},
  {name: 'nome', label: 'Nome', type: 'text', udt: 'text', nullable: false, default: null},
  {name: 'ativo', label: 'Ativo', type: 'boolean', udt: 'bool', nullable: false, default: 'true'},
];
const calls = [];
const table = {schema: 'dominios', name: 'natureza_risco', label: 'Naturezas de risco'};
const row = {id: '9007199254740993', codigo: 'teste', nome: '<img src=x onerror=alert(1)>', ativo: 'true', __version: '123'};
const dom = new JSDOM(html, {url: 'http://localhost/admin/tabelas', runScripts: 'outside-only'});
const w = dom.window;
w.HTMLDialogElement.prototype.showModal = function () { this.open = true; };
w.HTMLDialogElement.prototype.close = function () { this.open = false; };
w.fetch = async (url, options) => {
  calls.push({url: String(url), options});
  const data = String(url) === '/admin/api/database' ? {tables: [table]} : options.method
    ? {ok: true} : {...table, columns, pk: ['id'], writable: true, rows: [row], page: 1, pages: 2, total: 16};
  return {ok: true, json: async () => data};
};
w.eval(fs.readFileSync(path.join(root, 'static/admin_tables.js'), 'utf8'));
const tick = () => new Promise(resolve => setImmediate(resolve));
const $ = id => w.document.getElementById('db-' + id);
(async () => {
  await tick(); await tick();
  assert.equal($('title').textContent, 'Naturezas de risco');
  assert.equal($('head').querySelectorAll('th')[2].querySelector('button').textContent, 'Código');
  assert.equal($('head').querySelectorAll('th')[2].querySelector('small').textContent, 'codigo');
  assert.equal($('body').querySelector('img'), null, 'Dados devem ser texto, nunca HTML');
  assert.match($('body').textContent, /9007199254740993/);
  assert.equal($('edit').disabled, true);
  $('body').querySelector('input').click();
  assert.equal($('edit').disabled, false);
  $('edit').click();
  assert.equal($('editor').open, true);
  const name = w.document.getElementById('field-nome');
  name.value = 'Nome revisado';
  $('editor-form').dispatchEvent(new w.Event('submit', {cancelable: true}));
  await tick(); await tick();
  const patch = calls.find(c => c.options.method === 'PATCH');
  const payload = JSON.parse(patch.options.body);
  assert.equal(payload.records[0].key.id, '9007199254740993');
  assert.deepEqual(payload.values, {nome: 'Nome revisado'});
  assert.equal($('editor').open, false);
  $('column').value = 'codigo';
  $('column').dispatchEvent(new w.Event('change'));
  await tick(); await tick();
  $('value').value = '100%_';
  $('filter').dispatchEvent(new w.Event('submit', {cancelable: true}));
  await tick(); await tick();
  assert.equal(new URL(calls.at(-1).url, 'http://localhost').searchParams.get('value'), '100%_');
  $('clear').click(); await tick(); await tick();
  assert.equal($('value').disabled, true);
  assert.equal($('counter').textContent, '0 selecionados / 1 na página / 16 no total');
  assert.equal($('menu-list').querySelector('small').textContent, 'dominios.natureza_risco');
  console.log('DOM: aliases, XSS, precisão, seleção, edição e filtros verificados.');
  w.close();
})().catch(error => { console.error(error); w.close(); process.exitCode = 1; });
