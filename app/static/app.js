let conversationId=null;
let conversationViewRequest=0;
let isSending=false;
let isGeneratingImage=false;
let selectedModel="mikael";
let approvalResolver=null;
let pendingQueue=Promise.resolve();
let conversationRows=[];
let speakProgressEnabled=false;
const $=id=>document.getElementById(id);
function toast(msg){const t=$('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600)}
function confirmInApp(title,description,allowLabel='Permitir',denyLabel='Negar'){
  return new Promise(resolve=>{
    if(approvalResolver)approvalResolver(false);
    approvalResolver=resolve;
    $('approvalTitle').textContent=title;
    $('approvalDescription').textContent=description;
    $('approvalAllow').textContent=allowLabel;
    $('approvalDeny').textContent=denyLabel;
    $('approvalModal').classList.remove('hidden');
    $('approvalAllow').focus();
  });
}
function closeApproval(allowed){
  if(!approvalResolver)return;
  const resolve=approvalResolver;approvalResolver=null;
  $('approvalModal').classList.add('hidden');
  resolve(Boolean(allowed));
}
async function handlePendingApproval(action){
  const approved=await confirmInApp(action.title||'Excluir arquivo?',action.description||'A Mikael AI solicitou uma exclusão no GitHub.','Permitir exclusão','Negar');
  try{
    if(approved){
      const result=await api('/api/actions/'+Number(action.id)+'/approve',{method:'POST'});
      toast(result.message||'Ação aprovada e concluída.');
    }else{
      await api('/api/actions/'+Number(action.id)+'/deny',{method:'POST'});
      toast('Exclusão negada. Nada foi apagado.');
    }
  }catch(error){toast('Não foi possível resolver a solicitação: '+error.message)}
}
function queuePendingApprovals(actions){
  if(!Array.isArray(actions)||!actions.length)return;
  pendingQueue=pendingQueue.then(async()=>{
    for(const action of actions){
      if(Number.isInteger(Number(action.id)))await handlePendingApproval(action);
    }
  }).catch(error=>toast(error.message));
}
async function loadPendingApprovals(){
  try{const actions=await api('/api/actions/pending');queuePendingApprovals(actions)}catch(error){toast('Não foi possível verificar ações pendentes: '+error.message)}
}
async function api(url,opts={}){const res=await fetch(url,{...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(opts.headers||{})},credentials:'same-origin'});let data={};try{data=await res.json()}catch{}if(!res.ok)throw new Error(data.detail||'Erro na solicitação');return data}
function showTab(tab){const page=$('tab-'+tab);if(!page)return;document.querySelectorAll('.tab-page').forEach(x=>x.classList.remove('active'));page.classList.add('active');document.querySelectorAll('.nav-item').forEach(x=>{const active=x.dataset.tab===tab;x.classList.toggle('active',active);x.setAttribute('aria-current',active?'page':'false')});if(tab==='files')loadFiles();if(tab==='settings'){loadMemories();loadConnectors();}if(tab==='chat')loadConversations()}
function bubble(role,text){const el=document.createElement('div');el.className='bubble '+role;el.textContent=text;$('messages').appendChild(el);$('messages').scrollTop=$('messages').scrollHeight;return el}
function resetChat(){conversationViewRequest++;conversationId=null;$('currentConversationLabel').textContent='Nenhuma conversa selecionada';$('messages').innerHTML='<div class="welcome-msg">Sua próxima ideia começa aqui.<br><small>Descreva o que você quer programar.</small></div>'}
async function newConversation(){try{const c=await api('/api/conversations',{method:'POST'});resetChat();conversationId=c.id;$('currentConversationLabel').textContent='Conversa atual: '+(c.title||'Nova conversa');await loadConversations();toast('Nova conversa criada')}catch(e){toast('Não foi possível criar a conversa: '+e.message)}}
function renderConversations(){
  const list=$('conversationList');
  const query=($('conversationSearch')?.value||'').trim().toLocaleLowerCase('pt-BR');
  const rows=conversationRows.filter(item=>(item.title||'Nova conversa').toLocaleLowerCase('pt-BR').includes(query));
  list.innerHTML='';
  $('conversationCount').textContent=rows.length+' conversa(s)';
  if(!rows.length){list.textContent=query?'Nenhuma conversa corresponde à pesquisa.':'Nenhuma conversa criada ainda.';return}
  const now=new Date();
  const groups=[{label:'Hoje',items:[]},{label:'Últimos 7 dias',items:[]},{label:'Anteriores',items:[]}];
  rows.forEach(item=>{
    const date=item.created_at?new Date(item.created_at):null;
    const age=date&&!Number.isNaN(date.getTime())?(now-date)/86400000:99;
    groups[age<1?0:age<7?1:2].items.push(item);
  });
  groups.forEach(group=>{
    if(!group.items.length)return;
    const heading=document.createElement('div');heading.className='conversation-group-title';heading.textContent=group.label;list.append(heading);
    group.items.forEach(item=>{
      const b=document.createElement('button');b.type='button';
      b.className='list-item conversation-item'+(Number(item.id)===Number(conversationId)?' selected':'');
      b.setAttribute('aria-label','Abrir conversa '+(item.title||item.id));
      b.setAttribute('aria-current',Number(item.id)===Number(conversationId)?'true':'false');
      const content=document.createElement('span');content.className='conversation-item-content';
      const title=document.createElement('b');title.textContent=item.title||'Nova conversa';
      const date=document.createElement('small');date.textContent=item.created_at?new Date(item.created_at).toLocaleDateString('pt-BR',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'';
      content.append(title,date);b.append(content);
      const arrow=document.createElement('span');arrow.className='conversation-arrow';arrow.textContent='›';b.append(arrow);
      b.onclick=()=>openConversation(Number(item.id));list.append(b);
    });
  });
}
async function loadConversations(){
  try{conversationRows=await api('/api/conversations');renderConversations()}
  catch(e){$('conversationList').textContent='Não foi possível carregar o histórico.';toast(e.message)}
}
async function openConversation(id){if(!Number.isInteger(Number(id))||Number(id)<1){toast('Identificador de conversa inválido.');return}showTab('chat');const requestId=++conversationViewRequest;conversationId=Number(id);const messages=$('messages');messages.innerHTML='<div class="welcome-msg">Abrindo conversa...</div>';try{const c=await api('/api/conversations/'+Number(id));if(requestId!==conversationViewRequest)return;if(!c||Number(c.id)!==Number(id)||!Array.isArray(c.messages))throw new Error('O servidor retornou uma conversa inválida.');conversationId=c.id;$('currentConversationLabel').textContent='Conversa atual: '+(c.title||'Sem título');messages.innerHTML='';if(!c.messages.length){messages.innerHTML='<div class="welcome-msg">Conversa vazia. Envie sua primeira mensagem.</div>'}else{c.messages.forEach(m=>bubble(m.role==='assistant'?'assistant':'user',String(m.content??'')))}await loadConversations();messages.scrollTop=messages.scrollHeight}catch(e){if(requestId!==conversationViewRequest)return;conversationId=null;messages.innerHTML='<div class="welcome-msg">Não foi possível abrir esta conversa. Tente novamente.</div>';toast('Não foi possível abrir a conversa: '+e.message)}}
function announceProgress(message){
  const checkbox=$('speakProgress');
  if(!checkbox||!checkbox.checked||!('speechSynthesis' in window)||!('SpeechSynthesisUtterance' in window))return;
  try{
    const utterance=new SpeechSynthesisUtterance(message);
    utterance.lang='pt-BR';utterance.rate=1.02;utterance.pitch=1;
    window.speechSynthesis.speak(utterance);
  }catch{}
}

let activeWorkTask=null;
let workPollTimer=null;
let workPollBusy=false;
let workStatusReceivedAt=0;
function formatWorkTime(seconds){
  const value=Math.max(0,Math.floor(seconds||0));
  const h=Math.floor(value/3600),m=Math.floor((value%3600)/60),sec=value%60;
  return h?h+'h '+String(m).padStart(2,'0')+'m':m?m+'m '+String(sec).padStart(2,'0')+'s':sec+'s';
}
function renderLongWork(task){
  activeWorkTask=task;
  const panel=$('longWorkStatus');
  if(!task){panel.classList.add('hidden');return}
  panel.classList.remove('hidden');
  const labels={running:'Trabalho em andamento',paused:'Trabalho pausado',completed:'Projeto entregue',cancelled:'Trabalho cancelado'};
  $('longWorkState').textContent=labels[task.status]||'Tarefa salva';
  $('longWorkProgress').textContent=task.progress||'Aguardando atualização...';
  const remaining=Math.max(0,Number(task.remaining_seconds)||0);
  $('longWorkTime').textContent='Tempo restante: '+formatWorkTime(task.status==='running'?remaining-Math.floor((Date.now()-workStatusReceivedAt)/1000):remaining);
  $('pauseLongWork').disabled=task.status!=='running';
  $('resumeLongWork').disabled=task.status!=='paused';
  $('cancelLongWork').disabled=['completed','cancelled'].includes(task.status);
}
async function refreshLongWork(){
  if(workPollBusy)return;
  workPollBusy=true;
  try{
    const task=await api('/api/work/current');
    if(task){
      const changed=!activeWorkTask||activeWorkTask.status!==task.status||Number(activeWorkTask.remaining_seconds)!==Number(task.remaining_seconds);
      if(changed)workStatusReceivedAt=Date.now();
      renderLongWork(task);
    }else renderLongWork(null);
  }catch(error){console.warn('Não foi possível atualizar a tarefa:',error.message)}
  finally{workPollBusy=false}
}
async function startLongWork(goal,duration){
  const clean=String(goal||'').trim();
  if(clean.length<5){toast('Descreva o projeto antes de iniciar.');return}
  const button=$('startLongWork');button.disabled=true;
  try{
    const task=await api('/api/work/start',{method:'POST',body:JSON.stringify({
      goal:clean,duration_seconds:Math.min(10800,Math.max(60,Number(duration)||10800)),
      conversation_id:conversationId,model_id:selectedModel
    })});
    conversationId=task.conversation_id;
    $('workGoal').value='';
    $('currentConversationLabel').textContent='Conversa atual: trabalho prolongado';
    workStatusReceivedAt=Date.now();renderLongWork(task);
    await loadConversations();
    await openConversation(task.conversation_id);
    toast('Trabalho iniciado. Você pode minimizar o navegador; ative as notificações para receber avisos.');
  }catch(error){toast('Não foi possível iniciar: '+error.message)}
  finally{button.disabled=false}
}
async function pauseLongWork(){
  if(!activeWorkTask)return;
  try{const task=await api('/api/work/'+activeWorkTask.id+'/pause',{method:'POST'});workStatusReceivedAt=Date.now();renderLongWork(task);toast('Trabalho pausado e progresso salvo.')}
  catch(error){toast('Não foi possível pausar: '+error.message)}
}
async function resumeLongWork(){
  if(!activeWorkTask)return;
  try{const task=await api('/api/work/'+activeWorkTask.id+'/resume',{method:'POST'});workStatusReceivedAt=Date.now();renderLongWork(task);toast('Trabalho retomado.')}
  catch(error){toast('Não foi possível continuar: '+error.message)}
}
async function cancelLongWork(){
  if(!activeWorkTask)return;
  const ok=await confirmInApp('Cancelar trabalho prolongado?','O progresso já salvo será mantido, mas a IA não continuará esta tarefa.','Cancelar trabalho','Voltar');
  if(!ok)return;
  try{const task=await api('/api/work/'+activeWorkTask.id+'/cancel',{method:'POST'});workStatusReceivedAt=Date.now();renderLongWork(task);toast('Tarefa cancelada.')}
  catch(error){toast('Não foi possível cancelar: '+error.message)}
}
async function send(){
  const input=$('prompt'),text=input.value.trim();
  if(!text||isSending)return;
  const longMatch=text.match(/\btrabalh(?:e|ar|a)\b[\s\S]{0,100}?\bpor\s+(\d+)\s*(minutos?|mins?|m|horas?|h)\b/i);
  if(longMatch&&!/\b(não|nao|nunca)\b/i.test(text)){
    const amount=Number(longMatch[1]);const unit=longMatch[2].toLowerCase();
    const seconds=amount*(unit.startsWith('h')?3600:60);
    if(Number.isFinite(seconds)&&seconds>=60&&seconds<=10800){input.value='';await startLongWork(text,seconds);return}
    toast('O trabalho prolongado aceita de 1 minuto até 3 horas.');return;
  }
  const requestId=++conversationViewRequest;
  isSending=true;input.value='';input.disabled=true;$('sendBtn').disabled=true;
  $('attachBtn').disabled=true;$('imageGenBtn').disabled=true;
  if($('messages').querySelector('.welcome-msg'))$('messages').innerHTML='';
  bubble('user',text);
  const wait=bubble('assistant','Mensagem recebida. Estou preparando o trabalho...');
  const workStatus=$('workStatus');workStatus.classList.remove('hidden');workStatus.textContent='Preparando...';
  try{
    const response=await fetch('/api/chat/stream',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,conversation_id:conversationId,model_id:selectedModel})});
    if(!response.ok){let error={};try{error=await response.json()}catch{}throw new Error(error.detail||'Não foi possível iniciar a tarefa.')}
    if(!response.body)throw new Error('Este navegador não oferece suporte à resposta em tempo real.');
    const reader=response.body.getReader(),decoder=new TextDecoder();
    let buffer='',completed=false;
    const processEvent=raw=>{
      const line=raw.split('\n').find(value=>value.startsWith('data:'));
      if(!line)return;
      let event;try{event=JSON.parse(line.slice(5).trim())}catch{return}
      if(requestId!==conversationViewRequest)return;
      if(event.type==='progress'){
        wait.textContent=event.message||'Trabalhando...';
        workStatus.textContent=event.message||'Trabalhando...';
        announceProgress(event.message||'A Mikael AI está trabalhando.');
      }else if(event.type==='done'){
        completed=true;conversationId=event.conversation_id;
        wait.textContent=event.reply||'A IA não retornou uma resposta.';
        workStatus.classList.add('hidden');
        queuePendingApprovals(event.pending_actions||[]);
        loadConversations();
      }else if(event.type==='error'){
        completed=true;wait.textContent=event.message||'Ocorreu um erro durante o trabalho.';
        workStatus.classList.add('hidden');
      }
    };
    while(true){
      const {value,done}=await reader.read();
      if(done)break;
      buffer+=decoder.decode(value,{stream:true});
      const parts=buffer.split('\n\n');buffer=parts.pop()||'';
      parts.forEach(processEvent);
    }
    if(buffer.trim())processEvent(buffer);
    if(!completed)throw new Error('A conexão terminou antes da conclusão da tarefa.');
  }catch(e){
    if(requestId===conversationViewRequest){wait.textContent='Erro: '+e.message;workStatus.classList.add('hidden');toast(e.message)}
  }finally{
    isSending=false;input.disabled=false;$('sendBtn').disabled=false;
    $('attachBtn').disabled=false;$('imageGenBtn').disabled=false;
    if(requestId===conversationViewRequest)input.focus();
  }
}
async function loadFiles(){try{const rows=await api('/api/files');$('fileList').innerHTML='';if(!rows.length){$('fileList').textContent='Nenhum arquivo enviado ainda.';return}rows.forEach(f=>{const el=document.createElement('div');el.className='list-item file-item';if(f.is_image){const img=document.createElement('img');img.className='file-thumb';img.alt='Prévia de '+f.filename;img.loading='lazy';img.src='/api/files/'+f.id+'/preview';el.append(img)}const info=document.createElement('div');info.className='file-info';const title=document.createElement('span');title.textContent=(f.is_image?'Foto · ':'')+f.filename+' · '+f.characters+' caracteres';info.append(title);const actions=document.createElement('div');actions.className='file-actions';const download=document.createElement('button');download.textContent='Baixar';download.onclick=()=>{location.href='/api/files/'+f.id+'/download'};const b=document.createElement('button');b.textContent=f.is_image?'Analisar foto':'Analisar';b.onclick=async()=>{b.disabled=true;b.textContent='Analisando...';try{const r=await api('/api/files/'+f.id+'/analyze',{method:'POST'});showTab('chat');resetChat();bubble('assistant',r.analysis)}catch(e){toast(e.message)}finally{b.disabled=false;b.textContent=f.is_image?'Analisar foto':'Analisar'}};actions.append(download,b);el.append(info,actions);$('fileList').append(el)})}catch(e){toast(e.message)}}
async function generateFile(){const filename=$('newFileName').value.trim();const description=$('newFileDescription').value.trim();if(!filename||!description){toast('Informe o nome e descreva o arquivo.');return}const button=$('generateFile');button.disabled=true;button.textContent='Gerando...';try{const result=await api('/api/files/generate',{method:'POST',body:JSON.stringify({filename,description})});$('newFileName').value='';$('newFileDescription').value='';toast('Arquivo criado: '+result.filename);await loadFiles()}catch(e){toast(e.message)}finally{button.disabled=false;button.textContent='Gerar arquivo'}}
async function loadMemories(){const list=$('memoryList');try{const rows=await api('/api/memories');list.innerHTML='';if(!rows.length){list.textContent='Nenhuma memória salva ainda.';return}rows.forEach(m=>{const el=document.createElement('div');el.className='list-item';const t=document.createElement('span');t.textContent=m.content;const b=document.createElement('button');b.type='button';b.textContent='Excluir';b.onclick=async()=>{const allowed=await confirmInApp('Excluir esta memória?',m.content,'Excluir memória','Manter');if(!allowed)return;b.disabled=true;try{await api('/api/memories/'+m.id,{method:'DELETE'});await loadMemories();toast('Memória excluída')}catch(e){toast('Não foi possível excluir: '+e.message);b.disabled=false}};el.append(t,b);list.append(el)})}catch(e){list.textContent='Não foi possível carregar as memórias.';toast(e.message)}}
async function loadConnectors(){
  const list=$('connectorList');
  try{
    const rows=await api('/api/connectors');
    list.innerHTML='';
    const github=rows.find(x=>x.provider==='github');
    $('githubStatus').textContent=github?(github.enabled?'Conectado e ativo como @':'Conectado, mas desativado · @')+github.account:'Ainda não há uma conta GitHub conectada.';
    if(!github){$('githubPermissions').textContent='Conecte uma conta GitHub para consultar as permissões.';}
    else{await loadGitHubPermissions();}
    if(!rows.length){list.textContent='Nenhum conector conectado.';return}
    rows.forEach(item=>{
      const card=document.createElement('article');card.className='list-item connector-item'+(item.enabled?'':' connector-disabled');
      const info=document.createElement('div');info.className='connector-info';
      const identity=document.createElement('div');identity.className='connector-identity';
      const avatar=document.createElement('div');avatar.className='connector-avatar';
      if(item.provider==='github'&&item.avatar_url){const photo=document.createElement('img');photo.src=item.avatar_url;photo.alt='Foto do perfil GitHub de '+(item.account||'usuário');photo.loading='lazy';photo.referrerPolicy='no-referrer';photo.onerror=()=>{photo.remove();avatar.textContent='GH'};avatar.append(photo)}else{avatar.textContent=item.provider==='github'?'GH':'MCP'}
      const identityText=document.createElement('div');identityText.className='connector-identity-text';
      const name=document.createElement('b');name.textContent=item.name||'Conector sem nome';
      const detail=document.createElement('small');
      detail.textContent=(item.provider==='github'?'GitHub · @'+(item.account||'conta'):'MCP · '+(item.account||item.endpoint||'servidor'))+' · '+(item.enabled?'Ativo':'Desativado');
      identityText.append(name,detail);identity.append(avatar,identityText);info.append(identity);
      const actions=document.createElement('div');actions.className='connector-actions';
      const toggle=document.createElement('button');toggle.type='button';toggle.textContent=item.enabled?'Desabilitar':'Habilitar';toggle.setAttribute('aria-pressed',item.enabled?'true':'false');
      toggle.onclick=async()=>{toggle.disabled=true;const old=toggle.textContent;toggle.textContent='Salvando...';try{const result=await api('/api/connectors/'+item.id+'/enabled',{method:'PATCH',body:JSON.stringify({enabled:!item.enabled})});if(result.enabled!==!item.enabled)throw new Error('O servidor não confirmou o novo estado.');await loadConnectors();toast(result.enabled?'Conector habilitado.':'Conector desabilitado.')}catch(e){toast('Não foi possível alterar o conector: '+e.message);toggle.disabled=false;toggle.textContent=old}};
      const test=document.createElement('button');test.type='button';test.textContent='Testar';test.disabled=!item.enabled;
      test.onclick=async()=>{test.disabled=true;const old=test.textContent;test.textContent='Testando...';try{const result=await api('/api/connectors/'+item.id+'/test',{method:'POST'});toast('Conexão válida · '+(result.account||'OK'))}catch(e){toast('Falha no teste: '+e.message)}finally{test.disabled=!item.enabled;test.textContent=old}};
      const remove=document.createElement('button');remove.type='button';remove.textContent='Excluir';remove.className='danger-outline';
      remove.onclick=async()=>{const detail=item.provider==='github'?'A autorização GitHub salva para @'+(item.account||'sua conta')+' será removida deste app. A autorização concedida no GitHub não será revogada automaticamente.':'O servidor MCP '+item.name+' e seu token salvo serão removidos deste app.';const allowed=await confirmInApp('Excluir conector?',detail,'Excluir conector','Cancelar');if(!allowed)return;remove.disabled=true;remove.textContent='Excluindo...';try{await api('/api/connectors/'+item.id,{method:'DELETE'});await loadConnectors();toast('Conector excluído.')}catch(e){toast('Não foi possível excluir: '+e.message);remove.disabled=false;remove.textContent='Excluir'}};
      actions.append(toggle,test,remove);card.append(info,actions);list.append(card);
      loadConnectorToolSettings(card,item);
    });
  }catch(e){list.textContent='Não foi possível carregar os conectores.';toast(e.message)}
}
async function loadConnectorToolSettings(card,item){
  const panel=document.createElement('section');panel.className='connector-tool-settings';
  const heading=document.createElement('b');heading.textContent='O que a Mikael AI pode fazer';
  const note=document.createElement('small');note.textContent='Marque somente as ferramentas que este conector pode usar.';
  const list=document.createElement('div');list.className='connector-tool-list';list.textContent='Carregando ferramentas...';
  const save=document.createElement('button');save.type='button';save.className='outline';save.textContent='Salvar permissões';save.disabled=true;
  panel.append(heading,note,list,save);card.append(panel);
  try{
    const report=await api('/api/connectors/'+item.id+'/tools');
    list.innerHTML='';
    if(!report.tools.length){list.textContent='Nenhuma ferramenta segura foi encontrada neste conector.';return}
    const checks=[];
    report.tools.forEach(tool=>{
      const label=document.createElement('label');label.className='connector-tool-option';
      const input=document.createElement('input');input.type='checkbox';input.checked=Boolean(tool.enabled);
      const text=document.createElement('span');text.className='connector-tool-copy';
      const name=document.createElement('b');name.textContent=tool.label;
      const description=document.createElement('small');description.textContent=tool.description||'';
      text.append(name,description);label.append(input,text);list.append(label);
      checks.push({id:tool.id,input});
    });
    save.disabled=false;
    save.onclick=async()=>{
      save.disabled=true;save.textContent='Salvando...';
      try{
        const tool_ids=checks.filter(x=>x.input.checked).map(x=>x.id);
        await api('/api/connectors/'+item.id+'/tools',{method:'PATCH',body:JSON.stringify({tool_ids})});
        toast('Permissões do conector atualizadas.');
      }catch(error){toast('Não foi possível salvar: '+error.message)}
      finally{save.disabled=false;save.textContent='Salvar permissões'}
    };
  }catch(error){list.textContent='Não foi possível carregar as ferramentas: '+error.message}
}
function permissionScopeDescription(scope){
  const descriptions={
    'read:user':'Ler dados básicos do perfil GitHub.',
    'repo':'Acesso amplo a repositórios públicos e privados, conforme permissões da conta. Não significa que todas as operações estejam disponíveis na Mikael AI.',
    'workflow':'Gerenciar arquivos de workflow do GitHub Actions. A Mikael AI ainda não oferece ferramentas para executar workflows ou consultar seus logs.'
  };
  return descriptions[scope]||'Escopo OAuth concedido pelo GitHub; consulte a documentação oficial para o alcance detalhado.';
}
async function loadGitHubPermissions(){
  const container=$('githubPermissions');
  if(!container)return;
  container.textContent='Consultando o GitHub...';
  try{
    const report=await api('/api/connectors/github/permissions');
    container.innerHTML='';
    const status=document.createElement('div');
    status.className='permission-status '+(report.scope_status==='confirmed'?'confirmed':'unknown');
    status.textContent=report.scope_status==='confirmed'?'Escopos OAuth confirmados pelo GitHub':'O GitHub não informou o cabeçalho de escopos nesta consulta.';
    container.append(status);
    const scopeTitle=document.createElement('b');scopeTitle.textContent='Escopos OAuth concedidos';container.append(scopeTitle);
    const scopes=document.createElement('div');scopes.className='permission-list';
    if(report.scope_status==='confirmed'&&Array.isArray(report.oauth_scopes)&&report.oauth_scopes.length){
      report.oauth_scopes.forEach(scope=>{
        const item=document.createElement('div');item.className='permission-item';
        const name=document.createElement('b');name.textContent=scope;
        const detail=document.createElement('small');detail.textContent=permissionScopeDescription(scope);
        item.append(name,detail);scopes.append(item);
      });
    }else{
      const empty=document.createElement('small');empty.textContent=report.scope_status==='confirmed'?'O GitHub confirmou que não há escopos listados.':'Não é possível afirmar quais escopos foram concedidos sem o cabeçalho X-OAuth-Scopes.';
      scopes.append(empty);
    }
    container.append(scopes);
    const toolsTitle=document.createElement('b');toolsTitle.className='permission-section-title';toolsTitle.textContent='Ferramentas disponíveis na Mikael AI';container.append(toolsTitle);
    const tools=document.createElement('ul');tools.className='permission-bullets';
    (report.available_tools||[]).forEach(tool=>{const li=document.createElement('li');li.textContent=tool.label;tools.append(li)});
    container.append(tools);
    const blockedTitle=document.createElement('b');blockedTitle.className='permission-section-title';blockedTitle.textContent='Não disponíveis como ferramentas';container.append(blockedTitle);
    const blocked=document.createElement('ul');blocked.className='permission-bullets muted';
    (report.not_exposed||[]).forEach(item=>{const li=document.createElement('li');li.textContent=item.label+' — '+item.detail;blocked.append(li)});
    container.append(blocked);
    const notice=document.createElement('p');notice.className='permission-notice';notice.textContent=report.scope_notice||'Escopos OAuth e ferramentas da interface são coisas diferentes.';container.append(notice);
    const checked=document.createElement('small');checked.className='connector-note';checked.textContent='Conta: @'+(report.account||'desconhecida')+' · Verificado: '+new Date(Number(report.checked_at)*1000).toLocaleString('pt-BR');container.append(checked);
    if(!report.enabled){const disabled=document.createElement('small');disabled.className='permission-warning';disabled.textContent='O conector está desabilitado. A consulta de permissões foi feita apenas para transparência; as ferramentas não podem ser usadas até habilitar.';container.append(disabled);}
  }catch(error){
    container.textContent='Não foi possível consultar as permissões: '+error.message;
  }
}
async function addMcpConnector(){
  const name=$('mcpName').value.trim(),endpoint=$('mcpEndpoint').value.trim(),token=$('mcpToken').value;
  if(name.length<2||!endpoint){toast('Informe um nome e o endereço HTTPS do servidor MCP.');return}
  const button=$('addMcp');button.disabled=true;button.textContent='Testando servidor...';
  try{
    const result=await api('/api/connectors/mcp',{method:'POST',body:JSON.stringify({name,endpoint,token})});
    $('mcpToken').value='';$('mcpName').value='';$('mcpEndpoint').value='';
    await loadConnectors();toast('MCP conectado · '+(result.tools||[]).length+' ferramenta(s) encontrada(s).');
  }catch(e){toast('Não foi possível conectar: '+e.message)}
  finally{button.disabled=false;button.textContent='Testar e adicionar MCP'}
}
async 
function base64UrlToBytes(value){
  const padded=(value+'='.repeat((4-value.length%4)%4)).replace(/-/g,'+').replace(/_/g,'/');
  const raw=atob(padded);return Uint8Array.from(raw,c=>c.charCodeAt(0));
}
async function enableWorkNotifications(){
  const button=$('enableWorkNotifications');
  button.disabled=true;
  try{
    if(!('serviceWorker' in navigator)||!('PushManager' in window)||!('Notification' in window)){
      throw new Error('Este navegador não oferece notificações push. Use Chrome atualizado no Android.');
    }
    const permission=Notification.permission==='granted'? 'granted':await Notification.requestPermission();
    if(permission!=='granted')throw new Error('Permissão de notificações não concedida.');
    const config=await api('/api/push/public-key');
    const registration=await navigator.serviceWorker.register('/sw.js',{scope:'/'});
    await navigator.serviceWorker.ready;
    let subscription=await registration.pushManager.getSubscription();
    if(!subscription){
      subscription=await registration.pushManager.subscribe({
        userVisibleOnly:true,
        applicationServerKey:base64UrlToBytes(config.public_key)
      });
    }
    await api('/api/push/subscribe',{method:'POST',body:JSON.stringify(subscription.toJSON())});
    $('notificationStatus').textContent='Notificações ativadas. Você receberá avisos quando o trabalho começar, terminar ou for pausado.';
    button.textContent='Notificações ativadas';
    toast('Notificações ativadas com sucesso.');
  }catch(error){
    $('notificationStatus').textContent=error.message;
    toast('Não foi possível ativar notificações: '+error.message);
  }finally{button.disabled=false}
}

