---
name: mv-sobrevivencia
description: Sobrevivência operacional no Soul MV / MV ERP (Oracle, schema DBAMV) — regras do MCP soul-mv-erp (somente-leitura, PRODUÇÃO), convênios, planos, regras e tabelas de faturamento, diárias, taxas, vigências, preços, faturamento SUS/SIA/BPA/AIH, crítica de CPF/CADSUS, modelo financeiro de adiantamentos/devoluções (cliente e fornecedor), devolução de compras ao fornecedor, auditoria de acesso ao prontuário (LGPD), acesso ao PEP/perfil ambulatorial, cadastro estrutural de setor/unidade/leito, desvincular atendimento de agendamento oncológico/sessão de quimioterapia, descoberta de estrutura e geração de relatórios/PDF/CSV. Use quando o usuário mencionar MV/SoulMV/DBAMV, Atributo 058, CADSUS/PDQ, guia/APAC com identificação inválida, ranking ou tarifas de convênios, adiantamento, devolução (financeira ou de compras/fornecedor), contas a pagar/receber, auditoria de prontuário, quem acessou/imprimiu, acesso negado ao PEP, desvincular atendimento, cancelar atendimento oncológico, reagendar quimioterapia, ou qualquer investigação direta na base MV que não seja o relatório de exames zerados (esse é a skill mv-faturamento-zerados).
---

# Sobrevivência no Soul MV / MV ERP (base DBAMV)

Conhecimento operacional acumulado e validado em **produção** em instalações reais do Soul MV
(Oracle, schema `DBAMV`). Cada consulta/alteração mexe em banco hospitalar real — trate com o
cuidado devido. Para o caso específico de exames com Valor Total R$ 0,00 no Relatório de Produção
por Convênio, use a skill irmã **`mv-faturamento-zerados`**.

## Ambiente e ferramenta (leia primeiro)

- **O MCP `soul-mv-erp` é SOMENTE-LEITURA e normalmente conecta em PRODUÇÃO.** Confirme sempre
  via `SYS_CONTEXT` — **nunca assuma** que é homologação só pelo nome da conexão. Toda consulta de
  leitura pode e deve ser feita pelo MCP — é seguro (não altera nada).
- `executar_sql_livre` **só aceita SELECT**. Validadores desse tipo costumam **bloquear
  `WITH`/CTE** também (checam só "começa com SELECT") — converta CTEs em subqueries inline.
  Limite de linhas por consulta (`MAX_ROWS`); resultados grandes podem precisar ser salvos em
  arquivo.
- **Qualquer INSERT/UPDATE/DELETE ou rotina transacional NÃO passa pelo MCP somente-leitura.** O
  caminho de escrita é: (a) o **usuário roda o SQL no DBeaver** (ou similar) e commita, ou (b) a
  ação é feita **pela tela do MV** (rotinas financeiras, cancelamentos, devoluções). Gere o
  SQL/passo, o usuário executa e cola o retorno.
- `descrever_tabela` usa o parâmetro **`nome_tabela`** (não `tabela`).
- **Instalação multiempresa**: `CD_MULTI_EMPRESA` separa CNPJ/CNES diferentes dentro do mesmo
  banco (cada empresa pode ter razão social, CNES e regras fiscais próprias). Antes de qualquer
  consulta ou carga, confirme com `SELECT * FROM MULTI_EMPRESAS` **qual código é qual
  instituição na SUA instalação** — nunca assuma que os códigos de outro ambiente valem aqui.

## Regra de ouro: descubra a estrutura antes de escrever a query

Os nomes de coluna do MV **não são adivinháveis** e variam muito entre tabelas irmãs
(ex.: `CON_PAG` usa `VL_BRUTO_CONTA`; `CON_REC` usa `VL_PREVISTO`/`VL_RECEBIDO`; nenhuma
usa `VL_ORIGINAL`). Rode `descrever_tabela` **antes** de montar a consulta em vez de chutar
coluna e colecionar `ORA-00904 (invalid identifier)`. Padrões observados:
- Valores costumam ser `VL_*`; datas `DT_*`; timestamps `TZ_*` ou `DH_*`; sim/não `SN_*`
  ('S'/'N'); tipo/situação `TP_*`/`ST_*`; código `CD_*`; sequencial/PK quase sempre `CD_<tabela>`.
- O sequencial `CD_<tabela>` é gerado por **sequence** e cresce em ordem de inserção — serve
  como **relógio grosseiro** (ordem cronológica) quando não há coluna de data/hora confiável.

## Referências (casos resolvidos, carregados sob demanda)

Cada arquivo abaixo é um caso real, validado em produção e sanitizado (sem dado de paciente,
colaborador ou instituição). Leia o que for relevante para o pedido do usuário — não carregue
tudo de uma vez.

