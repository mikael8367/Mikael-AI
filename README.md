# Mikael AI

Assistente de programação com backend FastAPI, interface mobile, autenticação por senha, histórico, memórias persistentes, upload e análise de arquivos e integração com modelos compatíveis com a API da OpenAI.

## O que já funciona
- Chat com modelo LLM configurável por variáveis de ambiente.
- Histórico persistente de conversas.
- Memórias manuais persistidas no banco e recuperadas por correspondência de palavras.
- Upload e extração de texto de código, PDF e DOCX.
- Análise de arquivos pelo modelo (sem executar os arquivos).
- Instruções avançadas de engenharia de software, depuração e revisão de código.
- Modelo DeepSeek V4.1 Flash com nível de raciocínio configurável.
- Pesquisa na web sob demanda pelo OpenRouter, com links das fontes incluídos nas respostas.
- Geração de imagens na conversa via OpenRouter; imagens geradas ficam salvas na aba Arquivos.
- Conector GitHub por OAuth, com leitura e escrita de arquivos, criação de issues e pull requests em repositórios autorizados.
- Cadastro de servidores MCP remotos por HTTPS, com segredo armazenado criptografado e exposição limitada a ferramentas aparentemente somente de leitura.
- Interface mobile com abas inferiores animadas e versão visível no canto inferior direito.
- Autenticação por senha e cookie HttpOnly.
- Health check em `/health`, incluindo a versão atual.

## Versionamento
A versão segue o padrão `MAJOR.MINOR.PATCH`:
- **PATCH** (ex.: `1.0.1`): correções de bugs e ajustes pequenos sem adicionar funcionalidades.
- **MINOR** (ex.: `1.1.0`): novos recursos mantendo compatibilidade.
- **MAJOR** (ex.: `2.0.0`): mudanças grandes que alteram significativamente o funcionamento ou quebram compatibilidade.

A versão atual fica centralizada em `APP_VERSION` no arquivo `app/main.py`. Ao publicar uma atualização, altere esse valor e mantenha a versão exibida na interface e no health check sincronizada.

## Limites desta versão
- A IA não treina os pesos do modelo com conversas. O sistema guarda memórias e histórico para recuperar contexto.
- A aba Projetos ainda é uma área inicial; escrita/edição de repositórios, execução de código em sandbox e busca vetorial avançada não estão habilitadas.
- Arquivos são analisados como texto. O servidor não executa código enviado.
- O plano gratuito do Render pode dormir por inatividade e os limites de banco/serviço podem mudar. Verifique os limites atuais antes de publicar.

## Publicar pelo celular
1. Envie todos os arquivos e pastas mantendo a estrutura.
2. No Render, escolha **New + > Blueprint** e conecte o repositório.
3. O Render lerá `render.yaml` e criará o serviço e o banco.
4. Em Environment, preencha `APP_PASSWORD` com uma senha forte e `LLM_API_KEY` com a chave do provedor.
5. Confira `LLM_BASE_URL` e `LLM_MODEL`, faça o deploy e abra a URL `onrender.com` no navegador do celular.

## Conectores GitHub e MCP

A tela Configurações permite conectar o GitHub e cadastrar servidores MCP remotos.

### Configurar OAuth do GitHub
1. Abra https://github.com/settings/developers no navegador e entre em **OAuth Apps**.
2. Crie uma OAuth App chamada Mikael AI.
3. Em **Homepage URL**, use https://mikael-ai.onrender.com.
4. Em **Authorization callback URL**, use exatamente https://mikael-ai.onrender.com/api/connectors/github/callback.
5. Copie o Client ID e gere um Client Secret.
6. No Render, abra Environment do serviço e configure `GITHUB_CLIENT_ID` e `GITHUB_CLIENT_SECRET`. Configure `GITHUB_REDIRECT_URI` com a URL de callback acima.
7. Abra Configurações no site e toque em **Conectar conta GitHub**.

