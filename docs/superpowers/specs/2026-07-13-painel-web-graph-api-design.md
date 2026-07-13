# Protótipo local: app web + deploy Netlify + envio por Microsoft Graph API

Data: 2026-07-13

## Objetivo

Validar, com um protótipo 100% local, a transformação do gerador de painel (hoje um script CLI que produz HTML estático e abre no navegador local) num fluxo em que a responsável pelo Secullum sobe o `cartaoponto.xlsx`, revisa o painel gerado e, com um clique, publica o relatório e avisa CEO e gestores por e-mail com o link.

Este protótipo roda inteiro na máquina da responsável — sem servidor dedicado, sem autenticação na frente do relatório publicado. Server dedicado, login (Cloudflare Access) e robustez de produção (retry, auditoria) ficam fora de escopo aqui; ver "Fora de escopo".

## Arquitetura

Um único aplicativo Python local, iniciado por ela (`.bat` equivalente ao `atualizar_painel.bat` atual), que sobe um servidor web local (`localhost`) e abre o navegador nele — não precisa de infraestrutura além da máquina dela.

Componentes:

- **`painel_horas/`** — reaproveitado sem mudança de lógica (parser, cálculos, templates). Única alteração: a saída passa a ir para uma pasta por período (`painel/<periodo>/...`) em vez de sempre limpar e regravar `painel/`, para preservar histórico entre publicações (ver "Histórico").
- **`webapp/`** (novo) — servidor web local (FastAPI + uvicorn) com uma única página:
  - Seletor de arquivo → upload do `.xlsx`.
  - Ao subir o arquivo, roda o pipeline existente (`ler_colaboradores` → `montar_relatorio`/`montar_pessoa` → `render_pagina`/`render_pessoa`) e mostra o painel gerado na própria página (iframe apontando para os arquivos locais gerados).
  - Botão **Enviar**, com confirmação ("Vai publicar e notificar N destinatários — confirmar?").
  - Tela de configuração simples: mapa departamento → e-mail do gestor, persistido em `webapp/config.json`.
- **`deploy_netlify.py`** (novo) — publica a pasta do período gerado no Netlify via Netlify CLI (`netlify deploy --prod --dir=painel/<periodo>`), sob um caminho específico do período (ex.: site com subpastas `/2026-07/...`), preservando publicações anteriores.
- **`mailer_graph.py`** (novo) — chama a Microsoft Graph API (`POST /users/{remetente}/sendMail`) autenticando como aplicação registrada no Entra ID (client credentials, permissão de aplicativo `Mail.Send`), enviando pela caixa compartilhada `relatorios@fucape.br`. Mensagem curta + link do período publicado, um e-mail para o CEO e um para cada gestor configurado.

## Fluxo (ponta a ponta)

1. Responsável abre o app local (`localhost`) no navegador.
2. Sobe o `.xlsx` mais recente pelo seletor de arquivo, na mesma página (substitui a convenção atual de "pega o mais recente em `extratos/`" — agora é upload explícito).
3. Backend roda o pipeline existente, gera os HTML em `painel/<periodo>/`, e a página mostra o preview (index geral + navegação para departamentos/pessoas, igual ao gerado hoje).
4. Ela revisa no preview local.
5. Clica **Enviar** → confirma → backend:
   a. Publica `painel/<periodo>/` no Netlify (`deploy_netlify.py`).
   b. Envia e-mail via Graph API para o CEO e para cada gestor cadastrado (`mailer_graph.py`), com link para a versão publicada daquele período.
6. Página mostra confirmação com timestamp; se algum envio de e-mail falhar (token, permissão, endereço inválido), lista quais destinatários falharam e oferece reenviar só para esses.

## Histórico

Cada publicação vira uma versão própria por período (ex.: `/2026-07/`), sem sobrescrever publicações anteriores no Netlify — um link já enviado por e-mail continua válido depois de rodar o processo de novo em outro mês. Isso exige mudar `gerar_painel` para não limpar mais `painel/` inteiro a cada execução (comportamento atual), e sim escrever em uma subpasta nova nomeada pelo período do arquivo.

## Configuração departamento → gestor

Tela dentro do próprio app (não arquivo editado manualmente por terceiros): lista departamentos encontrados no `.xlsx` mais recente, campo de e-mail por departamento, botão salvar. Persistido em `webapp/config.json`. Usada só para montar a lista de destinatários no envio.

## Conteúdo do e-mail

Assunto + corpo curto (ex.: "Painel de horas — [período] disponível") com o link do painel publicado. Sem KPIs nem anexo no corpo — toda visualização acontece no link.

## Erros e casos-limite

