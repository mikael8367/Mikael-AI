# Dados de treinamento

## Corpus de programação da Mikael AI V1
- programming_train.jsonl: 384 exemplos autorais em português.
- programming_val.jsonl: 25 exemplos para escolher o melhor checkpoint.
- programming_test.jsonl: 18 exemplos isolados para avaliação final.
- O conjunto inclui Java (80), C++ (83), Python, JavaScript, Kotlin, C#, SQL, Git, HTML, CSS, algoritmos, estruturas de dados, APIs, segurança, testes e depuração.
- O corpus inicial é didático e pequeno; não representa conhecimento profissional nem substitui milhares de exemplos revisados, exercícios completos, testes executáveis e benchmarks.

## Regras para novos dados
- Use textos e exemplos que você criou ou tem autorização para usar.
- Não inclua senhas, chaves de API, dados pessoais, conversas privadas ou material protegido sem permissão.
- Separe treino, validação e teste por documento/origem, não apenas por linhas aleatórias, para reduzir vazamento.
- Revise manualmente precisão, português, código, segurança e resultado esperado.
- Não copie exemplos idênticos entre os conjuntos.
- Formato JSONL: um objeto por linha, com campos string "instruction" e "response"; campos adicionais de origem e tópico são permitidos.
- Todos os exemplos SFT devem caber no contexto de 256 bytes/tokens, incluindo prompt e resposta. O script rejeita os maiores.
- Não confunda geração de texto plausível com código executável e correto. Inclua testes de unidade e casos de borda.
