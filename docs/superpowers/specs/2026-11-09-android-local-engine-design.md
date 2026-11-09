# Mikael AI Android — motor de inferência local e controle de RAM

Data: 2026-11-09  
Branch: `feature/self-hosted-ai-engine`

## Objetivo

Transformar o aplicativo Android em um app nativo e exclusivamente offline: executar conversas de texto com um modelo GGUF diretamente no aparelho, usando llama.cpp compilado como biblioteca nativa, com limite de memória configurável. O app não deve carregar o site nem depender do Render, OpenRouter ou de qualquer serviço de IA remoto.

## Estado atual observado

- O Android é uma Activity com WebView apontando para `https://mikael-ai.onrender.com`.
- O envio de mensagens usa `POST /api/chat/stream` e o servidor salva o histórico no banco.
- O módulo Android atual não possui runtime de inferência local, armazenamento local de conversas nem preferências de RAM.
- O backend `LLM_PROVIDER=local` existente significa um servidor remoto compatível com API OpenAI, não inferência no telefone.
- O app tem um workflow de APK debug, mas ainda não foi validado por build Android real.

## Requisitos e critérios de aceitação

1. A opção Cloud continua usando o site e seu backend atuais sem alteração de comportamento.
2. A opção No dispositivo executa inferência de texto via llama.cpp no próprio processo/app Android, sem enviar o texto da conversa para o endpoint de chat Cloud.
3. O app permite escolher limites de memória de 512 MiB, 768 MiB, 1 GiB, 1,5 GiB e 2 GiB; opções indisponíveis para o aparelho ficam desabilitadas ou são recusadas com explicação.
4. O limite é aplicado ao orçamento do runtime (modelo, contexto/KV cache e buffers sob controle do motor), não apresentado como limite absoluto de todo o processo Android.
5. Antes de carregar, o app verifica memória disponível, tamanho do modelo e orçamento configurado; se não couber, não tenta carregar e explica como reduzir modelo/contexto ou limite.
6. Modelos são obtidos de fontes configuráveis/identificadas, baixados para armazenamento privado do app, com tamanho, progresso, espaço livre e integridade verificados. Download interrompido pode ser retomado ou reiniciado com segurança.
7. O modelo é descarregado ao trocar de modelo/modo, ao sair do modo local quando apropriado, e quando o app precisa liberar recursos; erros de JNI não derrubam silenciosamente a UI.
8. Conversas locais não são enviadas ao backend Cloud. O histórico local deve ser armazenado no aparelho; conversas Cloud permanecem no servidor.
9. O app não declara suporte local a visão, upload multimodal, pesquisa web ou ferramentas externas até cada capacidade ter integração local e teste próprios.
10. A interface atual do site e os arquivos `app/static/*` não são alterados. Todo trabalho fica na branch isolada.

## Abordagens consideradas

- **llama.cpp nativo via JNI/NDK (escolhida):** integração direta com o Android, sem servidor HTTP adicional; melhor controle de memória e ciclo de vida. Exige CMake/NDK, ABI correta e testes de compatibilidade.
- Servidor local separado: adiciona processo/servidor e overhead de memória, pior para aparelhos de entrada.
- Manter somente WebView/Cloud: não atende ao requisito de inferência no dispositivo.

## Decisões de produto e implementação

- O aplicativo Android terá uma tela nativa de Configurações acessível pelo app, sem modificar o site. Ela controla modo Cloud/No dispositivo, orçamento de RAM, modelo instalado e contexto.
- O chat Cloud continua na WebView. No modo local, o app apresentará uma experiência de chat local nativa ou uma ponte isolada que não encaminhe mensagens para `/api/chat/stream`; a decisão final deve privilegiar isolamento e persistência offline, não interceptação frágil de rede.
- Primeira entrega local: conversa de texto, streaming de tokens, interrupção de geração, histórico local e troca/descarga de modelo. Upload/análise de arquivos e imagens, visão, ferramentas e pesquisa web ficam explicitamente fora da primeira fatia até serem integrados com segurança.
- Começar com um GGUF pequeno e quantizado (classe 0.5B/1B, Q4), mas não fixar URL ou licença sem validar a fonte oficial, checksum, licença e compatibilidade do arquivo.
- RAM será configurável em MiB, mas o valor máximo real será limitado pela memória disponível e pelo orçamento seguro calculado no aparelho. Nunca reservar toda a RAM física.
- Configurações e histórico ficam no armazenamento privado do app. O usuário pode apagar os modelos baixados e o histórico pelas configurações. A conexão com a internet só pode ser usada para baixar modelos e atualizações explicitamente solicitadas; nunca para enviar prompts ou respostas.

## Segurança, privacidade e riscos

- Não carregar bibliotecas nativas ou modelos de fontes sem procedência; validar checksum e arquitetura ABI.
- Limitar tamanho do modelo, contexto, threads e buffers; tratar OOM, cancelamento, app em segundo plano e rotação/recriação da Activity.
- Não registrar prompts, respostas, tokens ou caminhos privados em logs.
- Não passar conteúdo local para a WebView ou backend Cloud por padrão.
- O modelo pode ser lento ou não caber em aparelhos com pouca RAM; a UI deve informar requisitos reais sem prometer desempenho.
- O Galaxy A12 é um alvo de teste prioritário, mas a capacidade exata depende da RAM livre e das variantes do modelo.

## Fora de escopo nesta primeira entrega

- Treinar pesos de um modelo do zero.
- Garantir funcionamento de modelos grandes no Galaxy A12.
- Inferência local de visão, geração de imagens, pesquisa web e conectores MCP/GitHub.\n- Qualquer modo Cloud ou dependência do Render/OpenRouter.
- Alterar ou publicar o site, modificar o serviço Render, criar serviços pagos ou gerar APK assinado de loja.

## Plano de validação

- Testes unitários para orçamento de memória, seleção de modelo, validação de arquivo/checksum e estados do runtime.
- Testes Android para inicialização JNI, geração, cancelamento, descarregamento, troca de modo e recuperação após erro.
- Verificar que o app não contém WebView, chamadas de chat remotas, OpenRouter ou dependência do Render; prompts e respostas permanecem no aparelho.
- Build debug em CI com NDK/CMake e teste em aparelho Android ARM64 real; registrar explicitamente limitações se não houver aparelho disponível.
- Revisão final de segurança, concorrência, ciclo de vida Android, vazamentos de memória, falhas de download e regressões Cloud.