- `.xlsx` inválido/corrompido ou sem colaboradores reconhecíveis → mensagem clara na página, não avança para preview nem habilita "Enviar".
- Falha no deploy Netlify (rede, CLI não autenticado) → mostra erro na página, **não** dispara os e-mails.
- Falha parcial no envio (alguns destinatários falham) → publicação já feita permanece válida; página lista quem falhou e permite reenviar só para os que falharam, sem re-publicar.
- Departamento sem e-mail de gestor configurado → alerta na tela de confirmação antes de enviar, permite prosseguir mesmo assim (ex.: setor sem gestor definido ainda) ou cancelar para completar a configuração primeiro.

## Testes

- Suite `pytest` existente (parser/cálculos/templates) não muda.
- Novo `test_webapp.py`: rotas de upload (valida rejeição de arquivo inválido), configuração (CRUD do mapa depto→e-mail), fluxo de envio com `deploy_netlify` e `mailer_graph` mockados (sem chamada real a Netlify/Graph API nos testes).
- `deploy_netlify.py`/`mailer_graph.py` isolados por trás de uma interface simples (função que recebe pasta/período, e-mails/link) para facilitar mock nos testes e trocar a implementação depois sem tocar no restante do app.

## Fora de escopo (YAGNI)

- Servidor de automação dedicado — cogitado, descartado por ora; a mesma arquitetura (app local) roda lá depois sem mudança de código, se o protótipo validar.
- Cloudflare Access ou qualquer autenticação na frente do relatório publicado no Netlify — protótipo de validação, sem controle de acesso pro link ainda.
- Pasta de rede compartilhada / watcher automático — descartado em favor do upload direto na página, mais intuitivo para usuária não técnica.
- Retry automático, log de auditoria de quem recebeu o quê e quando, geração de PDF alternativo — adiar para uma fase de produção, se o protótipo for aprovado.
- Suporte a múltiplos usuários/perfis no app local — só a responsável pelo Secullum usa, sem gestão de usuários.

## Verificação manual

Esta tarefa não possui testes automatizados — requer login real do Netlify CLI e registro real de aplicativo no Entra ID, que existem apenas no ambiente real da empresa (não na máquina de CI/dev que constrói este plano). A verificação deve ser feita manualmente pelo responsável antes de mostrar o protótipo ao CEO.

### Pré-requisitos (configurar uma única vez, fora do repositório)

1. Instalar o Netlify CLI (`npm install -g netlify-cli`) e rodar `netlify login` na máquina que executará este protótipo; criar um site Netlify uma vez (`netlify sites:create`) e anotar seu nome.

2. Registrar um aplicativo no Entra ID (Azure Portal → App registrations), conceder a permissão de aplicativo `Mail.Send` no Microsoft Graph com consentimento de admin e criar um segredo de cliente. Solicitar ao admin de M365 que crie a caixa de correio compartilhada `relatorios@fucape.br` se ela ainda não existir, e que conceda ao aplicativo permissão para enviar como essa caixa de correio (a permissão de aplicativo `Mail.Send` cobre isso por padrão em todo o locatário, a menos que o IT a restrinja — se restringir, usar uma `applicationAccessPolicy` limitada a essa caixa em vez de todo o locatário).

3. Definir variáveis de ambiente antes de executar: `PAINEL_CEO_EMAIL`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` (e opcionalmente `GRAPH_REMETENTE` se não usar o padrão `relatorios@fucape.br`).

### Passos de verificação manual

1. Executar `iniciar_painel_web.bat` (ou `python iniciar_painel_web.py`) — confirmar que o navegador abre em `http://127.0.0.1:8000/` mostrando o formulário de upload.

2. Subir um `cartaoponto.xlsx` real — confirmar que redireciona para `/preview`, mostra as contagens corretas e o iframe renderiza o painel real (ranking, cartões de departamento, abas funcionais "mensal/semanal/diário" em uma página de pessoa).

3. Preencher o e-mail do gestor em pelo menos um departamento no formulário de configuração, clicar em "Salvar configuração" — confirmar que redireciona de volta para `/preview` com o valor persistido (recarregar a página).

4. Clicar em "Enviar", confirmar no diálogo `confirm()` do JS, confirmar que a página de resultado mostra "Publicado em https://.../<periodo>/" e "Todos os envios OK".

5. Abrir o link impresso em um celular com dados móveis (não Wi-Fi da empresa) — confirmar que o painel carrega e as abas da página de pessoa ainda funcionam (este é o problema do SharePoint que este design foi escolhido para evitar — verificar que realmente não acontece no Netlify).

6. Verificar que a caixa de correio do CEO/gestor de teste recebeu realmente o e-mail com o link correto.

7. Re-executar todo o fluxo com um arquivo de outro período — confirmar que o link do período anterior (passo 5) ainda resolve depois desse segundo deploy (esta é a garantia de preservação de histórico da especificação).
