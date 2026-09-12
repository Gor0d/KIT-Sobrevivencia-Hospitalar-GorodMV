# Financeiro — Adiantamentos e Devoluções

Modelo mapeado e validado em caso real (nome e números de paciente/atendimento omitidos).
É o mapa para **qualquer** caso de adiantamento que precise virar devolução.

## As três tabelas e como se ligam

| Papel | Tabela | Como identificar |
|---|---|---|
| **O contrato do adiantamento** | `CONTRATO_ADIANTAMENTO` | 1 linha por adiantamento (`CD_CONTRATO_ADIANT`) |
| **O recebimento do adiantamento** | `CON_REC` com `TP_CON_REC='D'` | tem `CD_CONTRATO_ADIANT`, `CD_ATENDIMENTO` nulo, `VL_PREVISTO` = valor |
| **A conta hospitalar (cobrança real)** | `CON_REC` com `TP_CON_REC='P'` | tem `CD_ATENDIMENTO`, sem `CD_CONTRATO_ADIANT` |
| **A devolução (reembolso ao cliente)** | `CON_PAG` com `TP_CON_PAG='DO'` | tem `CD_CONTRATO_ADIANT`, `VL_BRUTO_CONTA` = valor, `TP_STATUS='LIBE'` |

Colunas-chave de `CONTRATO_ADIANTAMENTO`:
- `VL_CONTRATO_ADIANT` — valor do adiantamento.
- **`SN_RECEBIDO`** — `'S'` = já foi **aplicado** para abater conta a receber; `'N'` = adiantamento
  "solto", nunca aplicado. **Este flag é o coração do diagnóstico.**
- `CD_ATENDIMENTO` — atendimento vinculado (nulo se ainda não vinculado).
- `ST_CONTRATO_ADIANT`, `VL_SALDO_RECEBIDO`, `NM_CONTRATANTE`, `DT_CANCELAMENTO`.

## Como o MV cria a devolução (mecanismo nativo)

Quando um adiantamento é **aplicado a um atendimento** e o valor do adiantamento **excede** a
conta, o MV pergunta na tela:

> *"Deseja criar um Contas a Pagar reembolsando a diferença?"* → **Sim**

Ao confirmar, o MV cria automaticamente:
- o `CON_PAG` de devolução (`TP_CON_PAG='DO'`, `TP_STATUS='LIBE'`),
- a **parcela** correspondente em `ITCON_PAG`,
- a **contabilização** (lote/lançamento contábil),
- e marca `CONTRATO_ADIANTAMENTO.SN_RECEBIDO='S'`.

## Diagnóstico de um caso (roteiro)

1. Liste os adiantamentos do contratante/paciente e o estado de cada um:
   ```sql
   SELECT cd_contrato_adiant, vl_contrato_adiant, sn_recebido, st_contrato_adiant,
          cd_atendimento, cd_paciente, nm_contratante,
          TO_CHAR(dt_contrato_adiant,'dd/mm/yyyy') dt, TO_CHAR(dt_cancelamento,'dd/mm/yyyy') dt_canc
   FROM dbamv.contrato_adiantamento WHERE cd_contrato_adiant IN (...);
   ```
2. Veja quais já têm devolução criada:
   ```sql
   SELECT cd_con_pag, cd_contrato_adiant, vl_bruto_conta, tp_con_pag, tp_status, cd_atendimento
   FROM dbamv.con_pag WHERE cd_contrato_adiant IN (...);
   ```
3. Reconstrua o caixa do atendimento (adiantamentos recebidos vs conta):
   ```sql
   SELECT cd_con_rec, cd_contrato_adiant, vl_previsto, tp_con_rec, cd_atendimento, nm_cliente,
          SUBSTR(ds_con_rec,1,45) descricao
   FROM dbamv.con_rec WHERE cd_atendimento = <atend> OR cd_contrato_adiant IN (...);
   ```
   Some os `TP_CON_REC='D'` (adiantamentos) e subtraia o `TP_CON_REC='P'` (conta) → é o total a devolver.

## A regra prática

- **Adiantamento com `SN_RECEBIDO='S'` e já com `CON_PAG` 'DO'** = resolvido.
- **Adiantamento com `SN_RECEBIDO='N'`** = pendente: precisa ser **processado pela tela** (vincular
  ao atendimento e processar). Como a conta já pode estar coberta por outro adiantamento, o saldo
  vira excedente e o MV oferece criar a devolução → **Sim**.
- **NUNCA crie o `CON_PAG` de devolução por SQL bruto.** Um `INSERT` manual gera um Contas a Pagar
  **sem parcela (`ITCON_PAG`) e sem contabilização** → não entra no fluxo de pagamento, não concilia
  e **desajusta o saldo do adiantamento**. Em módulo financeiro isso é risco alto e difícil de
  reverter. A devolução tem que sair da rotina da tela, igual às que já funcionaram.
- Mesmo quando o usuário pede o SQL, explique isso e ofereça o **passo na tela + SQL de validação
  (somente leitura)**. Se a tela travar ao processar o adiantamento solto, rastreie o bloqueio da
  rotina — não parta para INSERT bruto.

## Cancelamento de recebimento/CON_PAG — a trava da prorrogação

