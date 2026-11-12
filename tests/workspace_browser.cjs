/* Aceitacao em ambiente isolado, navegador sem janela e sem perfil pessoal. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.HAZARDTRACK_TEST_BASE || 'http://127.0.0.1:15059';
if (!base.startsWith('http://127.0.0.1:15059')) throw Error('Teste de escrita restrito ao ambiente isolado.');
const credentials = fs.readFileSync(process.env.HAZARDTRACK_E2E_CREDENTIALS, 'utf8');
const value = key => credentials.match(new RegExp('^'+key+'\\s*:\\s*(.+)$','im'))?.[1].trim();
const out = process.env.HAZARDTRACK_E2E_OUTPUT;
fs.mkdirSync(out,{recursive:true});
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'});
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  const page=await context.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  try{
    await page.goto(base+'/admin/login');
    await page.locator('#login-user').fill(value('username'));
    await page.locator('#login-profile').selectOption('ADMIN');
    await page.locator('#login-pass').fill(value('senha'));
    await page.locator('button[type=submit]').click();
    await page.waitForURL(/\/admin\/central/,{timeout:30000});
    for(const section of ['visao','saude','territorio','alertas','operacao','integracoes','analytics','estatisticas','relatorios','administracao','controles','sistema']){
      await page.goto(base+'/admin/central/'+section);
      await page.locator('#panel-'+section+'.active').waitFor();
      assert.equal(await page.locator('.panel.active').count(),1);
      if(section==='territorio'){
        await page.locator('#territory-count').filter({hasText:/809/}).waitFor();
        await page.locator('#territory-search').fill('UA-R1-BER-10K-001');
        await page.locator('#territory-list button').first().click();
        assert.match(await page.locator('#territory-detail').innerText(),/Bertioga/);
        await page.screenshot({path:path.join(out,'territorio.png')});
      }
      if(section==='operacao'){
        await page.locator('#operation-kpis strong').first().waitFor();
        await page.locator('[data-table=instituicao_operadora]').click();
        const frame=page.frameLocator('#workspace-table-frame');
        await frame.locator('#db-title').filter({hasText:'Instituições operadoras'}).waitFor();
        await frame.locator('#db-add').click();
        await frame.locator('.db-lookup button').click();
        await frame.locator('.db-field select[aria-label^="Resultados"] option').nth(1).waitFor({state:'attached'});
        await page.locator('#workspace-table-close').click();
      }
      console.log('Página validada:',section);
    }
    // Exportação geográfica após o diagnóstico também verifica a convivência
    // das bibliotecas nativas de projeção e meteorologia no mesmo processo.
    for(const endpoint of ['/admin/api/workspace/territory/export','/api/public/alerts','/admin/api/reports/export?type=operacional','/admin/api/reports/export?type=alertas']){
      const response=await context.request.get(base+endpoint);
      assert.equal(response.status(),200,endpoint);
      assert.ok((await response.body()).length>0);
    }
    const token=await page.locator('meta[name=csrf-token]').getAttribute('content');
    const simulation=await context.request.post(base+'/admin/api/workspace/simulate',{
      headers:{'X-CSRF-Token':token},data:{ua_id:'UA-R1-BER-10K-001',natureza:'geo',nivel:3}
    });
    assert.equal(simulation.status(),200,await simulation.text());
    assert.equal((await simulation.json()).envios_realizados,0);
    await page.goto(base+'/admin/tabelas?esquema=dominios&tabela=natureza_risco');
    await page.locator('#db-table-count').filter({hasText:'33'}).waitFor();
    await page.locator('#db-add').click();
    const code='e2e_'+Date.now();
    await page.locator('#field-codigo').fill(code);
    await page.locator('#field-nome').fill('Teste isolado de interface');
    await page.locator('#db-save').click();
    await page.locator('#db-editor').waitFor({state:'hidden'});
    await page.locator('#db-column').selectOption('codigo');
    await page.waitForResponse(r=>r.url().includes('/dominios/natureza_risco?')&&r.request().method()==='GET');
    await page.locator('#db-value').fill(code);
    await page.locator('#db-value').press('Enter');
    await page.locator('#db-body tr').filter({hasText:code}).waitFor();
    await page.locator('#db-body input').first().check();
    await page.locator('#db-edit').click();
    await page.locator('#field-nome').fill('Teste revisado');
    await page.locator('#db-save').click();
    await page.locator('#db-editor').waitFor({state:'hidden'});
    await page.locator('#db-body tr').filter({hasText:'Teste revisado'}).waitFor();
    await page.screenshot({path:path.join(out,'tabelas.png')});
    await page.locator('#db-body input').first().check();
    await page.locator('#db-delete').click();
    await page.locator('#db-delete-submit').click();
    await page.locator('#db-confirm').waitFor({state:'hidden'});
    await page.locator('#db-body').filter({hasText:'Nenhum registro'}).waitFor();
    await page.setViewportSize({width:390,height:844});
    await page.goto(base+'/admin/central/operacao');
    await page.locator('#panel-operacao.active').waitFor();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2),true,'Sem rolagem horizontal no celular');
    await page.screenshot({path:path.join(out,'mobile.png')});
    assert.deepEqual(errors,[]);
    console.log('Login SIGMA, 12 páginas, busca geográfica, consulta SIGMA, cadastro/edição/exclusão e responsividade: OK.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