A autorização solicita `read:user`, `repo` e `workflow`. O escopo `repo` permite leitura e escrita nos repositórios públicos e privados aos quais sua conta já tem acesso; `workflow` permite criar ou atualizar arquivos de GitHub Actions. A Mikael AI pode listar repositórios, ler arquivos e issues, criar/atualizar arquivos (gerando commits), criar issues e abrir pull requests. A exclusão de um arquivo individual só fica disponível após uma confirmação separada na própria interface: o cartão informa repositório, caminho e branch, e oferece **Permitir exclusão** ou **Negar**. A autorização OAuth, mesmo já concedida, nunca aprova uma exclusão por si só. Não há ferramenta para apagar repositórios, branches, secrets ou configurações, nem para administrar toda a conta GitHub. Permissões efetivas também dependem das regras da organização, SSO e permissões que você já possui.

Se você já conectou o GitHub antes da versão 1.9.0, desconecte e conecte novamente depois do deploy para o GitHub mostrar a solicitação de `workflow`. A autorização atualizada precisa ser aprovada na tela oficial do GitHub.

### Aprovação de ações destrutivas

A Mikael AI não executa exclusões de arquivos GitHub diretamente. Ela cria uma solicitação pendente, exibida em uma janela própria com o destino exato. Cada solicitação expira em 15 minutos, pode ser negada e é validada novamente no GitHub antes da execução; se o arquivo mudou desde a prévia, a exclusão é cancelada. A interface também pede confirmação antes de desconectar conectores ou apagar memórias. Ferramentas MCP continuam restritas a operações filtradas como leitura e não recebem autorização para executar exclusões.

### Adicionar um servidor MCP
Informe nome, URL HTTPS pública do endpoint MCP Streamable HTTP e, se necessário, um token Bearer no campo próprio. O token é criptografado no servidor usando uma chave derivada de `APP_SECRET`; não é enviado de volta ao navegador. Não cole senhas de conta nem tokens no chat. Por segurança, endpoints locais, HTTP simples e IPs privados são rejeitados. Ferramentas MCP são filtradas para expor apenas nomes que aparentam ser de leitura; isso não substitui a revisão das permissões e da confiabilidade do servidor.

Desconectar remove a credencial armazenada pela Mikael AI, mas não revoga automaticamente a autorização na plataforma externa. Para revogar completamente o GitHub, remova o acesso em https://github.com/settings/applications.

**Importante:** mantenha `APP_SECRET` estável. Se ela for alterada, os tokens criptografados anteriormente não poderão ser descriptografados; será necessário reconectar os serviços.

## Geração de imagens
A geração usa a mesma `LLM_API_KEY` do OpenRouter e o modelo definido em `LLM_IMAGE_MODEL` (padrão: `google/gemini-2.5-flash-image`). A geração de imagens pode consumir créditos e não deve ser considerada gratuita. O usuário descreve a imagem no campo da conversa e toca no botão ✧. A imagem é salva em Arquivos.

## Pesquisa na web
A Mikael AI pode pesquisar na web quando a pergunta pedir informações atuais, documentação, versões, APIs ou quando o usuário solicitar uma pesquisa. A busca é executada pelo servidor do OpenRouter e as fontes retornadas são anexadas à resposta. Configure `LLM_WEB_SEARCH_ENABLED`, `LLM_WEB_SEARCH_ENGINE` e `LLM_WEB_SEARCH_MAX_RESULTS`. O padrão usa Exa com até 5 resultados e limita até 3 chamadas de busca por resposta. A pesquisa pode gerar cobrança adicional na conta OpenRouter, além dos tokens do modelo; confira os preços atuais antes de usar.

## Modelo de programação e raciocínio
O modelo padrão é `deepseek/deepseek-v4.1-flash`, com `LLM_REASONING_EFFORT=high`. O modelo e o nível de raciocínio podem ser alterados pelas variáveis `LLM_MODEL` e `LLM_REASONING_EFFORT` (`low`, `medium` ou `high`). O uso do provedor pode gerar custos conforme os preços e créditos da conta OpenRouter.

## Provedor de IA
O projeto usa o SDK OpenAI com `base_url` configurável. Para OpenRouter, gere uma chave na sua conta e configure `LLM_API_KEY`. A disponibilidade e o preço dos modelos mudam; confira o identificador exato no painel do provedor. Não coloque a chave no frontend nem no GitHub.

## Desenvolvimento
Python 3.11+:
```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

## Auditoria técnica
A versão atual requer validação contínua em ambiente real. Antes de produção, adicione rate limiting, proteção CSRF adequada, política de retenção/remoção de arquivos e logs estruturados. Nunca considere um deploy concluído sem testar login, chat, banco, upload e análise.
