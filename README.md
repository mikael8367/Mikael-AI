# Mikael AI

Assistente de programação com backend FastAPI, interface mobile, autenticação por senha, histórico, memórias persistentes, upload e análise de arquivos e integração com modelos compatíveis com a API da OpenAI.

## O que já funciona
- Chat com modelo LLM configurável por variáveis de ambiente.
- Histórico persistente de conversas.
- Memórias manuais persistidas no banco e recuperadas por correspondência de palavras.
- Upload e extração de texto de código, PDF e DOCX.
- Análise de arquivos pelo modelo (sem executar os arquivos).
- Interface mobile com abas inferiores animadas.
- Autenticação por senha e cookie HttpOnly.
- Health check em `/health`.

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
A versão inicial requer validação em ambiente real. Antes de produção, adicione rate limiting, proteção CSRF adequada, política de retenção/remoção de arquivos e logs estruturados. Nunca considere um deploy concluído sem testar login, chat, banco, upload e análise.
