# Mikael AI V1 Core

Modelo experimental autoral com pesos inicializados aleatoriamente. Não usa pesos de Qwen, Llama, Gemma ou outro LLM pronto. PyTorch é o framework matemático.

## Núcleo do modelo
- Transformer decoder-only causal.
- Tokenizador byte-level UTF-8 próprio (PAD=0, BOS=1, EOS=2, bytes=3..258), compatível com acentos e emojis.
- Configuração inicial: 4 camadas, dimensão 128, 4 cabeças, contexto 256.
- Treinamento causal e treinamento supervisionado SFT em scripts separados.

## Treinamento de programação
O primeiro corpus autoral de programação em português está em:
- data/programming_train.jsonl: 128 exemplos de treino.
- data/programming_val.jsonl: 15 exemplos de validação.
- data/programming_test.jsonl: 10 exemplos de teste isolado.

Abrange fundamentos de Python, JavaScript, HTML, CSS, Java, Kotlin, algoritmos, estruturas de dados, Git, APIs, segurança e depuração. Os exemplos foram escritos para caber no contexto atual de 256 bytes/tokens do tokenizador byte-level. O corpus é um primeiro ciclo didático e ainda é pequeno para produzir competência avançada; aumente-o com exemplos revisados e testes executáveis antes de alegar qualidade profissional.

### Treinar pelo celular com Google Colab
Abra o notebook:
Mikael_AI_V1_Programacao_Colab.ipynb

No Colab, selecione GPU quando disponível e execute as células em ordem. O notebook:
1. Clona esta branch.
2. Executa os testes e a compilação.
3. Treina até 30 épocas, com early stopping pela validação.
4. Salva o melhor checkpoint e um relatório.
5. Permite baixar os arquivos do treinamento.

Comando equivalente:
python sft_train.py --train data/programming_train.jsonl --val data/programming_val.jsonl --test data/programming_test.jsonl --epochs 30 --batch-size 8 --lr 0.0001 --patience 7 --output checkpoints/programming

O script salva o melhor checkpoint em checkpoints/programming/mikael-ai-v1-sft.pt e training_report.json. A avaliação de teste usa o checkpoint escolhido pela validação. Loss menor não garante código correto; revise e execute testes em ambiente isolado.

## Criação e entrega de arquivos/imagens
artifact_tools.py cria arquivos em uma pasta de saída controlada, sem aceitar caminhos arbitrários. Tipos de texto permitidos: TXT, MD, JSON, CSV, PY, JS, HTML, CSS, XML, YAML, JAVA, KT, C e CPP. Tipos de imagem: PNG, JPG, JPEG e WEBP. Há limites de tamanho, validação de extensão, assinatura real da imagem e nomes aleatórios para evitar sobrescrita.

O conector create_text_file está disponível quando o host chama register_artifact_connectors(). O conector create_image só é registrado quando o host fornece um image_generator. Esse callback deve chamar um provedor de geração de imagens configurado no servidor e retornar bytes reais PNG/JPEG/WEBP. Não há provedor de imagens embutido nesta biblioteca e não se deve fingir que a imagem foi gerada se o serviço não estiver configurado.

O gerenciador salva arquivos localmente no servidor, mas não cria sozinho um link público. O aplicativo/backend precisa implementar uma rota de download autenticada, verificar autorização e associar o artifact_id à conversa/usuário. Configure url_builder para devolver o link dessa rota. A interface Android também precisa mostrar cartão de arquivo/imagem com ação abrir/baixar.

## Conectores web
connectors.py fornece ConnectorRegistry. web_tools.py inclui pesquisa via Brave Search API (BRAVE_SEARCH_API_KEY no ambiente do servidor) e leitura de páginas públicas HTTP/HTTPS. Não executa JavaScript, não faz login e não acessa conteúdo privado. Conteúdo externo é dado não confiável. Nunca coloque chaves no app Android, no prompt ou no GitHub.

## Programação
coding_tools.py verifica sintaxe Python com AST, sem executar o código. Para outras linguagens, a validação sintática completa ainda não está implementada. O modelo pode gerar exemplos, mas o host não deve executar código gerado automaticamente.

## O que falta para uma IA de programação forte
- Expandir o corpus para milhares de exemplos revisados, com tarefas reais, bugs, testes e soluções explicadas.
- Acrescentar benchmarks separados por linguagem e dificuldade.
- Validar códigos com interpretadores/compiladores isolados; não usar apenas loss textual.
- Testar generalização em perguntas que não aparecem no treino.
- Evoluir arquitetura e contexto depois de medir memória e desempenho.
- Integrar o controlador de ferramentas, execução de testes segura e runtime Android.
- O checkpoint treinado precisa ser convertido/adaptado para runtime Android; o protótipo Python ainda não roda diretamente no app.

## Auditoria
Rode pytest -q e:
python -m py_compile mikael_ai_v1.py web_tools.py response_policy.py connectors.py coding_tools.py dataset_tools.py sft_train.py artifact_tools.py
CI automatiza testes e sintaxe; ainda é necessário teste integrado no backend e no Android.
