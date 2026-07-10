# Painel de Controle de Horas — FUCAPE Business School

Data: 2026-07-10

## Objetivo

Gerar, a partir do extrato do Banco de Horas do Secullum (xlsx), um painel executivo estático (HTML autossuficiente) igual ao artefato de referência (`claude-artifact-demo.mhtml`, artifact id `f1391c1e-7d6f-49a3-ba0e-59a5d07d4f51`), mais:

- uma página por departamento (mesmo layout, escopado), pra enviar aos gestores por e-mail
- correção interna de classificação "config/isento" usando data de admissão

Distribuição: `painel/index.html` vai pro CEO. Cada `painel/deptos/*.html` vai pro gestor daquele departamento. Tudo por e-mail, cada arquivo é autossuficiente (CSS+JS inline) — funciona anexado sozinho. O link departamento→página dentro do `index.html` só funciona se a pasta `deptos/` for enviada junto (aceitável, uso principal do CEO não depende disso).

## Fonte de dados

`ExtratoBancoHoras.xlsx` (exportado manualmente do Secullum Ponto Web). Estrutura real (Sheet1, ~1227 linhas, 44 blocos, 1 por colaborador):

```
EXTRATO DO BANCO DE HORAS
Período: 01/01/2026 até 09/07/2026.
(linha em branco)
EMPRESA: ... | CNPJ: ... | INSCRIÇÃO: ...
NOME: <nome> | Nº FOLHA: ... | Nº PIS/PASEP: ...
FUNÇÃO: <cargo> | C.T.P.S.: | ADMISSÃO: dd/mm/yyyy
DEPARTAMENTO: <depto>
OBSERVAÇÃO:
(linha em branco)
PERÍODO | TOTAL | CRÉDITO | DÉBITO | AJUSTE
01/01/2026 até 31/01/2026 | ... (repete por mês)
...
TOTAL | <soma> | <soma> | <soma> | <soma>
(linhas de assinatura, brancos)
```

Colunas de hora vêm como `datetime.timedelta` (openpyxl) ou string `-HH:MM` quando negativo (Excel não representa timedelta negativo). Parser trata os dois formatos, normaliza pra minutos assinados.

`Extrato do Banco de Horas.pdf` é o mesmo relatório em PDF — não é parseado, existe só como conferência visual/backup do RH.

## Cálculo

- **Saldo bruto do período** (mostrado): soma da coluna TOTAL de todos os meses do extrato, como já está no xlsx. É o número exibido em toda a UI (hero, KPIs, ranking, deptos).
- **Saldo do período trabalhado** (uso interno, não exibido como métrica separada): soma da coluna TOTAL só dos meses cujo início >= mês de admissão. Usado apenas para:
  - recalcular a flag "config/isento" (debito padrão >= 300h sem crédito correspondente), evitando falso positivo em quem foi admitido recentemente
  - aparecer como subtexto pequeno por colaborador dentro da página do depto (ex: `admitido 13/05/2026 · desde admissão: +6h03`) — não é card, não é KPI, não aparece no relatório geral

## Departamentos e agrupamento

Cada departamento distinto no xlsx vira 1 página, **exceto**: Controladoria + Administrativo + Financeiro, que são combinados em uma única página "Centro de Serviços Compartilhados" (CSC). Comercial permanece com página própria. Dentro da página CSC, cada colaborador mantém o nome do time original (Controladoria/Administrativo/Financeiro) como subtexto de rastreabilidade.

Se aparecer um departamento novo no xlsx que não existia antes, o script cria a página automaticamente (não precisa alterar código pra isso).

## Layout (idêntico ao artefato de referência + imagem de estilo fornecida)

Tema escuro. Estrutura, do topo pro rodapé:

