# Dados de treinamento

## Corpus de programação da Mikael AI V1
- programming_train.jsonl: 128 exemplos autorais em português.
- programming_val.jsonl: 15 exemplos para escolher o melhor checkpoint.
- programming_test.jsonl: 10 exemplos isolados para avaliação final.
- Os tópicos incluem Python, JavaScript, HTML, CSS, Java, Kotlin, algoritmos, estruturas de dados, Git, APIs, segurança e depuração.
- O corpus inicial é didático e pequeno; não representa conhecimento profissional nem substitui milhares de exemplos revisados e benchmarks.

## Regras para novos dados
- Use textos e exemplos que você criou ou tem autorização para usar.
- Não inclua senhas, chaves de API, dados pessoais, conversas privadas ou material protegido sem permissão.
- Separe treino, validação e teste por documento/origem, não apenas por linhas aleatórias, para reduzir vazamento.
- Revise manualmente precisão, português, código, segurança e resultado esperado.
- Não copie exemplos idênticos entre os conjuntos.
- Formato JSONL: um objeto por linha, com campos string "instruction" e "response"; campos adicionais de origem e tópico são permitidos.
- Todos os exemplos SFT devem caber no contexto de 256 bytes/tokens, incluindo prompt e resposta. O script rejeita os maiores.
- Não confunda geração de texto plausível com código executável e correto. Inclua testes de unidade e casos de borda.
