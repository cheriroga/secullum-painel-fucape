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
