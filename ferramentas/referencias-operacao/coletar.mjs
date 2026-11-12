import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
const root = path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, '$1'));
const sources = JSON.parse(await fs.readFile(path.join(root, 'fontes.json'), 'utf8'));
sources.push(...JSON.parse(await fs.readFile(path.join(root, 'fontes-complementares.json'), 'utf8')));
const out = path.join(root, 'coleta-2026-11-12');
await fs.mkdir(out, {recursive:true});
const manifest = [], links = [];
try {
 manifest.push(...JSON.parse(await fs.readFile(path.join(out,'manifesto.json'),'utf8')));
 links.push(...JSON.parse(await fs.readFile(path.join(out,'links-descobertos.json'),'utf8')));
} catch {}
for (let i=0;i<sources.length;i+=4) {
 await Promise.all(sources.slice(i,i+4).map(async s=>{
  if(manifest.some(r=>r.id===s.id)) return;
  const record={...s,consultado_em:new Date().toISOString()};
  try {
   const r=await fetch(s.url,{signal:AbortSignal.timeout(40000)});
   record.http_status=r.status; record.url_final=r.url;
   if(!r.ok) throw new Error('HTTP '+r.status);
   const b=Buffer.from(await r.arrayBuffer());
   const pdf=b.subarray(0,5).toString()==='%PDF-';
   const html=/text\/html/i.test(r.headers.get('content-type')||'');
   if(!pdf&&!html) throw new Error('Formato nao identificado');
   record.arquivo=s.id+(pdf?'.pdf':'.html');
   record.bytes=b.length; record.sha256=crypto.createHash('sha256').update(b).digest('hex');
   await fs.writeFile(path.join(out,record.arquivo),b);
   if(html){
    const text=b.toString('utf8');
    for(const m of text.matchAll(/<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi)){
     const label=m[2].replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
     if(/2026|2025|plano|portaria|resolu|\.pdf|contrato|anexo|unidade|regional|organograma|abrang/i.test(label+' '+m[1])){
      try{links.push({origem:s.id,titulo:label,url:new URL(m[1].replace(/&amp;/g,'&'),r.url).href});}catch{}
     }
    }
   }
   const blocked=html&&/Request unsuccessful|Incapsula incident|Access Denied/i.test(b.toString('utf8'));
   const wrongPdf=/\.pdf(?:\?|$)/i.test(s.url)&&!pdf;
   record.status=blocked?'bloqueado':wrongPdf?'conteudo_incorreto':'baixado';
   if(blocked||wrongPdf){
    await fs.mkdir(path.join(out,'falhas'),{recursive:true});
    await fs.rename(path.join(out,record.arquivo),path.join(out,'falhas',record.arquivo));
    record.arquivo='falhas/'+record.arquivo;
   }
  }catch(e){record.status='falha';record.erro=e.message;}
  manifest.push(record); console.log(s.id,record.status,record.bytes||record.erro);
 }));
}
await fs.writeFile(path.join(out,'manifesto.json'),JSON.stringify(manifest,null,2));
await fs.writeFile(path.join(out,'links-descobertos.json'),JSON.stringify(links,null,2));
