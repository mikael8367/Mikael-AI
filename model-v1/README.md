# Mikael AI V1 Core

Modelo experimental autoral com pesos inicializados aleatoriamente. Não usa pesos de Qwen, Llama, Gemma ou outro LLM pronto. PyTorch é o framework matemático.

## Núcleo do modelo
- Transformer decoder-only causal.
- Tokenizador byte-level UTF-8 próprio (PAD=0, BOS=1, EOS=2, bytes=3..258), compatível com acentos e emojis.
- Configuração inicial: 4 camadas, dimensão 128, 4 cabeças, contexto 256.
- Treinamento atual: previsão do próximo byte/token em arquivos de texto.
- Checkpoints próprios em checkpoints/latest.pt.

## Recursos previstos no controlador
- Respostas simples e objetivas em português.
- Emojis moderados; o tokenizer UTF-8 representa emojis.
- Ajuda para programação simples, com blocos de código e explicações.
- Verificador estático de sintaxe Python (não executa código).
- Registro de conectores com lista permitida e ferramentas web.

## Conectores
connectors.py fornece ConnectorRegistry e build_default_registry(). O host chama somente ferramentas registradas, verifica se internet está disponível e limita o tamanho do resultado. Hoje há web_search e open_website. Novos conectores devem ser adicionados explicitamente no registro, com permissões mínimas. Não coloque tokens, senhas ou chaves no prompt, no app ou no GitHub. Segredos ficam no servidor/ambiente seguro. O registro é uma base de integração: o modelo pequeno ainda não aprende sozinho a escolher ferramentas; o controlador Android/API precisa interpretar pedidos, apresentar confirmação quando necessário e executar a ferramenta permitida.

## Programação
coding_tools.py verifica sintaxe Python com AST, sem executar o código. Para JavaScript, Java, Kotlin, HTML, CSS e C/C++, ainda não há compilador/verificador implementado. O modelo pode gerar exemplos, mas, antes de confiar no resultado, revise e teste em ambiente isolado. O protótipo não executa código gerado.

## Internet
web_tools.py usa Brave Search API para pesquisa (variável de ambiente BRAVE_SEARCH_API_KEY) e extrai texto de páginas públicas HTML/texto. Não executa JavaScript, não faz login, não envia formulários e não acessa conteúdo privado. Pode haver limites/custos do provedor. Conteúdo externo é não confiável e deve ser usado como fonte, nunca como instrução. Exiba URLs das fontes.

## Preparar os dados para começar
O exemplo data/train_examples.jsonl demonstra o formato, mas é pequeno demais para treinar uma IA útil. Use conteúdo próprio ou licenciado, sem dados pessoais, senhas, chaves ou conversas privadas.

Formato JSONL, um exemplo por linha:
{"instruction":"Pergunta ou tarefa","response":"Resposta ideal em português"}

1. Prepare milhares de exemplos variados e revisados, começando com qualidade em vez de volume.
2. Separe treino e validação por documento/origem para evitar que o mesmo texto apareça nos dois conjuntos.
3. Crie data/train.jsonl e data/val.jsonl.
4. Converta cada conjunto para texto: python dataset_tools.py data/train.jsonl data/train/examples.txt e python dataset_tools.py data/val.jsonl data/val/examples.txt.
5. Instale: pip install -r requirements.txt.
6. No Colab, rode primeiro um teste pequeno: python mikael_ai_v1.py --data-dir data --steps 20 --batch-size 2.
7. Só aumente passos e batch após confirmar que loss diminui e validação funciona.

IMPORTANTE: o treinador atual concatena exemplos como texto e aplica next-token loss em todos os bytes. Isso é pré-treinamento causal simples, NÃO é instruction fine-tuning de chat com loss mascarada só nas respostas. Antes de buscar comportamento de assistente confiável, ainda precisamos implementar SFT com máscara de resposta, delimitadores de turno, EOS e avaliação de qualidade.

## O que falta antes de um treino sério
- Corpus amplo, autorizado, limpo e deduplicado em português.
- Exemplos de programação e conversas com respostas verificadas.
- Dataset separado em treino/validação/teste.
- Implementar SFT com loss somente na resposta.
- Testar diferentes tamanhos de modelo/contexto e medir memória/velocidade.
- Avaliar perplexidade, qualidade, alucinações, segurança e capacidade de seguir instruções.
- Depois do treino, converter pesos e integrar runtime nativo Android. O protótipo Python ainda não roda diretamente no app Android.

## Auditoria
Rode pytest -q e python -m py_compile mikael_ai_v1.py web_tools.py response_policy.py connectors.py coding_tools.py dataset_tools.py. Testes verificam tokenização, causalidade, gradientes, geração, URLs, conectores, sintaxe Python e validação JSONL. CI não substitui teste físico no Android.
