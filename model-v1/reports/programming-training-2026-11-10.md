# Relatório de treinamento — Mikael AI V1

**Data:** 10/11/2026  
**Workflow:** [Mikael AI V1 Programming Training](https://github.com/mikael8367/Mikael-AI/actions/runs/42742976139)  
**Commit usado pelo workflow:** `efd3f0b160bc0a5f638b69fe59a6efbb1fff2bda`  
**Dispositivo de treino:** CPU do GitHub Actions

## Dados
- Treino: 384 exemplos.
- Validação: 25 exemplos.
- Teste isolado: 18 exemplos.
- Foco: Java (80 exemplos) e C++ (83), com Python, JavaScript, Kotlin, C#, SQL, Git e fundamentos gerais.

## Execução
- Épocas executadas: 71 (limite configurado: 100).
- Melhor época: 56.
- Passos de otimização: 3.408.
- Early stopping: ativado após 15 épocas sem melhora da validação.

## Métricas
- Melhor loss de validação: **2,785875**.
- Loss no conjunto de teste: **2,812893**.

A loss é uma métrica de previsão de tokens. Ela não mede diretamente compilação, correção semântica, segurança, desempenho ou capacidade de resolver tarefas inéditas. O resultado é um primeiro ciclo de treinamento, não uma certificação de competência profissional.

## Checkpoint
O workflow publicou o checkpoint e o relatório como artefato:
- Artefato: `mikael-ai-v1-programming-checkpoint`
- Tamanho do ZIP: aproximadamente 9 MB.
- [Abrir o workflow e baixar o artefato](https://github.com/mikael8367/Mikael-AI/actions/runs/42742976139)
- Expiração do artefato: **10/12/2026**.

O checkpoint ainda precisa ser integrado/convertido para o runtime Android. Não é um APK e não foi instalado no aplicativo.
