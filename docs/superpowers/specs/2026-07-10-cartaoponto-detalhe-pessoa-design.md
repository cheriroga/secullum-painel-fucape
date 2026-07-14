# Cartão Ponto como fonte de verdade + Página de detalhe por colaborador

Data: 2026-07-10

## Objetivo

Substituir `ExtratoBancoHoras.xlsx` por `cartaoponto.xlsx` (cartão ponto do Secullum, batida a batida) como única fonte de dados do painel, e adicionar uma página por colaborador com o detalhe completo do ponto: todas as batidas, resumo mensal, resumo semanal e destaques (melhor/pior dia, semana, mês). Clicar no nome de um colaborador elegível em qualquer página de departamento leva pra essa página.

Isso substitui o design anterior (`2026-07-10-painel-horas-fucape-design.md`) na parte de fonte de dados e classificação — o restante daquele documento (layout geral, KPIs, hero gauge, agrupamento CSC, arquitetura Jinja2, distribuição por e-mail) continua valendo e não é repetido aqui.

## Fonte de dados

`cartaoponto.xlsx` (exportado do Secullum Ponto Web), colocado em `extratos/` (mesma pasta e mesmo mecanismo de "pega o xlsx mais recente por data de modificação" já existente). O antigo `ExtratoBancoHoras.xlsx` e o parsing dele saem de uso — código do parser antigo é removido, não fica morto ao lado do novo.

Estrutura real do arquivo: 1 sheet, 1 bloco por colaborador (tamanho do bloco varia com o período coberto — ver detecção em "Modelo de dados"), sem os marcadores textuais (`NOME:`, `PERÍODO`) que o extrato antigo usava. Cada bloco contém:

- Cabeçalho: nome, função, departamento, admissão. Existe também um campo **Inscrição** no arquivo, mas ele vem `ISENTO` para os 42 colaboradores do arquivo real sem exceção — não discrimina nada, não é usado pra classificação (ver seção de Cálculos).
- Tabela de horário padrão semanal (Ent/Sai esperados por dia da semana) — não usada no painel, ignorada.
- Linha `Totais` (período).
- 1 linha por dia calendário do período: `Data | Ent.1 | Saí.1 | Ent.2 | Saí.2 | Ent.3 | Saí.3 | Ex50% | Atras. | BTotal | ExNot`.
  - Entrada/saída: hora (`timedelta`) ou um código de status cobrindo o dia inteiro ou só um par Ent/Saí: `FOLGA`, `FALTA`, `Feriado`/`FERIADO`, `C. CONF`, `Afastam`, `FÉRIAS`, `ATEST`, `ABONO`, `COMP`, `EXTERNO`.
  - `BTotal`: saldo do dia, string assinada `"+HH:MM"`/`"-HH:MM"` (não é o mesmo formato do extrato antigo, que vinha majoritariamente como `timedelta` com string só no caso negativo).
  - Dias com código de status (sem batida real) não têm `BTotal` numérico — contam como 0 no saldo e ficam fora do cálculo de melhor/pior dia.

O arquivo pode cobrir 1 mês ou vários meses no mesmo export — o parsing não assume um tamanho de período fixo, só agrupa os dias que encontrar por mês/semana. "Relatório mensal" aqui quer dizer a UI se organiza por mês, não que o arquivo de entrada é sempre 1 mês.

## Modelo de dados (`parser.py`)

- `Dia`: `data`, `dia_semana`, batidas (`ent1..sai3`, cada uma hora ou código de status), `ex50_min`, `atraso_min`, `btotal_min` (int, signed, `None` se não houver — dia de status), `exnot_min`.
- `Colaborador`: `nome`, `funcao`, `admissao: date | None`, `departamento`, `dias: list[Dia]`. Substitui o antigo `meses: list[Mes]` — `Mes`/semana viram agregações derivadas, não dado bruto do xlsx.
- `ler_colaboradores()`: os blocos **não têm tamanho fixo** — o tamanho varia com o período coberto (confirmado: um arquivo com ~190 dias por colaborador dá blocos de 216 linhas, mas isso é o período deste arquivo, não uma constante do formato). Detecção por marcador, igual em espírito ao parser antigo: escaneia coluna 1 procurando célula `"Nome"` (bate exato, sem prefixo `NOME:`) pra abrir um bloco. Campos de cabeçalho ficam em offsets fixos relativos à linha do `"Nome"` (confirmado no arquivo real):
  - `Nome` → offset 0 (nome no col 2)
  - `Inscrição` → offset -2 (não usado, ver acima)
  - `Admissão` → offset +2 (valor direto no col 5, sem prefixo `"ADMISSÃO:"` como no extrato antigo)
  - `Função` → offset +3 (valor direto no col 2)
  - `Departamento` → offset +4 (valor direto no col 2)
  - Cabeçalho da tabela diária (`"Data"` no col 1) e linha `"Totais"` logo abaixo aparecem 5-10 linhas depois de `Departamento` — busca sequencial igual ao parser antigo faz pra `PERÍODO`.
  - Linhas diárias começam logo após `Totais` e continuam enquanto o col 1 for uma string no formato `"DD/MM/AAAA - Xxx"` (regex `^\d{2}/\d{2}/\d{4} - `) — para no primeiro valor que não bate (linha em branco ou legenda), o que funciona pra qualquer tamanho de período (1 mês ou vários) sem depender de contagem fixa de linhas.
  - Bloco sem `"Nome"` reconhecível, ou sem `Admissão`/`Departamento` no offset esperado → mesmo fallback do parser antigo (aviso no console, "Sem Departamento").

