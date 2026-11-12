/* Administração tabular: dados e metadados reais; sem HTML vindo do banco. */
(() => {
  'use strict';
  const $ = id => document.getElementById(`db-${id}`);
  const base = document.body.dataset.api;
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const initial = new URLSearchParams(location.search);
  let tables = [], active = null, data = null, page = 1, sort = '', direction = 'asc';
  let controller, sequence = 0, busy = false, mutation = false, editing = null;
  const selected = new Set();
  const fields = [];
  const node = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  function feedback(message = '') {
    $('feedback').textContent = message;
    $('feedback').hidden = !message;
  }
  async function api(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'same-origin', ...options,
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(result.error || (response.status === 401
        ? 'Sua sessão expirou. Entre novamente.'
        : 'Não foi possível concluir a operação. Recarregue a página.'));
    }
    return result;
  }
  function address() {
    return `${base}/${encodeURIComponent(active.schema)}/${encodeURIComponent(active.name)}`;
  }
  function menu() {
    $('menu-list').replaceChildren();
    const term = $('search').value.toLocaleLowerCase('pt-BR');
    for (const t of tables) {
      if (!`${t.label} ${t.name} ${t.schema}`.toLocaleLowerCase('pt-BR').includes(term)) continue;
      const b = node('button', undefined, 'db-table-link');
      b.append(node('span', t.label), node('small', `${t.schema}.${t.name}`));
      b.title = `${t.label} — ${t.schema}.${t.name}`;
      if (active?.schema === t.schema && active?.name === t.name) b.setAttribute('aria-current', 'page');
      b.onclick = () => choose(t);
      $('menu-list').append(b);
    }
    if (!$('menu-list').children.length) $('menu-list').textContent = 'Nenhuma tabela encontrada.';
  }
  function choose(t, updateHistory = true) {
    if (mutation) return;
    if (updateHistory) { initial.delete('column'); initial.delete('value'); }
    active = t; data = null; page = 1; sort = ''; direction = 'asc';
    selected.clear(); clearFilter(false); menu();
    $('title').textContent = t.label;
    $('description').textContent = `${t.schema}.${t.name}`;
    $('head').replaceChildren(); $('body').replaceChildren();
    if (updateHistory) {
      const url = new URL(location.href);
      url.searchParams.set('esquema', t.schema); url.searchParams.set('tabela', t.name);
      history.pushState(null, '', url);
    }
    load();
  }
  function selection() {
    $('add').disabled = busy || !data?.writable;
    $('edit').disabled = busy || !data?.writable || selected.size !== 1;
    $('delete').disabled = busy || !data?.writable || !selected.size;
    $('reload').disabled = busy;
    $('counter').textContent = `${selected.size} selecionados / ${data?.rows.length || 0} na página / ${data?.total || 0} no total`;
    $('first').disabled = $('prev').disabled = busy || page <= 1;
    $('last').disabled = $('next').disabled = busy || page >= (data?.pages || 1);
    const boxes = $('body').querySelectorAll('input[type=checkbox]');
    boxes.forEach((b, i) => { b.checked = selected.has(i); b.closest('tr').classList.toggle('selected', b.checked); });
    const all = $('head').querySelector('input');
    if (all) {
      all.checked = boxes.length > 0 && selected.size === boxes.length;
      all.indeterminate = selected.size > 0 && selected.size < boxes.length;
    }
  }
  function render() {
    $('head').replaceChildren(); $('body').replaceChildren();
    const header = node('tr'), checkCell = node('th', undefined, 'db-select');
    const all = node('input'); all.type = 'checkbox'; all.setAttribute('aria-label', 'Selecionar todos os registros da página');
    all.onchange = () => { selected.clear(); if (all.checked) data.rows.forEach((_, i) => selected.add(i)); selection(); };
    checkCell.append(all); header.append(checkCell);
    for (const c of data.columns) {
      const th = node('th'); th.scope = 'col';
      th.setAttribute('aria-sort', sort === c.name ? (direction === 'asc' ? 'ascending' : 'descending') : 'none');
      const b = node('button', c.label);
      b.title = `Ordenar por ${c.label}`;
      b.onclick = () => { direction = sort === c.name && direction === 'asc' ? 'desc' : 'asc'; sort = c.name; page = 1; load(); };
      th.append(b, node('small', c.name)); header.append(th);
    }
    $('head').append(header);
    data.rows.forEach((row, index) => {
      const tr = node('tr'), cell = node('td', undefined, 'db-select'), box = node('input');
      box.type = 'checkbox'; box.setAttribute('aria-label', `Selecionar registro ${index + 1}`);
      box.onchange = () => { if (box.checked) selected.add(index); else selected.delete(index); selection(); };
      cell.append(box); tr.append(cell);
      for (const c of data.columns) {
        if ((row.__large_fields || []).includes(c.name)) {
          const td=node('td'),link=node('a','Abrir conteúdo completo');
          const params=new URLSearchParams({column:c.name,key:JSON.stringify(descriptor(index).key)});
          link.href=`${address()}/value?${params}`;link.target='_blank';link.rel='noopener';
          td.append(link);tr.append(td);continue;
        }
        const raw = row[c.name];
        let value = raw === null ? 'NULL' : c.udt === 'bool' ? (raw === 'true' ? 'Sim' : 'Não') : raw;
        if (raw && ['timestamp', 'timestamptz'].includes(c.udt)) {
          const parsed = new Date(raw);
          if (!Number.isNaN(parsed.getTime())) value = parsed.toLocaleString('pt-BR', {timeZone:'America/Sao_Paulo'});
        } else if (raw && c.udt === 'date') value = raw.split('-').reverse().join('/');
        const td = node('td', value, raw === null ? 'db-null' : '');
        td.title = `${c.label} (${c.name}): ${raw === null ? 'NULL' : raw}`;
        tr.append(td);
      }
      $('body').append(tr);
    });
    if (!data.rows.length) {
      const tr = node('tr'), td = node('td', 'Nenhum registro encontrado.');
      td.colSpan = data.columns.length + 1; tr.append(td); $('body').append(tr);
    }
    $('page').textContent = `Página ${data.page} de ${data.pages}`;
    selection();
  }
  async function load() {
    if (!active || mutation) return;
    controller?.abort(); controller = new AbortController();
    const current = ++sequence; busy = true; selected.clear(); selection(); feedback();
    $('content').setAttribute('aria-busy', 'true');
    const params = new URLSearchParams({page, sort, direction,
      column: data ? $('column').value : (initial.get('column') || ''),
      value: data ? $('value').value : (initial.get('value') || ''),
      empty: $('empty').checked ? '1' : '0', invert: $('invert').getAttribute('aria-pressed') === 'true' ? '1' : '0'});
    try {
      const result = await api(`${address()}?${params}`, {signal: controller.signal});
      if (current !== sequence) return;
      const first = !data; data = result; page = result.page;
      $('table-section').hidden = false;
      $('description').textContent = `${data.schema}.${data.name} · ${data.total} registro(s) · Chave primária: ${data.pk.join(', ') || 'não definida'}${data.read_only_reason ? ' · ' + data.read_only_reason : ''}`;
      if (first) {
        $('column').replaceChildren(new Option('— Coluna —', ''));
        data.columns.forEach(c => $('column').append(new Option(`${c.label} (${c.name})`, c.name)));
        if (initial.get('column')) {
          $('column').value = initial.get('column'); $('value').value = initial.get('value') || '';
          $('value').disabled = $('empty').disabled = !$('column').value;
        }
      }
      render();
    } catch (error) {
      if (current !== sequence) return;
      if (error.name !== 'AbortError') { feedback(error.message); data = null; $('table-section').hidden = true; }
    } finally {
      if (current === sequence) { busy = false; selection(); $('content').setAttribute('aria-busy', 'false'); }
    }
  }
  function clearFilter(reload = true) {
    $('column').value = ''; $('value').value = ''; $('empty').checked = false;
    $('value').disabled = $('empty').disabled = true;
    $('value').placeholder = 'Selecione a coluna'; $('invert').setAttribute('aria-pressed', 'false');
    page = 1; if (reload) load();
  }
  function descriptor(index) {
    const row = data.rows[index];
    return {key: Object.fromEntries(data.pk.map(k => [k, row[k]])), version: row.__version};
  }
  function editor(update) {
    if (busy || !data?.writable) return;
    editing = update ? [...selected][0] : null;
    const row = editing === null ? null : data.rows[editing];
    $('editor-title').textContent = `${update ? 'Editar registro' : 'Adicionar registro'} · ${data.label}`;
    $('editor-error').textContent = ''; $('fields').replaceChildren(); fields.length = 0;
    for (const c of data.columns) {
      if (c.generated || ['criado_em', 'atualizado_em', 'sigma_validado_em'].includes(c.name) || (update && c.pk)) continue;
      const field = node('div', undefined, 'db-field'), label = node('label', c.label);
      const input = node(c.udt === 'bool' ? 'select' : ['json', 'jsonb'].includes(c.udt) ? 'textarea' : 'input');
      input.id = `field-${c.name}`; label.htmlFor = input.id;
      if (c.udt === 'bool') input.append(new Option('Sim', 'true'), new Option('Não', 'false'));
      if (row && row[c.name] !== null) input.value = row[c.name];
      if (!row && c.name === initial.get('column')) input.value = initial.get('value') || '';
      const mode = node('select'); mode.setAttribute('aria-label', `Preenchimento de ${c.label}`);
      if (!update && c.default !== null) mode.append(new Option('Usar valor padrão', 'default'));
      mode.append(new Option('Informar valor', 'value'));
      if (c.nullable) mode.append(new Option('Sem valor (NULL)', 'null'));
      if (update) mode.value = row[c.name] === null ? 'null' : 'value';
      else if (!c.default && c.nullable) mode.value = 'null';
      if (!row && c.name === initial.get('column')) mode.value = 'value';
      function modeChanged() { input.disabled = mode.value !== 'value'; input.required = mode.value === 'value' && !c.nullable; }
      mode.onchange = modeChanged; modeChanged();
      field.append(label, node('small', `${c.name} · ${c.type}${c.pk ? ' · Chave primária' : ''}`), mode, input);
      const sigmaKind = c.name === 'sigma_instituicao_id' ? 'instituicao' : c.name === 'sigma_pessoa_id' ? 'pessoa' : null;
      if (sigmaKind || c.reference) {
        const lookup = node('div', undefined, 'db-lookup');
        const search = node('input'); search.placeholder = 'Buscar por nome'; search.setAttribute('aria-label', `Buscar ${c.label}`);
        const button = node('button', 'Buscar'); button.type = 'button';
        const results = node('select'); results.setAttribute('aria-label', `Resultados de ${c.label}`);
        results.append(new Option('Selecione um resultado', ''));
        button.onclick = async () => {
          button.disabled = true;
          try {
            const root = base.replace(/\/database$/, '/workspace');
            const route = sigmaKind ? `${root}/sigma/${sigmaKind}` : `${root}/options/${c.reference.schema}/${c.reference.table}`;
            const response = await api(`${route}?q=${encodeURIComponent(search.value)}`);
            results.replaceChildren(new Option(response.items.length ? 'Selecione um resultado' : 'Nenhum resultado', ''));
            response.items.forEach(item => results.append(new Option(`${item.nome} · ${item.id}`, item.id)));
          } catch (error) { $('editor-error').textContent = error.message; }
          finally { button.disabled = false; }
        };
        results.onchange = () => { if (results.value) { input.value = results.value; mode.value = 'value'; modeChanged(); } };
        lookup.append(search, button); field.append(lookup, results);
      }
      $('fields').append(field); fields.push({column: c, input, mode});
    }
    $('editor').showModal();
  }
  $('editor-form').onsubmit = async event => {
    event.preventDefault(); if (mutation) return;
    const values = {};
    try {
      for (const {column: c, input, mode} of fields) {
        if (mode.value === 'default') continue;
        let value = mode.value === 'null' ? null : input.value;
        if (value !== null && ['json', 'jsonb'].includes(c.udt)) {
          try { value = JSON.parse(value); } catch { throw new Error(`Informe um JSON válido em ${c.label}.`); }
        }
        if (editing !== null && mode.value === 'value' && input.value === data.rows[editing][c.name]) continue;
        if (editing !== null && value === null && data.rows[editing][c.name] === null) continue;
        values[c.name] = value;
      }
      if (!Object.keys(values).length) throw new Error('Nenhuma alteração foi informada.');
      mutation = true; $('save').disabled = true;
      const body = {values}; if (editing !== null) body.records = [descriptor(editing)];
      await api(address(), {method: editing === null ? 'POST' : 'PATCH', body: JSON.stringify(body)});
      $('editor').close(); mutation = false; await load(); feedback('Registro salvo com sucesso.');
      if (window.parent !== window) window.parent.postMessage({type:'hazardtrack:records-changed'}, location.origin);
    } catch (e) { $('editor-error').textContent = e.message; }
    finally { mutation = false; $('save').disabled = false; }
  };
  $('delete').onclick = () => {
    $('delete-message').textContent = `Confirma a exclusão de ${selected.size} registro(s) de ${data.label}? Registros vinculados podem impedir a exclusão.`;
    $('delete-error').textContent = ''; $('confirm').showModal();
  };
  $('delete-form').onsubmit = async event => {
    event.preventDefault(); if (mutation) return;
    mutation = true; $('delete-submit').disabled = true;
    try {
      await api(address(), {method: 'DELETE', body: JSON.stringify({records: [...selected].map(descriptor)})});
      $('confirm').close(); mutation = false; await load(); feedback('Registros excluídos com sucesso.');
      if (window.parent !== window) window.parent.postMessage({type:'hazardtrack:records-changed'}, location.origin);
    } catch (e) { $('delete-error').textContent = e.message; }
    finally { mutation = false; $('delete-submit').disabled = false; }
  };
  document.querySelectorAll('[data-close]').forEach(b => b.onclick = () => { if (!mutation) $('editor').close(); });
  $('delete-cancel').onclick = () => { if (!mutation) $('confirm').close(); };
  [$('editor'), $('confirm')].forEach(d => d.addEventListener('cancel', e => { if (mutation) e.preventDefault(); }));
  $('add').onclick = () => editor(false); $('edit').onclick = () => editor(true);
  $('reload').onclick = load; $('search').oninput = menu;
  $('filter').onsubmit = e => { e.preventDefault(); page = 1; load(); };
  $('column').onchange = () => {
    $('value').disabled = !$('column').value || $('empty').checked;
    $('empty').disabled = !$('column').value;
    $('value').placeholder = $('column').value ? 'Digite o valor e pressione Enter' : 'Selecione a coluna';
    $('value').value = ''; page = 1; load();
  };
  $('empty').onchange = () => { $('value').disabled = $('empty').checked; page = 1; load(); };
  $('invert').onclick = () => { $('invert').setAttribute('aria-pressed', $('invert').getAttribute('aria-pressed') !== 'true'); page = 1; load(); };
  $('clear').onclick = () => clearFilter();
  $('first').onclick = () => { page = 1; load(); };
  $('prev').onclick = () => { page--; load(); };
  $('next').onclick = () => { page++; load(); };
  $('last').onclick = () => { page = data.pages; load(); };
  $('sidebar-toggle').onclick = () => {
    const sidebar = document.getElementById('admin-sidebar');
    const open = sidebar.classList.toggle('open'); $('sidebar-toggle').setAttribute('aria-expanded', open);
  };
  function fromUrl() {
    const params = new URLSearchParams(location.search);
    const t = tables.find(t => t.schema === params.get('esquema') && t.name === params.get('tabela'));
    choose(t || tables[0], false);
  }
  window.addEventListener('popstate', fromUrl);
  api(base).then(result => {
    tables = result.tables.sort((a, b) => a.label.localeCompare(b.label, 'pt-BR'));
    $('table-count').textContent = tables.length;
    if (tables.length) fromUrl();
    else { feedback('Nenhuma tabela disponível.'); $('content').setAttribute('aria-busy', 'false'); }
  }).catch(e => { feedback(e.message); $('menu-list').textContent = 'Não foi possível carregar as tabelas.'; $('content').setAttribute('aria-busy', 'false'); });
})();