**Convênios e faturamento**
- Ranking de convênios por atendimentos, mapeamento de planos/regras/tabelas, seleção de
  vigência, precedência entre `VAL_PRO` e `TAB_CONVENIO`, CSV por convênio e parecer
  administrativo → [references/convenios-diarias-taxas.md](references/convenios-diarias-taxas.md)
- Consulta ambulatorial faturando 2 procedimentos (genérica + especialidade) e consultas de
  OUTROS atendimentos caindo numa conta só (retorno mal configurado / transferência 24h) →
  [references/faturamento-ambulatorial-retorno-consolidacao.md](references/faturamento-ambulatorial-retorno-consolidacao.md)
- Conferência de fatura de terceirizado por lista de atendimentos (ex.: terapia nutricional) →
  [references/faturamento-terceirizado-conferencia.md](references/faturamento-terceirizado-conferencia.md)

**Faturamento SUS**
- Crítica SIA/BPA **Atributo 058 — CPF obrigatório**, conciliação por CADSUS/PDQ ou SISREG,
  tratamento de recém-nascido, geração controlada de `UPDATE DBAMV.PACIENTE` →
  [references/sia-bpa-atributo-058-cpf.md](references/sia-bpa-atributo-058-cpf.md)
- Guia/APAC com **"identificação inválida"** (série nova do gestor, 5º dígito não reconhecido
  pelo MV) → [references/faturamento-sus-guia-apac-identificacao-invalida.md](references/faturamento-sus-guia-apac-identificacao-invalida.md)
- Crítica **510 AIH** "não foi encontrado item compatível" (compatibilidade SIGTAP faltando) →
  [references/faturamento-sus-critica-510-aih.md](references/faturamento-sus-critica-510-aih.md)
- BPA/exame de um setor caindo sempre no MESMO prestador (fallback do setor, não quem atendeu) →
  [references/faturamento-sus-bpa-fallback-prestador-setor.md](references/faturamento-sus-bpa-fallback-prestador-setor.md)
- Fechamento de conta AIH/espelho/Jasper falhando com `ORA-04063`/`ORA-06508`, package body
  `INVALID` → [references/aih-package-invalido.md](references/aih-package-invalido.md)

**Financeiro**
- Adiantamento de cliente virando devolução, e devolução de adiantamento pago a FORNECEDOR
  (gateway) → [references/financeiro-adiantamentos-devolucoes.md](references/financeiro-adiantamentos-devolucoes.md)
- Devolução de compra ao fornecedor travada / "não consegue excluir" a NF →
  [references/compras-devolucao-fornecedor.md](references/compras-devolucao-fornecedor.md)

**Prontuário, acesso e cadastro**
- Quem acessou/imprimiu o prontuário, com horário (LGPD) →
  [references/auditoria-prontuario-lgpd.md](references/auditoria-prontuario-lgpd.md)
- "Você não tem acesso a página" no PEP (MVPEP) apesar dos perfis certos →
  [references/mvpep-acesso-perfil-ambulatorial.md](references/mvpep-acesso-perfil-ambulatorial.md)
- Criar/segregar estrutura assistencial nova (origem → setor/CC → unidade de internação → leitos)
  → [references/cadastro-estrutural-setor-unidade-leito.md](references/cadastro-estrutural-setor-unidade-leito.md)

**Oncologia**
- Desvincular atendimento de sessão de quimioterapia para reagendar (com e sem
  medicamento/documento clínico já registrado) →
  [references/oncologia-desvincular-atendimento-quimioterapia.md](references/oncologia-desvincular-atendimento-quimioterapia.md)

**Entregáveis**
- Padrão de geração de relatório/planilha/PDF (Edge/Chrome headless, openpyxl, reportlab) →
  [references/relatorios-pdf-xlsx-padrao.md](references/relatorios-pdf-xlsx-padrao.md)

## Comunicação com o usuário

- Consultas de diagnóstico: cole o SQL direto no chat; reserve arquivos para o que o usuário vai
  guardar/reexecutar.
- Em ação de risco (financeiro, cancelamento, alteração em produção): confirme o alvo, dê o passo
  pela tela + SQL de **validação somente leitura**, e seja honesto sobre limitações (sem horário,
  sem trilha de impressão, etc.) em vez de inventar dado.
- Ao documentar um caso novo nesta skill: descreva o **padrão**, nunca o caso identificável — sem
  nome de paciente, número de prontuário/atendimento/guia, matrícula de colaborador, nome de
  instituição/convênio/fornecedor ou caminho de arquivo local. Rode a varredura de
  [CONTRIBUINDO.md](../../CONTRIBUINDO.md) antes de qualquer PR.