`horas.py`: `parse_horas` ganha suporte ao formato `"+HH:MM"` explícito (além do `"-HH:MM"` e `timedelta` que já suportava).

## Cálculos e classificação (`calculos.py`)

- **Saldo bruto do colaborador** = soma de `btotal_min` de todos os `dias` (mesmo número que o saldo do extrato antigo — confirmado pelo usuário que BTotal acumulado bate com o saldo já exibido hoje).
- **Fora da base / não elegível**: colaborador sem nenhum dia com batida real (nenhum `Dia` do período tem `ent1`/`ent2`/`ent3` como hora — todos são código de status ou vazio). Substitui a heurística antiga (débito ≥ 300h e crédito ≤ 5% do débito) e a correção por data de admissão — ambas removidas, esse critério já é direto e não depende de quando a pessoa foi admitida.
  - Validado nos dados reais: 8 dos 42 colaboradores do arquivo têm 0/190 dias com batida (só débito automático o período inteiro) — exatamente o grupo que a heurística antiga capturava (ex: débitos de -422h/-387h/-360h). O flag `Inscrição` do arquivo foi descartado como critério — vem `"ISENTO"` pros 42 colaboradores sem exceção, não discrimina nada (provavelmente status fiscal/sindical, não tem relação com isenção de bater ponto).
- `dept_label()` (agrupamento CSC: Controladoria+Administrativo+Financeiro) mantido sem mudança.
- Agregações novas por colaborador, usadas na página de pessoa:
  - Resumo mensal: soma de `btotal_min` por mês.
  - Resumo semanal: soma de `btotal_min` por semana (segunda a domingo, seguindo a mesma convenção `SEG..DOM` do arquivo).
  - Destaques: melhor/pior dia (maior/menor `btotal_min` entre dias com valor numérico), melhor/pior semana, melhor/pior mês.

## Página de pessoa

Novo template (`pessoa.html.j2`, mesma linguagem visual dark theme do restante), gerado em `painel/deptos/pessoas/<slug>.html` — um por colaborador elegível (tem ao menos 1 dia com batida real no período). Colaboradores fora da base não ganham página (nome permanece sem link onde aparecem).

Estrutura:

1. Header: nome, função, departamento, admissão, período coberto pelo arquivo.
2. Cards de destaque: saldo total, melhor dia, pior dia, melhor semana, pior semana, melhor mês, pior mês.
3. 3 abas trocáveis via JS vanilla (mesmo padrão dos filtros Todos/Só credores/Só devedores já usado no ranking — `template.py`), só uma visível por vez:
   - **Resumo mensal**: tabela mês × saldo.
   - **Semanal**: tabela semana × saldo.
   - **Diário completo**: tabela com todas as colunas cruas (Data, Ent.1–Saí.3, Ex50%, Atras., BTotal, ExNot), código de status no lugar da hora quando aplicável.

## Navegação

Nome do colaborador vira link `<a href="pessoas/<slug>.html">` em toda página de departamento (ranking) e no `index.html` geral — mesmo colaborador, mesma página, então o link vale nos dois lugares. Nomes na tabela "fora da base" continuam sem link (não têm página). `slug.py` reaproveitado sem mudança.

## Erros e casos-limite

- Bloco sem `Nome` reconhecível no offset esperado → aviso no console com a posição, pula o bloco, não trava o script inteiro.
- Dia com código de status parcial (ex: `ATEST` só em Ent.2/Saí.2, resto com hora real) → parser trata célula por célula, não assume o dia inteiro como status.
- Dias sem `BTotal` numérico → contam 0 no saldo, ficam fora do cálculo de melhor/pior dia.
- Semana = segunda a domingo (segue a abreviação `SEG..DOM` do próprio arquivo).
- `painel/deptos/pessoas/` recebe a mesma limpeza de página obsoleta que `deptos/` já tem hoje (remove htmls de quem saiu ou virou fora-da-base entre execuções).
- `extratos/` vazia ou sem `.xlsx` → mesmo comportamento atual (mensagem clara no console, não gera nada, não sobrescreve painel anterior).

## Testes

- `conftest.py`: builder de xlsx no formato cartaoponto (marcador `Nome` + linhas diárias no padrão `DD/MM/AAAA - Xxx`, tamanho de bloco variável) substitui o builder de extrato.
- `test_parser.py`/`test_calculos.py`: reescritos pro novo modelo (`Dia`/`Colaborador.dias`, classificação por "0 dias com batida real").
- Novo `test_pessoa.py`: render do template de pessoa + geração/limpeza de página em `gerar_painel`.
- `test_template.py`/`test_atualizar_painel.py`: cobrem também o link nome→pessoa nas páginas de depto e no index.

## Fora de escopo (YAGNI)

- Sem histórico/série temporal entre execuções — cada rodada é um snapshot do período do arquivo atual (mesma decisão do design anterior).
- Colunas `Ex50%`/`Atras.`/`ExNot` aparecem só como coluna crua na aba Diário completo — sem cálculo ou KPI novo em cima delas.
- Tabela de horário padrão semanal (Ent/Sai esperados por dia) do cabeçalho do bloco — não usada, ignorada no parsing.
