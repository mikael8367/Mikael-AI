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
- A aba Projetos é a área inicial; integração GitHub, edição real de repositórios, execução de testes em sandbox e busca vetorial avançada são próximas etapas.
- Arquivos são analisados como texto. O servidor não executa código enviado.
- O plano gratuito do Render pode dormir por inatividade e os limites de banco/serviço podem mudar. Verifique os limites atuais antes de publicar.

## Publicar pelo celular
1. Envie todos os arquivos e pastas mantendo a estrutura.
2. No Render, escolha **New + > Blueprint** e conecte o repositório.
3. O Render lerá `render.yaml` e criará o serviço e o banco.
4. Em Environment, preencha `APP_PASSWORD` com uma senha forte e `LLM_API_KEY` com a chave do provedor.
5. Confira `LLM_BASE_URL` e `LLM_MODEL`, faça o deploy e abra a URL `onrender.com` no navegador do celular.

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
