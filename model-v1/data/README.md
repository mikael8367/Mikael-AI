# Dados de treinamento

- Use textos e exemplos que você criou ou tem autorização para usar.
- Não inclua senhas, chaves de API, dados pessoais, conversas privadas ou material protegido sem permissão.
- Separe treino e validação por documento/origem, não apenas por linhas aleatórias, para reduzir vazamento entre conjuntos.
- Revise manualmente precisão, português, código e segurança.
- train_examples.jsonl é somente um pequeno exemplo de formato, não um corpus suficiente para treinar um assistente útil.
- Formato JSONL: um objeto por linha, com campos string "instruction" e "response".
- Prepare: python dataset_tools.py data/train_examples.jsonl data/train/examples.txt
- Para validação, prepare outro arquivo independente em data/val/.
- O treinador atual usa previsão do próximo byte/token em texto concatenado; isso ainda não é um treinamento supervisionado completo de chat com mascaramento de loss. A próxima evolução deve implementar instruction fine-tuning com rótulos apenas na resposta e separação explícita de turnos.
