# Painel de Horas — Fucape

Gera o painel de banco de horas a partir do cartão ponto do Secullum (`cartaoponto.xlsx`). Tem duas formas de uso:

- **CLI local** (`atualizar_painel.bat`) — gera o HTML e abre no navegador, só isso.
- **App web** (`iniciar_painel_web.bat`) — upload do xlsx pela tela, revisão, e um botão "Enviar" que publica no Netlify e manda e-mail (CEO + gestores), via Microsoft Graph API ou Outlook Desktop (à sua escolha).

Este guia cobre como instalar do zero numa máquina nova.

## Pré-requisitos

| Ferramenta | Versão | Pra quê |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.10 ou mais novo | Roda o painel e o app web |
| [Node.js](https://nodejs.org/) (inclui npm) | qualquer versão recente | Só pra instalar o Netlify CLI (só pro app web) |
| Conta [Netlify](https://www.netlify.com/) | plano gratuito serve | Publicar o painel (só pro app web) |
| App registration no Entra ID | — | Enviar e-mail via Microsoft Graph API — só se for usar `PAINEL_METODO_ENVIO=graph` |
| Outlook Desktop instalado e logado | — | Enviar e-mail via Outlook — só se for usar `PAINEL_METODO_ENVIO=outlook` |

No instalador do Python no Windows, marque **"Add python.exe to PATH"**.

## Instalação

1. Clonar/copiar este repositório pra máquina.

2. Criar e ativar um ambiente virtual (venv) na raiz do repositório — **não instale as dependências direto no Python global**:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```

   O prompt do terminal passa a mostrar `(.venv)` quando está ativado. A partir daqui, todo `python`/`pip` do resto deste guia é o do venv.

3. Instalar as dependências Python:

   ```
   pip install -r requirements.txt
   ```

   Os `.bat` de entrada (`atualizar_painel.bat`, `iniciar_painel_web.bat`, `iniciar_painel_web_silencioso.bat`) já chamam `.venv\Scripts\python.exe` diretamente — não precisam do venv ativado pra rodar, só que a etapa acima já tenha sido feita uma vez.

4. **Só necessário se for usar o app web** (publicar no Netlify + mandar e-mail — pule pra "CLI local" abaixo se só quiser gerar o HTML):

   a. Instalar o Netlify CLI:

      ```
      npm install -g netlify-cli
      ```

      No Windows, se depois disso o comando `netlify` não for reconhecido num terminal novo, a pasta do npm global (`%AppData%\npm`) não está no PATH — adicione manualmente em Configurações > Variáveis de Ambiente, ou rode `setx PATH "%PATH%;%AppData%\npm"` e abra um terminal novo.

   b. Fazer login e linkar o site:

      ```
      netlify login
      netlify init
      ```

      `netlify init` cria (ou linka) um site Netlify e salva a associação em `.netlify/` dentro da pasta do repositório — o `deploy_netlify.py` depende disso pra saber pra onde publicar.

   c. Escolher como o e-mail vai ser enviado — `PAINEL_METODO_ENVIO=graph` (default) ou `PAINEL_METODO_ENVIO=outlook`:

      - **`graph`**: registrar um aplicativo no Entra ID (Azure Portal → App registrations → New registration), conceder a permissão de aplicativo `Mail.Send` no Microsoft Graph com consentimento de admin, e criar um segredo de cliente (Certificates & secrets). Pedir ao admin de M365 pra criar a caixa compartilhada que vai enviar os e-mails (ex.: `relatorios@fucape.br`) e conceder a esse aplicativo permissão pra enviar como essa caixa.
      - **`outlook`**: não precisa de nenhum cadastro — só o Outlook Desktop instalado e logado na conta que vai mandar os e-mails, na mesma máquina que roda o app web. Usa `pywin32` (já incluso no `requirements.txt`) pra automatizar o Outlook.

   d. Copiar `.env.example` para `.env` e preencher com os valores reais:

      ```
      copy .env.example .env
      ```

      Variáveis:
      - `PAINEL_CEO_EMAIL` — e-mail de quem recebe o painel geral
      - `PAINEL_METODO_ENVIO` — `graph` ou `outlook` (ver passo c)
      - `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` — só se `PAINEL_METODO_ENVIO=graph`, do app registration do passo (c)
      - `GRAPH_REMETENTE` — opcional, só pro método `graph` (default `relatorios@fucape.br`)
      - `PAINEL_MODO_TESTE` — opcional, deixe comentada; só descomente pra testar o botão Enviar sem publicar/mandar e-mail de verdade

      `.env` nunca deve ser commitado (já está no `.gitignore`).

## Como rodar

### CLI local (só gerar o HTML, sem publicar nem enviar e-mail)

1. Colocar o `cartaoponto.xlsx` exportado do Secullum na pasta `extratos/`.
2. Rodar `atualizar_painel.bat` (duplo clique). Ele pega o `.xlsx` mais recente da pasta, gera o painel em `painel/` e abre no navegador.

### App web (upload, revisão, publicar e notificar)

- `iniciar_painel_web.bat` — abre um terminal (mostra os logs) e o navegador em `http://127.0.0.1:8000`.
- `iniciar_painel_web_silencioso.bat` — mesma coisa, mas sem janela de terminal (roda em segundo plano).

Em ambos: sobe o `.xlsx`, revisa o preview, configura o e-mail dos gestores por departamento (se ainda não configurado) e clica **Enviar**. O servidor fecha sozinho quando a aba do navegador é fechada — não precisa lembrar de fechar nada manualmente.

## Testes

Com o venv ativado:

```
python -m pytest -q
```

Ou sem ativar, direto:

```
.venv\Scripts\python.exe -m pytest -q
```

Use sempre `python -m pytest`, **não** `pytest` sozinho — nesse projeto o `pytest` direto não encontra os módulos (`painel_horas`, `webapp`) porque a raiz do repositório não entra no `sys.path` automaticamente nesse modo.

## Estrutura de pastas (gitignored, criadas em uso)

- `.venv/` — ambiente virtual Python (criado na instalação, não commitado)
- `extratos/` — onde entra o `.xlsx` pro CLI local
- `painel/` — saída do CLI local
- `painel_web/` — saída do app web, uma subpasta por período (ex.: `painel_web/2026-06/`)
- `webapp_data/` — config de gestores (`config.json`), uploads temporários e log do modo silencioso
- `.netlify/` — associação do site criado pelo `netlify init`
