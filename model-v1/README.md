# Mikael AI V1 Core

Primeiro protótipo de um modelo de linguagem autoral com pesos inicializados aleatoriamente. Não carrega pesos de Qwen, Llama, Gemma ou qualquer LLM pré-treinado.

## Arquitetura inicial
- Decoder-only Transformer causal implementado no arquivo mikael_ai_v1.py.
- PyTorch é usado como framework de tensores e operações; não fornece pesos ou modelo pré-treinado.
- Tokenizador UTF-8 byte-level próprio: PAD=0, BOS=1, EOS=2 e bytes=3..258.
- 4 camadas, dimensão 128, 4 cabeças, contexto 256 e vocabulário 259.
- Treinamento por previsão do próximo token em arquivos de texto locais.
- Checkpoint próprio em checkpoints/latest.pt.

## Treinar pelo Google Colab
1. Clone o repositório e abra a pasta model-v1.
2. Instale: pip install -r requirements.txt
3. Coloque textos que você tenha direito de usar em data/train/ e data/val/. Não inclua dados pessoais.
4. Execute: python mikael_ai_v1.py --data-dir data --steps 2000 --batch-size 16
5. O checkpoint será salvo em checkpoints/latest.pt.

Para gerar texto depois do treino:
python mikael_ai_v1.py --prompt "Olá, quem é você?" --checkpoint checkpoints/latest.pt --max-new-tokens 80

## Limitações
Este é um protótipo pequeno para validar arquitetura e pipeline, não uma IA geral pronta. Começa sem conhecimento. A qualidade depende do corpus, tempo de treinamento e avaliação. Tokenização por bytes é simples, mas pode consumir mais tokens em português. Ainda não há instruction tuning, memória persistente, ferramentas ou runtime nativo Android. O runtime Android será uma etapa posterior, depois de validar o modelo e o formato dos pesos.

## Auditoria
Execute pytest -q. Os testes verificam UTF-8, dimensões, loss, máscara causal, gradientes e limite de geração. Comece com poucos passos e acompanhe loss de treino e validação. Carregue apenas checkpoints gerados por você ou de origem confiável.
