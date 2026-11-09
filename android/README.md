# Aplicativo Android Mikael AI

Este módulo Android é separado do backend/site: ele abre a interface web publicada em uma WebView segura e adiciona integração nativa de notificações para trabalhos prolongados. Os arquivos do site e o serviço Render não são alterados por esse módulo.

## Compilar APK pelo celular

1. Abra a branch `feature/self-hosted-ai-engine` no GitHub.
2. Entre em **Actions** e abra **Build Mikael AI Android APK**.
3. Toque em **Run workflow** (ou aguarde o workflow iniciar após uma alteração em `android/`).
4. Quando terminar, abra a execução e baixe o artefato `mikael-ai-android-debug`.

O artefato é um APK de depuração, não um APK assinado para publicação na Play Store.

## Notificações de trabalho

O app observa as rotas de trabalho prolongado da Mikael AI. Quando a rota de início confirma uma tarefa em execução, inicia um serviço Android em primeiro plano com notificação persistente. O app mantém o estado visível ao alternar para segundo plano para não disparar a pausa automática que existe na interface web. Quando a API informa conclusão ou falha, a notificação persistente é removida e uma notificação final é exibida.

O Android pode exigir que o usuário permita notificações. Fabricantes também podem aplicar restrições próprias de bateria. O serviço de notificação não transforma tarefas comuns de chat em tarefas de segundo plano: a integração cobre o recurso de **Trabalho prolongado** que já existe no backend.

## Modos de execução

O backend da branch suporta um endpoint de inferência próprio por configuração de servidor (`LLM_PROVIDER=local`). Isso é diferente de executar o modelo dentro do aparelho. A interface Android atual ainda usa a API hospedada e **não inclui um runtime de modelo local**. Não selecione nem anuncie o modo “No dispositivo” como funcional até que um runtime Android compatível seja integrado e testado no aparelho-alvo.

## Segurança e limitações

- A WebView só mantém navegação dentro de `https://mikael-ai.onrender.com`; links externos são abertos fora do app.
- JavaScript é necessário porque a interface existente depende dele; acesso a arquivos locais da WebView fica desativado.
- O serviço Android não garante execução se o usuário forçar a parada do app, revogar permissões ou se o fabricante encerrar o processo.
- O trabalho prolongado é executado pelo backend. A notificação é apenas o acompanhamento nativo no Android.
- Teste em aparelho real antes de considerar o APK pronto para uso diário.
