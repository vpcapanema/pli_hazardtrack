const fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const base=process.env.HAZARDTRACK_SMOKE_BASE;
const raw=fs.readFileSync(process.env.HAZARDTRACK_E2E_CREDENTIALS,'utf8');
const value=k=>raw.match(new RegExp('^'+k+'\\s*:\\s*(.+)$','im'))[1].trim();
(async()=>{const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'});try{
 const c=await browser.newContext();const p=await c.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(base+'/admin/login');await p.locator('#login-user').fill(value('username'));await p.locator('#login-pass').fill(value('senha'));await p.locator('#login-profile').selectOption('ADMIN');await p.locator('button[type=submit]').click();await p.waitForURL(/\/admin\/central/);
 for(const s of ['visao','saude','territorio','alertas','operacao','integracoes','analytics','estatisticas','relatorios','administracao','controles','sistema']){const r=await p.goto(base+'/admin/central/'+s);assert.equal(r.status(),200);await p.locator('#panel-'+s+'.active').waitFor();}
 const catalog=await c.request.get(base+'/admin/api/database');assert.equal(catalog.status(),200);const data=await catalog.json();const tables=data.tables;assert.equal(tables.length,33);
 for(const t of tables){const r=await c.request.get(base+'/admin/api/database/'+t.schema+'/'+t.name+'?limit=1');assert.equal(r.status(),200,t.name+': '+await r.text());}
 const products=await (await c.request.get(base+'/admin/api/database/hazardtrack/produto_monitoramento')).json(); const large=products.rows.find(r=>(r.__large_fields||[]).includes('dados')); if(large){const q=new URLSearchParams({column:'dados',key:JSON.stringify({id:large.id})});const full=await c.request.get(base+'/admin/api/database/hazardtrack/produto_monitoramento/value?'+q);assert.equal(full.status(),200);JSON.parse(await full.text());console.log('Conteúdo histórico extenso: download integral validado.');} const territory=await c.request.get(base+'/admin/api/workspace/territory');assert.equal(territory.status(),200);console.log('UAs:',(await territory.json()).items.length);
 for(const route of ['/admin/api/workspace/summary','/admin/api/workspace/institutions','/admin/api/workspace/territory/export','/api/public/alerts','/admin/api/alerts','/admin/api/dashboard','/admin/api/analytics','/admin/api/alert-controls']){const r=await c.request.get(base+route);assert.equal(r.status(),200,route);if(route.endsWith('summary')){const d=await r.json();console.log('Resumo:',JSON.stringify(d));}}
 assert.deepEqual(errors,[]);console.log('VALIDADO: login real, 12 páginas, 33 tabelas e APIs. Nenhuma mutação cadastral ou envio.');
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
