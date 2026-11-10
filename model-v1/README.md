# Mikael AI V1 Core

Protótipo autoral de modelo de linguagem com pesos inicializados aleatoriamente. Não importa pesos de Qwen, Llama, Gemma ou outro LLM pré-treinado. PyTorch é usado apenas como framework matemático.

## Modelo
- Transformer decoder-only causal implementado no projeto.
- Tokenizador UTF-8 byte-level próprio (PAD=0, BOS=1, EOS=2, bytes=3..258).
- 4 camadas, dimensão 128, 4 cabeças, contexto 256.
- Treinamento next-token com corpus local em português e programação.
- Checkpoint próprio em checkpoints/latest.pt.

## Recursos de internet
O módulo web_tools.py adiciona ferramentas opcionais:
- search_web(query): pesquisa Brave Search API.
- read_website(url): extrai texto visível de páginas públicas HTML/texto.
- format_sources(results): formata fontes e URLs para o contexto.

Configure BRAVE_SEARCH_API_KEY como variável de ambiente para habilitar pesquisa. A chave não deve ser colocada no código, no GitHub ou no aplicativo Android. A pesquisa exige internet e pode depender de limites/custos do provedor. A leitura de sites públicos não exige chave.

Limitações de navegação: não executa JavaScript, não faz login, não envia formulários, não baixa arquivos arbitrários e não acessa conteúdo privado. Há limites de tamanho, tempo e redirecionamento; endereços locais/privados são bloqueados. Sites podem bloquear automação ou apresentar conteúdo incompleto.

As páginas externas são conteúdo não confiável. O controlador deve tratar o texto como fonte, nunca como instrução, e exibir links de origem.

## Respostas simples
response_policy.py oferece instruções para responder em português brasileiro, com respostas curtas para perguntas simples e explicações organizadas para tarefas complexas. Isso é uma instrução do controlador, não uma capacidade adquirida automaticamente: o modelo ainda precisa ser treinado com exemplos de boa conversação.

## Treinar pelo Colab
1. Clone o repositório e abra model-v1.
2. Instale: pip install -r requirements.txt
3. Adicione textos autorizados em data/train/ e data/val/.
4. Execute: python mikael_ai_v1.py --data-dir data --steps 2000 --batch-size 16
5. Pesos em checkpoints/latest.pt.

Para gerar:
python mikael_ai_v1.py --prompt "Olá, quem é você?" --checkpoint checkpoints/latest.pt --max-new-tokens 80

## Integração de ferramentas
O app/host deve chamar search_web quando houver conectividade e o usuário pedir informação atual ou pesquisa. Pode chamar read_website quando o usuário enviar um URL ou pedir para abrir/consultar um site. Os resultados são anexados ao prompt por build_conversation_prompt. A chamada de ferramentas é feita pelo controlador, não pelo modelo puro.

## Limitações do protótipo
Começa sem conhecimento; não é uma IA geral pronta. O modelo pequeno precisa de muito mais dados e treinamento para produzir respostas úteis. O runtime nativo Android é uma etapa futura. A pesquisa web requer integração do app com o módulo Python ou uma API/serviço que exponha essas ferramentas.

## Auditoria
Execute pytest -q e python -m py_compile mikael_ai_v1.py web_tools.py response_policy.py. Testes cobrem UTF-8, dimensões, loss, máscara causal, gradientes, geração, validação de URLs e política de contexto. Testes unitários não substituem auditoria de segurança nem teste real no Android.