async function boot(){try{await api('/api/me');$('login').classList.add('hidden');$('app').classList.remove('hidden');try{const saved=localStorage.getItem('mikael_selected_model');if(['mikael','deepseek','gpt4o_mini'].includes(saved))selectedModel=saved}catch{}$('modelSelect').value=selectedModel;await loadModels();await loadPendingApprovals();const params=new URLSearchParams(location.search);if(params.get('connector')==='github_connected'){toast('GitHub conectado com sucesso!');showTab('settings')}else if(params.has('connector_error')){toast('Não foi possível conectar o GitHub. Confira a configuração OAuth.');showTab('settings')}if(params.has('connector')||params.has('connector_error'))history.replaceState({},'',location.pathname)}catch{$('login').classList.remove('hidden')}}
async function loadModels(){try{const models=await api('/api/models');const select=$('modelSelect');if(!Array.isArray(models)||!models.some(m=>m.id==='mikael'))throw new Error('Lista de modelos inválida.');select.innerHTML='';models.forEach(model=>{const option=document.createElement('option');option.value=model.id;option.textContent=model.name;option.title=model.description||'';select.append(option)});if(!models.some(m=>m.id===selectedModel))selectedModel='mikael';select.value=selectedModel}catch(error){toast('Não foi possível carregar os modelos: '+error.message)}}
$('approvalAllow').onclick=()=>closeApproval(true);
$('approvalDeny').onclick=()=>closeApproval(false);
$('approvalModal').addEventListener('click',event=>{if(event.target===$('approvalModal'))closeApproval(false)});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('approvalModal').classList.contains('hidden'))closeApproval(false)});
$('modelSelect').onchange=()=>{const value=$('modelSelect').value;if(!['mikael','deepseek','gpt4o_mini'].includes(value)){selectedModel='mikael';$('modelSelect').value='mikael';return}selectedModel=value;try{localStorage.setItem('mikael_selected_model',value)}catch{}toast('Modelo selecionado: '+$('modelSelect').selectedOptions[0].textContent)};
$('loginBtn').onclick=async()=>{try{await api('/api/login',{method:'POST',body:JSON.stringify({password:$('password').value})});boot()}catch(e){$('loginError').textContent=e.message}};
$('password').addEventListener('keydown',e=>{if(e.key==='Enter')$('loginBtn').click()});
$('githubConnect').onclick=()=>{location.href='/api/connectors/github/start'};
$('githubPermissionsRefresh').onclick=loadGitHubPermissions;
$('conversationSearch').addEventListener('input',renderConversations);
$('speakProgress').onchange=()=>{speakProgressEnabled=$('speakProgress').checked;try{localStorage.setItem('mikael_speak_progress',speakProgressEnabled?'1':'0')}catch{}if(!speakProgressEnabled&&'speechSynthesis'in window)window.speechSynthesis.cancel();toast(speakProgressEnabled?'Leitura das atualizações ativada.':'Leitura das atualizações desativada.')};
try{$('speakProgress').checked=localStorage.getItem('mikael_speak_progress')==='1'}catch{}if(!('speechSynthesis'in window)||!('SpeechSynthesisUtterance'in window)){$('speakProgress').disabled=true;$('speakProgress').parentElement.title='Este navegador não oferece leitura em voz alta.'}

