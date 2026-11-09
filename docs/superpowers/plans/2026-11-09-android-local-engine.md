# Mikael AI Android Local Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar no Android uma opção Cloud/No dispositivo, chat offline com llama.cpp e orçamento configurável de RAM, preservando o site e o backend atuais.

**Architecture:** O Android passa a ter uma navegação nativa simples com abas inferiores para Cloud, Local e Configurações. Cloud continua abrindo a WebView existente; Local usa JNI para chamar llama.cpp diretamente, com modelos GGUF no armazenamento privado e histórico local; Configurações controla modo, modelo, contexto e orçamento de memória. A compilação nativa ARM64 será feita com CMake/NDK no workflow GitHub Actions.

**Tech Stack:** Kotlin, Android SDK (minSdk 26), Android NDK, CMake, C++ llama.cpp C API, JNI, GGUF, Gradle, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-09-android-local-engine-design.md`

## Global Constraints

- Alterar somente a branch `feature/self-hosted-ai-engine`.
- Não modificar `app/static/*`, o site publicado, o serviço Render, banco de dados ou configuração de produção.
- Cloud deve continuar usando `https://mikael-ai.onrender.com` e `/api/chat/stream` sem mudança de contrato.
- ABI inicial: `arm64-v8a`; Android mínimo: API 26.
- O modo local não pode enviar prompts/histórico para o endpoint Cloud.
- Limites configuráveis: 512 MiB, 768 MiB, 1024 MiB, 1536 MiB e 2048 MiB, limitados pelo orçamento seguro estimado do aparelho.
- Limite de RAM é orçamento do runtime, não promessa de limitar a memória total do processo Android.
- Primeira entrega local suporta texto; visão, imagem, busca web e ferramentas externas não podem aparecer como recursos locais funcionais.
- Não criar serviços pagos, não fazer deploy e não gerar APK manualmente nesta etapa.

## Review Focus

- Modelo GGUF maior que o orçamento ou arquivo truncado: rejeitar antes de chamar JNI e informar motivo.
- Memória livre insuficiente após o app ficar em segundo plano: falhar de forma recuperável, sem travar ou encerrar a Activity.
- Troca rápida Cloud/Local durante geração: cancelar geração e descarregar o modelo sem deixar ponteiro nativo inválido.
- Download interrompido, sem espaço ou com checksum incorreto: não marcar modelo como instalado nem carregar arquivo parcial.
- Rotação/recriação da Activity ou retorno do processo: recuperar estado persistido sem duplicar geração ou perder histórico local.

---

### Task 1: Base nativa llama.cpp e contrato JNI

**Files:**
- Create: `android/app/src/main/cpp/CMakeLists.txt`
- Create: `android/app/src/main/cpp/mikael_llama_jni.cpp`
- Create: `android/app/src/main/java/com/mikael/ai/LocalInferenceEngine.kt`
- Modify: `android/app/build.gradle.kts`
- Modify: `.github/workflows/android-apk.yml`
- Test: `android/app/src/test/java/com/mikael/ai/NativeConfigTest.kt`

**Interfaces:**
- `LocalInferenceEngine.load(modelPath: String, contextTokens: Int, memoryBudgetBytes: Long): Result<Unit>`
- `LocalInferenceEngine.generate(prompt: String, onToken: (String) -> Unit): Result<String>`
- `LocalInferenceEngine.cancel()`
- `LocalInferenceEngine.unload()`
- JNI deve serializar operações de load/generate/cancel/unload e nunca expor ponteiros C++ à camada Kotlin.

- [ ] Adicionar testes de contrato para estados unloaded/loading/ready/generating/error e rejeição de parâmetros inválidos.
- [ ] Executar os testes e confirmar falha inicial pelo contrato ausente.
- [ ] Fixar uma versão/tag imutável do llama.cpp e integrar via CMake FetchContent; compilar apenas `arm64-v8a`, com opções Android portáveis e sem OpenMP.
- [ ] Implementar JNI com RAII, mutex, cancelamento e liberação idempotente de contexto/modelo.
- [ ] Configurar externalNativeBuild e NDK no workflow de APK.
- [ ] Rodar testes Kotlin e build nativo debug; registrar falhas de ambiente separadamente.

### Task 2: Orçamento de RAM e preferências Android

**Files:**
- Create: `android/app/src/main/java/com/mikael/ai/MemoryBudget.kt`
- Create: `android/app/src/main/java/com/mikael/ai/AppPreferences.kt`
- Test: `android/app/src/test/java/com/mikael/ai/MemoryBudgetTest.kt`

**Interfaces:**
- `MemoryBudget.availableBytes(activityManager): Long`
- `MemoryBudget.safeBudgetBytes(availableBytes: Long, selectedLimitBytes: Long): Long`
- `MemoryBudget.validateModel(modelBytes: Long, contextTokens: Int, budgetBytes: Long): BudgetResult`
- `AppPreferences.executionMode: ExecutionMode`
- `AppPreferences.memoryLimitBytes: Long`

- [ ] Escrever testes para cada limite (512/768/1024/1536/2048 MiB), valores inválidos, RAM livre baixa e estimativa de contexto/cache.
- [ ] Verificar RED para os testes de orçamento.
- [ ] Implementar cálculo conservador usando memória disponível do Android, reserva para o sistema/app, tamanho do modelo, contexto/KV cache e margem para buffers.
- [ ] Persistir preferências em armazenamento privado; nunca permitir valor arbitrário acima das opções aceitas.
- [ ] Rodar testes unitários e revisar overflow, conversões MiB/bytes e limites inferiores/superiores.

### Task 3: Catálogo, download e integridade de modelos GGUF

**Files:**
- Create: `android/app/src/main/java/com/mikael/ai/ModelRepository.kt`
- Create: `android/app/src/main/java/com/mikael/ai/ModelDownloadWorker.kt`
- Create: `android/app/src/main/java/com/mikael/ai/InstalledModel.kt`
- Test: `android/app/src/test/java/com/mikael/ai/ModelRepositoryTest.kt`

**Interfaces:**
- `ModelRepository.listInstalled(): List<InstalledModel>`
- `ModelRepository.verify(model: InstalledModel): ModelVerification`
- `ModelRepository.delete(modelId: String)`
- `ModelDownloadWorker.enqueue(model: ModelDescriptor)`

- [ ] Testar metadados inválidos, espaço insuficiente, download interrompido, tamanho divergente e checksum incorreto.
- [ ] Verificar RED antes da implementação.
- [ ] Definir um catálogo inicial pequeno somente após validar repositório oficial, licença, tamanho, arquitetura e checksum do GGUF.
- [ ] Baixar para diretório privado usando arquivo temporário, progresso, checagem de espaço e SHA-256; promover para instalado somente após validação.
- [ ] Permitir cancelar/remover download e excluir modelo instalado, sem apagar histórico de conversas.
- [ ] Rodar testes e verificar que arquivos parciais nunca aparecem como modelos prontos.

### Task 4: Histórico e serviço de chat local

**Files:**
- Create: `android/app/src/main/java/com/mikael/ai/LocalConversationStore.kt`
- Create: `android/app/src/main/java/com/mikael/ai/LocalChatController.kt`
- Create: `android/app/src/test/java/com/mikael/ai/LocalConversationStoreTest.kt`
- Create: `android/app/src/test/java/com/mikael/ai/LocalChatControllerTest.kt`

**Interfaces:**
- `LocalConversationStore.create(): LocalConversation`
- `LocalConversationStore.append(conversationId: String, message: LocalMessage)`
- `LocalConversationStore.list(): List<LocalConversation>`
- `LocalChatController.send(conversationId: String, prompt: String, onToken: (String) -> Unit)`
- `LocalChatController.cancel()`

- [ ] Testar persistência após recriação, mensagens vazias, falha de inferência, cancelamento e isolamento por conversa.
- [ ] Verificar RED para os testes de persistência e roteamento.
- [ ] Implementar armazenamento local privado sem compartilhar tabela/API do servidor.
- [ ] Conectar o controller ao contrato JNI; transmitir tokens incrementalmente e permitir parar geração.
- [ ] Garantir por teste que o fluxo local não chama `/api/chat/stream` nem qualquer endpoint de chat.
- [ ] Rodar testes e revisar concorrência entre geração, cancelamento e troca de conversa.

### Task 5: Navegação nativa, chat e configurações

**Files:**
- Create: `android/app/src/main/java/com/mikael/ai/AndroidAppController.kt`
- Create: `android/app/src/main/java/com/mikael/ai/LocalChatActivity.kt` (ou tela nativa equivalente dentro do shell)
- Create: `android/app/src/main/java/com/mikael/ai/SettingsScreen.kt`
- Modify: `android/app/src/main/java/com/mikael/ai/MainActivity.kt`
- Modify: `android/app/src/main/AndroidManifest.xml`
- Test: `android/app/src/test/java/com/mikael/ai/ExecutionModeTest.kt`

**Interfaces:**
- `ExecutionMode = CLOUD | ON_DEVICE`
- `AndroidAppController.selectMode(mode: ExecutionMode)`
- `AndroidAppController.send(prompt: String)`
- `SettingsScreen` expõe modo, orçamento RAM, modelo instalado, contexto e status de memória.

- [ ] Testar roteamento: Cloud usa WebView; ON_DEVICE usa somente LocalChatController.
- [ ] Testar alternância durante geração, ausência de modelo e modelo que excede orçamento.
- [ ] Implementar navegação inferior com abas Cloud, Local e Configurações, feedback de carregamento e animações leves.
- [ ] Construir tela de configurações com opções de RAM, seleção/instalação de modelo, espaço usado, memória disponível e descarregar modelo.
- [ ] Implementar chat local com streaming, enviar, cancelar, estados vazios/erro e histórico local.
- [ ] Manter navegação Cloud isolada e confirmar que a interface web e seus arquivos não mudaram.
- [ ] Rodar testes de roteamento e revisar acessibilidade/toque em telas pequenas.

### Task 6: Integração, build e auditoria profunda

**Files:**
- Modify: `android/README.md`
- Modify: `.github/workflows/android-apk.yml`
- Test: todos os testes Android e verificações do workflow.

- [ ] Rodar testes unitários, lint e build debug ARM64 com NDK/CMake no CI.
- [ ] Verificar logs de build, bibliotecas empacotadas, ABI e tamanho do APK.
- [ ] Auditar privacidade: prompts locais não saem do aparelho; logs não contêm prompt/token; Cloud continua com autenticação e host restrito.
- [ ] Auditar memória: load/unload repetido, contexto grande, pressão de memória, cancelamento e troca de modo.
- [ ] Auditar downloads: falha de rede, checksum, armazenamento cheio, retomada e exclusão.
- [ ] Revisar ciclo de vida Android, rotação, background, encerramento do processo e recuperação de estado.
- [ ] Atualizar README com instalação de modelos, limites conhecidos, recursos não suportados e procedimento de build pelo celular.
- [ ] Comparar a branch com `main` e confirmar que nenhum arquivo do site/produção foi alterado.
- [ ] Não declarar pronto para uso no aparelho sem teste real em Android ARM64; separar claramente resultado de CI e teste físico.

## Ordem e dependências

Task 1 e Task 2 são a base; Task 3 depende do contrato de orçamento e do armazenamento; Task 4 depende do JNI; Task 5 integra as tarefas 2–4; Task 6 só ocorre após integração. Cada tarefa deve terminar com teste e revisão do diff antes da próxima.