Cancelar um `CON_PAG`/recebimento pode falhar com **`CNT_HIST_PRORROG_ITCONPAG_FK`**: a parcela
(`ITCON_PAG`) tem um filho em `HISTORICO_PRORROGACAO`. Caminho: **remover a prorrogação bloqueadora
e então cancelar pela interface** — não forçar `DELETE`/cancelamento por SQL cru. Antes de cancelar,
reavalie se o cancelamento é mesmo necessário: muitas vezes o alvo se atinge só **criando a
devolução** (sem cancelar nada), e a conta hospitalar real deve permanecer.

## Casos futuros (múltiplos adiantamentos)

Cada adiantamento deve ser **vinculado ao atendimento e processado individualmente**; o excedente
de cada um gera sua própria devolução. **Não deixar adiantamento "solto"** (`SN_RECEBIDO='N'`, sem
atendimento) — é a origem clássica da confusão ("o valor não bate", "sobrou adiantamento sem
devolução").

## Validação pós-ação (somente leitura)
```sql
-- Uma linha CON_PAG 'DO' por devolução esperada:
SELECT cd_con_pag, cd_contrato_adiant, vl_bruto_conta, tp_con_pag, tp_status
FROM dbamv.con_pag WHERE cd_contrato_adiant IN (...);
-- Todos os adiantamentos processados devem ficar sn_recebido='S':
SELECT cd_contrato_adiant, sn_recebido, vl_contrato_adiant
FROM dbamv.contrato_adiantamento WHERE cd_contrato_adiant IN (...);
```

---

# Devolução de adiantamento a FORNECEDOR pago (gateway de pagamento)

Caso: adiantamento pago a um fornecedor (ex.: gateway de pagamento) e depois **devolvido**
(mercadoria não recebida). Objetivo típico: **fazer o reembolso aparecer no extrato do banco** e
zerar o adiantamento.

## Identificar a movimentação
- Adiantamento a fornecedor = `CON_PAG` com `TP_CON_PAG='AF'`, `TP_ADIANTAMENTO='F'`, `CD_FORNECEDOR`,
  `NR_DOCUMENTO` = ordem de compra. Fluxo normal: **DO** (previsão/ordem, vl 0) → **AF** (adiantamento pago)
  → **ES** (nota fiscal, que consome o AF). Se nunca vem o ES, o AF fica **órfão** (mercadoria não chegou).
- Contabilização do AF: `CON_PAG.CD_REDUZIDO` → `PLANO_CONTAS` (ex.: reduzido de "ADIANTAMENTO A
  FORNECEDORES PJ"); `CD_LCTO_MOVIMENTO` = lote contábil.
- Pagamento do título: **`PAGCON_PAG`** (por `CD_ITCON_PAG`). `TP_PAGAMENTO`: **1**=Borderô, **3**=Cheque,
  **4**=Dinheiro, **5**=Débito C/C, **B**=Baixa Contábil. `SN_ESTORNO` diz se já foi estornado. A conta
  bancária fica em **`CON_COR`** (não `CONTA_FINANC`); o movimento bancário em **`MOV_CONCOR`** (não
  `MOV_CAIXA`) quando é débito/crédito em conta corrente. **Se `MOV_CAIXA` está vazio mas há `PAGCON_PAG`
  com `CD_CON_COR`, o dinheiro saiu pelo banco (conta corrente), não pelo caixa.**

## O certo: lançar a ENTRADA no extrato — NÃO cancelar/estornar o pagamento
Se o dinheiro **saiu de verdade do banco** e o **reembolso voltou** ao mesmo banco, os DOIS movimentos
estão no extrato real. **Cancelar** (`O_CANC_PAG`) ou **estornar** (`O_ESTORNO_PAG`) o pagamento **apaga o
débito original** → o extrato do banco continua com ele → **a conciliação não bate**. O certo:
- Tela **Lançamento de Extrato** (`O_LANEXTR`) → **entrada/crédito** na conta corrente do banco, na **data
  da devolução**, **Cód. Contábil = o reduzido do adiantamento**. Isso faz o reembolso
  **aparecer no extrato** e **zera o saldo do adiantamento** (razão da conta: D do pagamento + C da
  devolução = zero). Depois **Conciliação Bancária** (`O_CONCBANC`). O pagamento original permanece intacto.
- **Não** usar conta de receita como contrapartida (não é receita, é devolução de adiantamento).

## Telas (catálogo `MENU_SOUL`)
`MENU_SOUL` é o catálogo de telas do MV: **`TEXTO_PT_BR`** = nome no menu, **`CD_MODULO`** = form. Serve para
achar QUALQUER tela (`WHERE UPPER(texto_pt_br) LIKE '%DEVOLU%'`). Relevantes: `O_LANEXTR` (Lançamento de
Extrato), `O_CONCBANC` (Conciliação Bancária), `O_ESTORNO_PAG` (Estorno Pagamento), `O_CANC_PAG`
(Cancelamento de Pagamentos). **Não existe** tela "Devolução de Adiantamento a Fornecedor" dedicada.

## Validação (leitura)
```sql
-- Lado banco: a entrada no extrato, já conciliada, contrapartida no adiantamento
SELECT cd_mov_concor, cd_con_cor, vl_movimentacao, TO_CHAR(dt_movimentacao,'dd/mm/yyyy') dt,
       cd_reduzido, sn_conciliado, ds_movimentacao
FROM dbamv.mov_concor WHERE cd_con_cor=<conta> AND vl_movimentacao=<vl> AND dt_movimentacao=<data devol>;
-- Pagamento original deve permanecer (sn_estorno nulo):
SELECT tp_pagamento, sn_estorno FROM dbamv.pagcon_pag WHERE cd_itcon_pag=<parcela do AF>;
```
