# Mikael AI V1 Core

Modelo experimental autoral com pesos inicializados aleatoriamente. Não usa pesos de Qwen, Llama, Gemma ou outro LLM pronto. PyTorch é o framework matemático.

## Núcleo do modelo
- Transformer decoder-only causal.
- Tokenizador byte-level UTF-8 próprio (PAD=0, BOS=1, EOS=2, bytes=3..258), compatível com acentos e emojis.
- Configuração inicial: 4 camadas, dimensão 128, 4 cabeças, contexto 256.
- Treinamento causal e treinamento supervisionado SFT em scripts separados.

## Recursos do controlador
- Respostas simples em português e suporte a emojis.
- Ajuda para programação simples e verificação estática de sintaxe Python.
- Conectores web controlados por lista permitida.
- Criação de arquivos de texto/código e integração opcional com provedor de imagens.

## Criação e entrega de arquivos/imagens
artifact_tools.py cria arquivos em uma pasta de saída controlada, sem aceitar caminhos arbitrários. Tipos de texto permitidos: TXT, MD, JSON, CSV, PY, JS, HTML, CSS, XML, YAML, JAVA, KT, C e CPP. Tipos de imagem: PNG, JPG, JPEG e WEBP. Há limites de tamanho, validação de extensão, assinatura real da imagem e nomes aleatórios para evitar sobrescrita.

O conector create_text_file está disponível quando o host chama register_artifact_connectors(). O conector create_image só é registrado quando o host fornece um image_generator. Esse callback deve chamar um provedor de geração de imagens configurado no servidor e retornar bytes reais PNG/JPEG/WEBP. Não há provedor de imagens embutido nesta biblioteca e não se deve fingir que a imagem foi gerada se o serviço não estiver configurado.

IMPORTANTE: o gerenciador salva arquivos localmente no servidor, mas não cria sozinho um link público. O aplicativo/backend precisa implementar uma rota de download autenticada, verificar autorização e associar o artifact_id à conversa/usuário. Configure url_builder para devolver o link dessa rota. Não exponha diretórios internos, não aceite caminhos enviados pelo modelo e não deixe arquivos privados públicos por padrão. A interface Android também precisa mostrar cartão de arquivo/imagem com ação abrir/baixar.

## Conectores web
connectors.py fornece ConnectorRegistry. web_tools.py inclui pesquisa via Brave Search API (BRAVE_SEARCH_API_KEY no ambiente do servidor) e leitura de páginas públicas HTTP/HTTPS. Não executa JavaScript, não faz login e não acessa conteúdo privado. Conteúdo externo é dado não confiável. Nunca coloque chaves no app Android, no prompt ou no GitHub.

## Programação
coding_tools.py verifica sintaxe Python com AST, sem executar o código. Para outras linguagens, a validação sintática completa ainda não está implementada. O modelo pode gerar exemplos, mas o host não deve executar código gerado automaticamente.

## Treinamento supervisionado (SFT)
O script sft_train.py aplica loss somente nos tokens da resposta, mascarando o enunciado da pergunta. Execute:
python sft_train.py --train data/train.jsonl --val data/val.jsonl --epochs 3 --batch-size 8

Os arquivos train.jsonl e val.jsonl atuais são apenas smoke-tests minúsculos e não produzem um assistente competente. Expanda com exemplos variados, revisados e autorizados antes de qualquer treino sério.

## Preparar os dados
Formato JSONL, um exemplo por linha:
{"instruction":"Pergunta ou tarefa","response":"Resposta ideal em português"}

- Use conteúdo próprio ou licenciado; não inclua senhas, chaves, dados pessoais ou conversas privadas.
- Separe treino, validação e teste por documento/origem para reduzir vazamento.
- Verifique fatos, português, código, fontes e segurança de cada exemplo.
- Aumente contexto e batch somente após medir memória e estabilidade.

## O que falta para uma versão utilizável
- Corpus grande, limpo, deduplicado e autorizado.
- Mais exemplos de programação, conversação, conectores e criação de artefatos.
- Treinar e avaliar pesos com métricas e testes humanos.
- Configurar um provedor real de imagens e proteger suas credenciais no backend.
- Implementar API de download autenticado e interface Android para exibir arquivos/imagens.
- Integrar o controlador de ferramentas ao fluxo de conversa; os pesos atuais ainda não decidem de forma confiável quando chamar ferramentas.
- Converter pesos e integrar runtime nativo Android. O protótipo Python ainda não roda diretamente no app.

## Auditoria
Rode pytest -q e:
python -m py_compile mikael_ai_v1.py web_tools.py response_policy.py connectors.py coding_tools.py dataset_tools.py sft_train.py artifact_tools.py
A CI verifica os módulos e testes automatizados; ainda é necessário teste integrado no backend e no Android.
