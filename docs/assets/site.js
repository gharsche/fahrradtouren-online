document.addEventListener('click',event=>{document.querySelectorAll('.nav-group[open]').forEach(menu=>{if(!menu.contains(event.target))menu.removeAttribute('open')})});
const form=document.querySelector('[data-search-form]');
if(form){form.addEventListener('submit',event=>{const input=form.querySelector('input[name="s"]');if(!input||!input.value.trim()){event.preventDefault();input?.focus()}})}
if(document.body.dataset.searchPage==='true'){
 const query=new URLSearchParams(location.search).get('s')||'';
 const input=document.querySelector('#search-query'); if(input)input.value=query;
 const status=document.querySelector('#search-status'); const results=document.querySelector('#search-results');
 if(query&&status&&results){fetch(window.SITE_BASE+'/assets/search-index.json').then(r=>r.json()).then(items=>{const q=query.toLocaleLowerCase('de');const found=items.filter(x=>(x.title+' '+x.text).toLocaleLowerCase('de').includes(q));status.textContent=found.length+' Treffer';for(const item of found){const box=document.createElement('article');box.className='search-result';const h=document.createElement('h2');const a=document.createElement('a');a.href=window.SITE_BASE+item.path;a.textContent=item.title;h.appendChild(a);const p=document.createElement('p');p.textContent=item.text.slice(0,260);box.append(h,p);results.appendChild(box)}if(!found.length)status.textContent='Keine Treffer';}).catch(()=>{status.textContent='Die Suche ist momentan nicht verfügbar.'})}
}
