let conversationId=null;
let isSending=false;
let isGeneratingImage=false;
const $=id=>document.getElementById(id);
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600)}
async function api(url,opts={}){const res=await fetch(url,{...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(opts.headers||{})},credentials:'same-origin'});let data={};try{data=await res.json()}catch{}if(!res.ok)throw new Error(data.detail||'Erro na solicitação');return data}
function showTab(tab){const page=$('tab-'+tab);if(!page)return;document.querySelectorAll('.tab-page').forEach(x=>x.classList.remove('active'));page.classList.add('active');document.querySelectorAll('.nav-item').forEach(x=>{const active=x.dataset.tab===tab;x.classList.toggle('active',active);x.setAttribute('aria-current',active?'page':'false')});if(tab==='files')loadFiles();if(tab==='settings')loadMemories();if(tab==='chat')loadConversations()}
function bubble(role,text){const el=document.createElement('div');el.className='bubble '+role;el.textContent=text;$('messages').appendChild(el);$('messages').scrollTop=$('messages').scrollHeight;return el}
function resetChat(){conversationId=null;$('messages').innerHTML='<div class="welcome-msg">Sua próxima ideia começa aqui.<br><small>Descreva o que você quer programar.</small></div>'}
async function newConversation(){try{const c=await api('/api/conversations',{method:'POST'});conversationId=c.id;resetChat();conversationId=c.id;await loadConversations();toast('Nova conversa criada')}catch(e){toast('Não foi possível criar a conversa: '+e.message)}}
async function loadConversations(){const list=$('conversationList');try{const rows=await api('/api/conversations');list.innerHTML='';if(!rows.length){list.textContent='Nenhuma conversa criada ainda.';return}rows.forEach(c=>{const b=document.createElement('button');b.type='button';b.className='list-item conversation-item'+(Number(c.id)===Number(conversationId)?' selected':'');b.textContent=c.title||'Nova conversa';b.setAttribute('aria-label','Abrir conversa '+(c.title||c.id));b.setAttribute('aria-current',Number(c.id)===Number(conversationId)?'true':'false');b.onclick=()=>openConversation(Number(c.id));list.append(b)})}catch(e){list.textContent='Não foi possível carregar o histórico.';toast(e.message)}}
async function openConversation(id){if(!Number.isInteger(Number(id))||Number(id)<1){toast('Identificador de conversa inválido.');return}showTab('chat');conversationId=Number(id);const messages=$('messages');messages.innerHTML='<div class="welcome-msg">Abrindo conversa...</div>';try{const c=await api('/api/conversations/'+Number(id));if(!c||Number(c.id)!==Number(id)||!Array.isArray(c.messages))throw new Error('O servidor retornou uma conversa inválida.');conversationId=c.id;messages.innerHTML='';if(!c.messages.length){messages.innerHTML='<div class="welcome-msg">Conversa vazia. Envie sua primeira mensagem.</div>'}else{c.messages.forEach(m=>bubble(m.role==='assistant'?'assistant':'user',String(m.content??'')))}await loadConversations();messages.scrollTop=messages.scrollHeight}catch(e){conversationId=null;messages.innerHTML='<div class="welcome-msg">Não foi possível abrir esta conversa. Tente novamente.</div>';toast('Não foi possível abrir a conversa: '+e.message)}}
async function send(){const input=$('prompt');const text=input.value.trim();if(!text||isSending)return;isSending=true;input.value='';input.disabled=true;$('sendBtn').disabled=true;if($('messages').querySelector('.welcome-msg'))$('messages').innerHTML='';bubble('user',text);const wait=bubble('assistant','Mikael AI está analisando...');try{const d=await api('/api/chat',{method:'POST',body:JSON.stringify({message:text,conversation_id:conversationId})});conversationId=d.conversation_id;wait.textContent=d.reply||'A IA não retornou uma resposta.';await loadConversations()}catch(e){wait.textContent='Erro: '+e.message;toast(e.message)}finally{isSending=false;input.disabled=false;$('sendBtn').disabled=false;input.focus()}}
async function loadFiles(){try{const rows=await api('/api/files');$('fileList').innerHTML='';if(!rows.length){$('fileList').textContent='Nenhum arquivo enviado ainda.';return}rows.forEach(f=>{const el=document.createElement('div');el.className='list-item file-item';if(f.is_image){const img=document.createElement('img');img.className='file-thumb';img.alt='Prévia de '+f.filename;img.loading='lazy';img.src='/api/files/'+f.id+'/preview';el.append(img)}const info=document.createElement('div');info.className='file-info';const title=document.createElement('span');title.textContent=(f.is_image?'Foto · ':'')+f.filename+' · '+f.characters+' caracteres';info.append(title);const actions=document.createElement('div');actions.className='file-actions';const download=document.createElement('button');download.textContent='Baixar';download.onclick=()=>{location.href='/api/files/'+f.id+'/download'};const b=document.createElement('button');b.textContent=f.is_image?'Analisar foto':'Analisar';b.onclick=async()=>{b.disabled=true;b.textContent='Analisando...';try{const r=await api('/api/files/'+f.id+'/analyze',{method:'POST'});showTab('chat');resetChat();bubble('assistant',r.analysis)}catch(e){toast(e.message)}finally{b.disabled=false;b.textContent=f.is_image?'Analisar foto':'Analisar'}};actions.append(download,b);el.append(info,actions);$('fileList').append(el)})}catch(e){toast(e.message)}}
async function generateFile(){const filename=$('newFileName').value.trim();const description=$('newFileDescription').value.trim();if(!filename||!description){toast('Informe o nome e descreva o arquivo.');return}const button=$('generateFile');button.disabled=true;button.textContent='Gerando...';try{const result=await api('/api/files/generate',{method:'POST',body:JSON.stringify({filename,description})});$('newFileName').value='';$('newFileDescription').value='';toast('Arquivo criado: '+result.filename);await loadFiles()}catch(e){toast(e.message)}finally{button.disabled=false;button.textContent='Gerar arquivo'}}
async function loadMemories(){const list=$('memoryList');try{const rows=await api('/api/memories');list.innerHTML='';if(!rows.length){list.textContent='Nenhuma memória salva ainda.';return}rows.forEach(m=>{const el=document.createElement('div');el.className='list-item';const t=document.createElement('span');t.textContent=m.content;const b=document.createElement('button');b.type='button';b.textContent='Excluir';b.onclick=async()=>{b.disabled=true;try{await api('/api/memories/'+m.id,{method:'DELETE'});await loadMemories();toast('Memória excluída')}catch(e){toast('Não foi possível excluir: '+e.message);b.disabled=false}};el.append(t,b);list.append(el)})}catch(e){list.textContent='Não foi possível carregar as memórias.';toast(e.message)}}
async function boot(){try{await api('/api/me');$('login').classList.add('hidden');$('app').classList.remove('hidden')}catch{$('login').classList.remove('hidden')}}
$('loginBtn').onclick=async()=>{try{await api('/api/login',{method:'POST',body:JSON.stringify({password:$('password').value})});boot()}catch(e){$('loginError').textContent=e.message}};
$('password').addEventListener('keydown',e=>{if(e.key==='Enter')$('loginBtn').click()});
$('logoutBtn').onclick=async()=>{try{await api('/api/logout',{method:'POST'});location.reload()}catch(e){toast(e.message)}};
document.querySelectorAll('.nav-item').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
async function generateChatImage(){
  const input=$('prompt');
  const prompt=input.value.trim();
  if(prompt.length<5){toast('Descreva a imagem com pelo menos 5 caracteres.');input.focus();return}
  if(isSending||isGeneratingImage)return;
  isGeneratingImage=true;
  const button=$('imageGenBtn');
  button.disabled=true;
  $('sendBtn').disabled=true;
  $('attachBtn').disabled=true;
  input.disabled=true;
  input.value='';
  const messages=$('messages');
  if(messages.querySelector('.welcome-msg'))messages.innerHTML='';
  bubble('user','✧ Gerar imagem: '+prompt);
  const status=bubble('assistant','Criando sua imagem... isso pode levar alguns instantes.');
  try{
    const result=await api('/api/images/generate',{method:'POST',body:JSON.stringify({prompt})});
    status.textContent=result.message||'Imagem criada com sucesso.';
    const imageBubble=document.createElement('div');
    imageBubble.className='bubble assistant generated-image-bubble';
    const img=document.createElement('img');
    img.src=result.image_data_url;
    img.alt='Imagem gerada pela Mikael AI';
    img.loading='lazy';
    const actions=document.createElement('div');
    actions.className='generated-image-actions';
    const download=document.createElement('a');
    download.href='/api/files/'+result.file_id+'/download';
    download.textContent='Baixar imagem';
    download.setAttribute('download',result.filename);
    actions.append(download);
    imageBubble.append(img,actions);
    messages.append(imageBubble);
    messages.scrollTop=messages.scrollHeight;
    await loadFiles();
    toast('Imagem gerada e salva em Arquivos.');
  }catch(error){
    status.textContent='Não foi possível gerar a imagem: '+error.message;
    toast(error.message);
  }finally{
    isGeneratingImage=false;
    button.disabled=false;
    $('sendBtn').disabled=false;
    $('attachBtn').disabled=false;
    input.disabled=false;
    input.focus();
  }
}
async function handleChatFiles(event){
  const selected=Array.from(event.target.files||[]);
  event.target.value='';
  if(!selected.length)return;
  if(selected.length>10){toast('Envie no máximo 10 arquivos por vez.');return}
  showTab('chat');
  const messages=$('messages');
  if(messages.querySelector('.welcome-msg'))messages.innerHTML='';
  bubble('user','📎 Enviando '+selected.length+' arquivo(s)/imagem(ns) para análise: '+selected.map(f=>f.name).join(', '));
  for(const file of selected){
    const status=bubble('assistant','Recebendo '+file.name+'...');
    try{
      const form=new FormData();form.append('file',file);
      const uploaded=await api('/api/upload',{method:'POST',body:form});
      status.textContent='Analisando '+uploaded.filename+'...';
      const result=await api('/api/files/'+uploaded.id+'/analyze',{method:'POST'});
      status.textContent='Análise de '+uploaded.filename+':\\n\\n'+(result.analysis||'A IA não retornou uma análise.');
    }catch(error){
      status.textContent='Não foi possível analisar '+file.name+': '+error.message;
    }
  }
  await loadFiles();
}
$('sendBtn').onclick=send;$('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
$('attachBtn').onclick=()=>{if(!isSending&&!isGeneratingImage)$('chatFileInput').click()};
$('imageGenBtn').onclick=generateChatImage;
$('chatFileInput').onchange=handleChatFiles;
$('newChat').onclick=newConversation;$('startChat').onclick=()=>{showTab('chat');newConversation();$('prompt').focus()};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{showTab('chat');resetChat();$('prompt').value=b.dataset.prompt;$('prompt').focus()});
$('generateFile').onclick=generateFile;$('fileInput').onchange=async e=>{const selected=Array.from(e.target.files||[]);if(!selected.length)return;if(selected.length>10){toast('Envie no máximo 10 arquivos por vez.');e.target.value='';return}let sent=0;const errors=[];for(const file of selected){const form=new FormData();form.append('file',file);try{await api('/api/upload',{method:'POST',body:form});sent++}catch(err){errors.push(file.name+': '+err.message)}}e.target.value='';await loadFiles();if(errors.length)toast(sent+' enviado(s). Falhas: '+errors.slice(0,2).join(' | '));else toast(sent+' arquivo(s)/foto(s) enviado(s) com sucesso')};
$('saveMemory').onclick=async()=>{const content=$('memoryText').value.trim();if(!content)return;try{await api('/api/memories',{method:'POST',body:JSON.stringify({content,category:'projeto'})});$('memoryText').value='';toast('Memória salva');loadMemories()}catch(e){toast(e.message)}};
boot();