$('addMcp').onclick=addMcpConnector;
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
      status.textContent='Análise de '+uploaded.filename+':\n\n'+(result.analysis||'A IA não retornou uma análise.');
    }catch(error){
      status.textContent='Não foi possível analisar '+file.name+': '+error.message;
    }
  }
  await loadFiles();
}
$('sendBtn').onclick=send;$('startLongWork').onclick=()=>startLongWork($('workGoal').value,$('workDuration').value);
$('pauseLongWork').onclick=pauseLongWork;$('resumeLongWork').onclick=resumeLongWork;$('cancelLongWork').onclick=cancelLongWork;$('enableWorkNotifications').onclick=enableWorkNotifications;

$('prompt').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});
$('attachBtn').onclick=()=>{if(!isSending&&!isGeneratingImage)$('chatFileInput').click()};
$('imageGenBtn').onclick=generateChatImage;
$('chatFileInput').onchange=handleChatFiles;
$('newChat').onclick=newConversation;$('startChat').onclick=()=>{showTab('chat');newConversation();$('prompt').focus()};
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{showTab('chat');resetChat();$('prompt').value=b.dataset.prompt;$('prompt').focus()});
$('generateFile').onclick=generateFile;$('fileInput').onchange=async e=>{const selected=Array.from(e.target.files||[]);if(!selected.length)return;if(selected.length>10){toast('Envie no máximo 10 arquivos por vez.');e.target.value='';return}let sent=0;const errors=[];for(const file of selected){const form=new FormData();form.append('file',file);try{await api('/api/upload',{method:'POST',body:form});sent++}catch(err){errors.push(file.name+': '+err.message)}}e.target.value='';await loadFiles();if(errors.length)toast(sent+' enviado(s). Falhas: '+errors.slice(0,2).join(' | '));else toast(sent+' arquivo(s)/foto(s) enviado(s) com sucesso')};
$('saveMemory').onclick=async()=>{const content=$('memoryText').value.trim();if(!content)return;try{await api('/api/memories',{method:'POST',body:JSON.stringify({content,category:'projeto'})});$('memoryText').value='';toast('Memória salva');loadMemories()}catch(e){toast(e.message)}};
boot();
refreshLongWork();
workPollTimer=setInterval(()=>refreshLongWork(),15000);
