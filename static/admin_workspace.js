/* Nova area restrita: dados reais, operacoes explicitas e nenhuma entrega. */
(() => {
  'use strict';
  const prefix = window.__BASE_PATH__ || '';
  const $ = id => document.getElementById(id);
  const csrf = document.querySelector('meta[name="csrf-token"]').content;
  const path = value => prefix + value;
  const create = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const date = value => value ? new Date(value).toLocaleString('pt-BR', {timeZone:'America/Sao_Paulo'}) : '—';
  const levels = ['Monitoramento', 'Observação', 'Atenção', 'Alerta', 'Alerta máximo'];
  let territory = [], territoryPage = 1, map, mapLayer, currentPanel;
  let institutions = [], alerts, alertCursor = null, alertStack = [], alertSequence = 0;
  let importPayload = null, importBusy = false;
  function message(text = '') { $('workspace-feedback').textContent = text; $('workspace-feedback').hidden = !text; }
  async function api(endpoint, options = {}) {
    const response = await fetch(path(endpoint), {credentials:'same-origin', ...options,
      headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf}});
    if (response.status === 401) { location.href = path('/admin/login'); throw new Error('Sessão expirada.'); }
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || 'Não foi possível concluir a operação.');
    return body;
  }
  function action(label, callback, cls='btn-secondary') { const b = create('button', label, cls); b.type='button'; b.onclick=callback; return b; }
  function table(host, headings, rows) {
    host.replaceChildren();
    const wrapper=create('div',undefined,'ws-table-wrap'), t=create('table',undefined,'ws-table');
    const head=create('thead'), tr=create('tr'); headings.forEach(h=>tr.append(create('th',h))); head.append(tr); t.append(head);
    const body=create('tbody');
    rows.forEach(cells=>{ const r=create('tr');cells.forEach(value=>{const cell=create('td');if(value instanceof Node) cell.append(value); else cell.textContent=value??'—';r.append(cell);});body.append(r); });
    if (!rows.length) { const r=create('tr'), cell=create('td','Nenhum registro encontrado.');cell.colSpan=headings.length;r.append(cell);body.append(r); }
    t.append(body);wrapper.append(t);host.append(wrapper);
  }
  function openTable(name, title, column, value, schema='hazardtrack') {
    const query=new URLSearchParams({esquema:schema,tabela:name,embedded:'1'});
    if (column && value) {query.set('column',column);query.set('value',value);}
    $('workspace-table-title').textContent=title;
    $('workspace-table-frame').src=path('/admin/tabelas?')+query;
    $('workspace-table-dialog').showModal();
  }
  function cards(id, entries) {
    $(id).replaceChildren();
    entries.forEach(([name,title,description,column,schema])=>{
      const card=create('article',undefined,'card ws-module-card');
      card.append(create('h2',title),create('p',description));
      card.append(action('Gerenciar',()=>openTable(name,title,column,$('institution-select')?.value,schema)));
      $(id).append(card);
    });
  }
  cards('operation-cards',[
    ['unidade_operacional','Unidades operacionais','Estrutura regional e unidades vinculadas à instituição.','instituicao_id'],
    ['interlocutor_institucional','Interlocutores','Vínculo com pessoas existentes no SIGMA.'],
    ['competencia_operacional','Competências','Natureza do risco, responsabilidade, papel e abrangência.','instituicao_id'],
    ['contato_operacional','Contatos operacionais','E-mail, telefone e endereço de integração da operação.','instituicao_id'],
    ['programa_operacional','Programas','Coordenação, vigência e organização das ações.','coordenacao_estadual_id'],
    ['programa_fase','Fases dos programas','Fases habilitadas para cada programa.'],
    ['abrangencia_operacional','Abrangências','Áreas de responsabilidade, versões e vigências.'],
    ['abrangencia_componente','Componentes territoriais','Rodovias e quilômetros, polígonos, municípios e referências.'],
    ['documento_referencia','Documentos de referência','Fonte oficial, vigência, revisão e arquivo do documento.'],
    ['competencia_referencia','Fontes das competências','Documentos que fundamentam as responsabilidades.'],
    ['abrangencia_referencia','Fontes das abrangências','Documentos que fundamentam as áreas de atendimento.'],
  ]);
  cards('integration-cards',[
    ['contato_operacional','Destinatários','Gerencie e-mails e números exclusivamente operacionais.'],
    ['regra_envio_alerta','Regras de comunicação','Critérios, intervalo de reenvio e inclusão de JSON.'],
    ['regra_envio_destino','Destinos das regras','Associe contatos às regras da mesma instituição.'],
    ['integracao_institucional','Integrações institucionais','Contrato, referência externa da credencial e situação.'],
    ['configuracao_envio','Autorização institucional','Chave preparatória auditada; envios do protótipo permanecem bloqueados.'],
  ]);
  cards('administration-cards',[
    ['auditoria_administrativa','Auditoria','Quem alterou, quando e quais valores foram modificados.'],
    ...[['natureza_risco','Naturezas de risco'],['responsabilidade_operacional','Responsabilidades operacionais'],['tipo_unidade_operacional','Tipos de unidade'],['tipo_abrangencia','Tipos de abrangência'],['papel_institucional','Papéis institucionais'],['fase_operacional','Fases operacionais'],['canal_envio','Canais de envio']].map(([n,t])=>[n,t,'Categorias extensíveis, com descrição e situação.',null,'dominios']),
  ]);
  $('workspace-table-close').onclick=()=>{$('workspace-table-dialog').close();$('workspace-table-frame').src='about:blank';};
  document.querySelectorAll('[data-table]').forEach(b=>b.onclick=()=>openTable(b.dataset.table,'Vincular instituição do SIGMA'));
  window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===$('workspace-table-frame').contentWindow&&e.data?.type==='hazardtrack:records-changed') loadOperation().catch(e=>message(e.message));});
  async function loadOperation() {
    const [summary,directory]=await Promise.all([api('/admin/api/workspace/summary'),api('/admin/api/workspace/institutions')]);
    const labels={instituicao_operadora:'Instituições',unidade_operacional:'Unidades',competencia_operacional:'Competências',contato_operacional:'Contatos',regra_envio_alerta:'Regras',documento_referencia:'Documentos'};
    $('operation-kpis').replaceChildren();
    Object.entries(labels).forEach(([key,label])=>{const item=create('article',undefined,'card ws-kpi');item.append(create('span',label),create('strong',summary.counts[key]));$('operation-kpis').append(item);});
    institutions=directory.items;const selected=$('institution-select').value;
    $('institution-select').replaceChildren(new Option('Todas as instituições',''));
    institutions.forEach(i=>$('institution-select').append(new Option(i.nome,i.id)));
    $('institution-select').value=selected; institutionSummary();
    if(directory.warning) message(directory.warning);
  }
  function institutionSummary(){const i=institutions.find(i=>String(i.id)===$('institution-select').value);$('institution-summary').textContent=i?`${i.nome} · ${i.unidades} unidade(s) · ${i.contatos} contato(s) · ${i.ativa?'Ativa':'Inativa'}`:'Selecione uma instituição para trabalhar com seus vínculos operacionais.';}
  $('institution-select').onchange=institutionSummary;
  $('institution-refresh').onclick=()=>loadOperation().catch(e=>message(e.message));
  async function loadTerritory() {
    const [geo,layers]=await Promise.all([api('/admin/api/workspace/territory'),api('/admin/api/workspace/layers')]);
    territory=geo.items;
    $('ua-options').replaceChildren();territory.forEach(u=>$('ua-options').append(new Option(`${u.sigla_rodovia} · ${u.municipio}`,u.ua_id)));
    table($('territory-layers'),['Camada','Grupo','Situação','Exportar'],layers.items.map(l=>{
      const link=create('a','Baixar GeoJSON','btn-secondary');link.href=l.download_url;link.setAttribute('download','');
      return [l.nome,l.grupo,l.disponivel?'Disponível':'Indisponível',l.disponivel?link:'Ainda não disponível'];
    }));
    renderTerritory();
  }
  function selectUA(u) {
    const labels={ua_id:'Unidade de análise',sigla_rodovia:'Rodovia',municipio:'Município',regiao_nome:'Região',km_inicial:'Quilômetro inicial',km_final:'Quilômetro final',RAGEO:'Risco estático geológico',RAHID:'Risco estático hidrológico',regional:'Regional',residencia_dr:'Residência de conservação',uba_nome:'Unidade de atendimento',conservado_por:'Conservado por',escala:'Escala',tipo:'Tipo'};
    table($('territory-detail'),['Atributo','Valor'],Object.entries(labels).map(([k,label])=>[label,u[k]]));
    if(map) map.setView([u.lat,u.lon],13);
  }
  function renderTerritory() {
    const term=$('territory-search').value.toLocaleLowerCase('pt-BR');
    const filtered=territory.filter(u=>`${u.ua_id} ${u.sigla_rodovia} ${u.municipio} ${u.regiao_nome}`.toLocaleLowerCase('pt-BR').includes(term));
    const pages=Math.max(1,Math.ceil(filtered.length/25));territoryPage=Math.min(territoryPage,pages);
    $('territory-count').textContent=`${filtered.length} UAs`;
    table($('territory-list'),['UA','Rodovia','Município','Quilômetros','RAGEO','RAHID'],filtered.slice((territoryPage-1)*25,territoryPage*25).map(u=>[action(u.ua_id,()=>selectUA(u),'ws-link'),u.sigla_rodovia,u.municipio,`${u.km_inicial} — ${u.km_final}`,u.RAGEO,u.RAHID]));
    const prev=action('Anterior',()=>{territoryPage--;renderTerritory();}),next=action('Próxima',()=>{territoryPage++;renderTerritory();});prev.disabled=territoryPage===1;next.disabled=territoryPage===pages;
    $('territory-pagination').replaceChildren(prev,create('span',`Página ${territoryPage} de ${pages}`),next);
    if(currentPanel!=='territorio'||!window.L) return;
    if(!map){map=L.map('territory-map').setView([-23.6,-45.7],9);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap',maxZoom:19}).addTo(map);mapLayer=L.layerGroup().addTo(map);}
    mapLayer.clearLayers();
    filtered.forEach(u=>{if(Array.isArray(u.geometry)){const line=L.polyline(u.geometry,{color:'#003b5a',weight:3}).on('click',()=>selectUA(u));line.bindTooltip(u.ua_id);line.addTo(mapLayer);}});
    map.invalidateSize();
  }
  $('territory-search').oninput=()=>{territoryPage=1;renderTerritory();};
  $('territory-export').onclick=()=>{location.href=path('/admin/api/workspace/territory/export');};
  $('layers-package').onclick=()=>{location.href=path('/admin/api/workspace/layers/geopackage/export');};
  $('territory-import').onclick=()=>{$('territory-import-dialog').showModal();};
  $('territory-import-cancel').onclick=()=>{if(!importBusy)$('territory-import-dialog').close();};
  $('territory-import-dialog').addEventListener('cancel',e=>{if(importBusy)e.preventDefault();});
  $('territory-import-form').oninput=()=>{importPayload=null;$('territory-confirm').disabled=true;};
  $('territory-import-form').onsubmit=async e=>{
    e.preventDefault();if(importBusy)return;importBusy=true;$('territory-validate').disabled=true;
    try{const form=e.currentTarget,file=form.elements.arquivo.files[0];if(!file||file.size>20_000_000)throw new Error('Selecione um GeoJSON de até 20 MB.');const candidate={geojson:JSON.parse(await file.text()),fonte:form.elements.fonte.value};const result=await api('/admin/api/workspace/territory/import',{method:'POST',body:JSON.stringify(candidate)});importPayload=candidate;$('territory-import-result').textContent=`${result.novas_uas} UA(s) válida(s). Confirme para incorporar ao monitoramento.`;$('territory-confirm').disabled=false;}catch(error){$('territory-import-result').textContent=error.message;}finally{importBusy=false;$('territory-validate').disabled=false;}
  };
  $('territory-confirm').onclick=async()=>{if(!importPayload||importBusy)return;importBusy=true;$('territory-confirm').disabled=true;try{const result=await api('/admin/api/workspace/territory/import',{method:'POST',body:JSON.stringify({...importPayload,confirmar:true})});$('territory-import-result').textContent=`Inclusão concluída: ${result.total} UAs. O próximo ciclo usará a malha atualizada.`;importPayload=null;await loadTerritory();}catch(e){$('territory-import-result').textContent=e.message;$('territory-confirm').disabled=false;}finally{importBusy=false;}};
  async function loadAlerts() {
    const seq=++alertSequence;
    const q=new URLSearchParams({limit:25});if(alertCursor)q.set('before',alertCursor);if($('alerts-ua').value)q.set('ua_id',$('alerts-ua').value.trim());if($('alerts-channel').value)q.set('channel',$('alerts-channel').value);
    const result=await api('/admin/api/alerts?'+q);if(seq!==alertSequence)return;alerts=result;
    table($('alerts-list'),['Alerta','UA','Natureza','Nível','Situação'],alerts.alerts.map(a=>[action('#'+a.id,()=>alertDetail(a),'ws-link'),a.ua_id,a.canal==='geo'?'Movimentos de massa':'Inundação',levels[a.rd_atual],a.encerrado_em?'Encerrado':'Aberto']));
    const prev=action('Mais recentes',()=>{alertCursor=alertStack.pop()||null;loadAlerts().catch(e=>message(e.message));}),next=action('Mais antigos',()=>{alertStack.push(alertCursor);alertCursor=alerts.next_before;loadAlerts().catch(e=>message(e.message));});prev.disabled=!alertStack.length;next.disabled=!alerts.next_before;
    $('alerts-pagination').replaceChildren(prev,create('span',`${alerts.alerts.length} episódio(s)`),next);
    $('alerts-detail').replaceChildren(create('p','Selecione um episódio.'));
  }
  function alertDetail(a) {
    const host=$('alerts-detail');host.replaceChildren(create('h3',`Alerta #${a.id} · ${a.ua_id}`),create('p',`Abertura: ${date(a.aberto_em)} · Atualização: ${date(a.atualizado_em)}`));
    const list=create('ol',undefined,'ws-timeline');
    const types={abertura:'Abertura',escalada:'Elevação do risco',reducao:'Redução do risco',encerramento:'Encerramento',sem_dados:'Sem dados',retomada:'Retomada'};
    alerts.events.filter(e=>e.alerta_id===a.id).forEach(e=>list.append(create('li',`${date(e.ocorrido_em)} · ${types[e.tipo]||e.tipo} · ${e.rd===null?'Sem dado':levels[e.rd]}`)));host.append(list);
    const notices=alerts.notifications.filter(n=>n.alerta_id===a.id);host.append(create('p',`${notices.length} notificação(ões) registrada(s).`));
    notices.forEach(n=>{const attempts=alerts.attempts.filter(t=>t.notificacao_id===n.id);host.append(create('p',`${n.transporte==='email'?'E-mail':'Integração HTTP'} · ${n.estado} · ${attempts.length} tentativa(s)`));attempts.forEach(t=>host.append(create('p',`${date(t.ocorrido_em)} · ${t.sucesso?'Entrega confirmada':'Falha de entrega'}${t.erro?' · '+t.erro:''}`)));});
    const link=create('a','Baixar alerta em JSON','btn-secondary');link.href=path(`/admin/api/workspace/alert/${a.id}/json`);host.append(link);
    const details=create('details'),summary=create('summary','Evidências do cálculo'),pre=create('pre',JSON.stringify(a.evidencia,null,2));details.append(summary,pre);host.append(details);
  }
  $('alerts-search').onclick=()=>{alertCursor=null;alertStack=[];loadAlerts().catch(e=>message(e.message));};
  function simulateLevels(){const fire=$('simulate-nature').value==='fire';$('simulate-level').replaceChildren();(fire?['Mínimo','Baixo','Médio','Alto','Crítico']:levels).forEach((label,i)=>$('simulate-level').append(new Option(label,i)));}
  $('simulate-nature').onchange=simulateLevels;simulateLevels();
  $('simulate-form').onsubmit=async e=>{e.preventDefault();const button=e.currentTarget.querySelector('button');button.disabled=true;try{const body=Object.fromEntries(new FormData(e.currentTarget));const result=await api('/admin/api/workspace/simulate',{method:'POST',body:JSON.stringify(body)});const host=$('simulate-result');host.replaceChildren(create('h3',`${result.destinatarios.length} regra(s) correspondente(s) · nenhum envio`));result.avisos.forEach(a=>host.append(create('p',a,'ws-note')));result.destinatarios.forEach(d=>{const card=create('article',undefined,'ws-simulation');card.append(create('h4',d.regra),create('p',`${d.unidade} · ${d.ativa?'Regra ativa':'Regra desativada'}`));d.contatos.forEach(c=>card.append(create('p',`${c.canal} · ${c.rotulo} · ${c.destino} · ${c.ativo&&c.vinculo_ativo?'Ativo':'Desativado'}`)));host.append(card);});const detail=create('details'),summary=create('summary','Prévia JSON'),pre=create('pre',JSON.stringify(result,null,2));detail.append(summary,pre);host.append(detail);}catch(error){message(error.message);}finally{button.disabled=false;}};
  async function integrations() {
    if(!territory.length)await loadTerritory();
    const phases=await api('/admin/api/workspace/options/dominios/fase_operacional');
    $('simulate-phase').replaceChildren(new Option('Sem fase específica',''));phases.items.forEach(p=>$('simulate-phase').append(new Option(p.nome,p.id)));
    $('integration-links').replaceChildren();
    [['Eventos de alerta (consulta incremental)','/api/public/alerts'],['Camadas geodinâmicas','/api/public/ua-layers'],['Risco de fogo','/api/public/fire-risk/snapshot']].forEach(([label,url])=>{const p=create('p'),a=create('a',label);a.href=path(url);a.target='_blank';a.rel='noopener';p.append(a,create('code',location.origin+path(url)));$('integration-links').append(p);});
  }
  async function administration(){const ctx=await api('/admin/api/auth/context');$('sigma-links').replaceChildren();Object.entries(ctx.sigma_links||{}).filter(([key])=>['cadastro_sigma','login_sigma'].includes(key)).forEach(([key,url])=>{const a=create('a',key==='cadastro_sigma'?'Cadastro no SIGMA':'Acessar SIGMA','btn-secondary');a.href=url;a.target='_blank';a.rel='noopener';$('sigma-links').append(a);});}
  document.addEventListener('hazardtrack:panel',async e=>{currentPanel=e.detail;message();try{if(currentPanel==='territorio')await loadTerritory();if(currentPanel==='alertas')await loadAlerts();if(currentPanel==='operacao')await loadOperation();if(currentPanel==='integracoes')await integrations();if(currentPanel==='administracao')await administration();if(['territorio','alertas','operacao','integracoes','administracao'].includes(currentPanel))$('updated-at').textContent='Atualizado '+new Date().toLocaleString('pt-BR');}catch(error){message(error.message);}});
  $('btn-refresh').addEventListener('click',()=>document.dispatchEvent(new CustomEvent('hazardtrack:panel',{detail:currentPanel})));
})();