1. **Header**: eyebrow "Fucape Business School · Extrato Secullum", título "Banco de Horas / Painel do CEO" (ou "/ Painel [Depto]" nas páginas de depto), meta (período, data de emissão, contagem de colaboradores/elegíveis).
2. **Hero gauge**: saldo líquido consolidado em destaque, nota de rodapé do hero, barra de gauge dividida (segmento negativo vermelho + positivo verde, largura proporcional), legenda com contagem de credores/devedores.
3. **KPIs** (4 cards, borda esquerda colorida): passivo de horas (verde), a receber (vermelho), concentração de risco (âmbar), registros não elegíveis (azul).
4. **Alerta** (caixa âmbar/oliva): nota de leitura de dado sobre os registros não elegíveis, só aparece se houver algum nesse escopo.
5. **Seção 01 — Ranking individual**: barras horizontais por colaborador (verde=credor, vermelho=devedor), filtros clicáveis Todos/Só credores/Só devedores (JS vanilla reimplementado — a cópia salva do artefato perdeu a lógica original).
6. **Seção 02 — Saldo por departamento** (só no `index.html`): grid de cards por depto com mini-barra e valor; nome do depto é link `<a href="deptos/<slug>.html">`.
7. **Seção 03 — Fora da base**: tabela dos registros "config/isento" (débito padrão sem batida real), recalculada com saldo do período trabalhado; some se vazia no escopo daquela página.
8. **Footer**: nota de metodologia + limite de leitura (mesmo texto do artefato original, adaptado ao escopo).

Cores/variáveis (`--pos` verde, `--neg` vermelho, `--amber`, `--blue`, `--ink`, `--mut`) recriadas visualmente a partir da imagem de referência anexada pelo usuário — CSS original do artefato não foi recuperável do `.mhtml` (só veio o HTML, a folha de estilo externa não foi salva). Espera-se uma rodada de ajuste fino de cor/contraste depois da primeira geração.

## Arquitetura

Python + template HTML autossuficiente (sem servidor, sem dependência pesada). Uma função de template (Jinja2) gera geral e todas as páginas de depto — muda só o conjunto de dados injetado e textos de escopo (contagem, título).

```
painel-horas/
├── atualizar_painel.bat       # duplo-clique, chama o .py
├── atualizar_painel.py        # script principal
├── extratos/                  # xlsx novo do Secullum entra aqui
│   └── ExtratoBancoHoras.xlsx
└── painel/
    ├── index.html              # relatorio geral -> CEO
    └── deptos/
        ├── hub-fucape.html
        ├── tecnologia.html
        ├── biblioteca.html
        ├── centro-servicos-compartilhados.html
        ├── secretaria-academica.html
        ├── diretoria.html
        ├── comunicacao.html
        ├── secretaria-pesquisa.html
        ├── comercial.html
        ├── coordenacao-curso.html
        ├── atendimento.html
        ├── gente-cultura.html
        └── marketing.html
```

Script pega automaticamente o `.xlsx` mais recente (por data de modificação) da pasta `extratos/` — não depende de nome fixo.

## Erros e casos-limite

- `extratos/` vazia ou sem `.xlsx` → mensagem clara no console, não gera nada, não sobrescreve painel anterior.
- Bloco de colaborador incompleto (falta admissão/depto) → aviso no console com o nome, usa "Sem departamento" como fallback, não trava o script inteiro.
- Departamento novo (não visto antes) → gera página nova automaticamente.
- Valor de hora como string `-HH:MM` vs `timedelta` → parser trata ambos os formatos.

## Execução

`atualizar_painel.bat` → `python atualizar_painel.py` → gera `painel/index.html` + `painel/deptos/*.html` → abre `index.html` no navegador padrão → imprime resumo no console (ex: "Painel atualizado: 44 colaboradores, 13 departamentos") antes de encerrar.

## Fora de escopo (YAGNI)

- Sem automação de download do Secullum (extração continua manual, usuário exporta e joga na pasta).
- Sem histórico/série temporal entre execuções — cada rodada é um snapshot do período do extrato atual, igual ao artefato original.
- Sem servidor web, sem watch-folder, sem agendamento automático.
