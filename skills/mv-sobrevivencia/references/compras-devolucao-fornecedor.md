# Compras/Almoxarifado — Devolução ao Fornecedor (entrada de mercadoria)

Modelo mapeado e validado em caso real (nome do fornecedor e números de nota fiscal omitidos).
É o mapa para **qualquer** caso de "NF de devolução travada"/"não consegue excluir" no
módulo de Compras — é uma cadeia de tabelas totalmente diferente da de adiantamento financeiro.

## As tabelas e como se ligam

| Papel | Tabela | Como identificar |
|---|---|---|
| **A compra original (nota de entrada)** | `DOCUMENTO_ENTRADA` + `ENT_PRO` | 1 linha por NF de compra (`CD_ENT_PRO`), liga a `CD_ORD_COM` (ordem de compra) |
| **Os itens recebidos** | `ITENT_PRO` | 1 linha por produto/`CD_ENT_PRO`; `QT_ENTRADA` = recebido, **`QT_DEVOLVIDA`** = já devolvido |
| **A devolução ao fornecedor (cabeçalho)** | `DEV_FOR` | 1 linha por **lote** de devolução (`CD_DEVOLUCAO`), aponta pro `CD_ENT_PRO` de origem, tem `NR_DOCUMENTO`/`NR_SERIE` (a NF que o fornecedor emitiu) e `CD_MOT_DEV` |
| **Os itens de cada lote devolvido** | `ITDEV_FOR` | 1 linha por produto/`CD_DEVOLUCAO`, tem `CD_ITENT_PRO` (aponta pro item original) e `CD_CUSTO_MEDIO` |
| **A baixa real de estoque** | `CUSTO_MEDIO` (`TP_CUSTO_MEDIO='DEVOLUCAO'`) | `QT_ENTRADA` negativo = quantidade baixada do saldo pra aquele produto/estoque |

Não existe uma tabela "NOTA_FISCAL" para isso — `NOTA_FISCAL`/`NOTA_FISCAL_RECEBIMENTO` são do
módulo de faturamento/contas a receber. Pra compras, é sempre `DOCUMENTO_ENTRADA`/`ENT_PRO` (entrada)
e `DEV_FOR`/`ITDEV_FOR` (devolução). `MVTO_ESTOQUE` **não é usado** para o registro fiscal da
devolução de compra — quem baixa o saldo é o `CUSTO_MEDIO`.

## O bug operacional clássico: devolução parcial virou devolução da nota inteira

Sintoma relatado: "não consegue excluir a NF de devolução, trava". Causa raiz observada:
a devolução deveria cobrir **só o item com problema** (ex.: 1 produto fora de especificação, motivo
"MATERIAL EM DESACORDO COM O SOLICITADO"), mas alguém processou a devolução de
**todos os itens da entrada**, muitas vezes em **múltiplos lotes** (`DEV_FOR` diferentes) porque a
tela tem limite de itens por lançamento — e digitou o **mesmo número de NF** (a única que tinha em
mãos, do item realmente devolvido) em todos os lotes.

**Como confirmar isso é o que aconteceu — diagnóstico em 3 passos:**
```sql
-- 1) Ache a entrada original pelo nº da NF de compra
SELECT cd_ent_pro, cd_fornecedor, nr_documento, vl_total, cd_ord_com, sn_fechado
FROM dbamv.ent_pro WHERE cd_fornecedor = <forn> AND nr_documento = '<nf_compra>';

-- 2) Veja TODOS os lotes de devolução dessa entrada — se a soma dos vl_total bater com o
--    vl_total da entrada inteira, é sinal de devolução da nota toda (errado)
SELECT cd_devolucao, nr_documento, vl_total, TO_CHAR(dt_devolucao,'dd/mm/yyyy') dt
FROM dbamv.dev_for WHERE cd_ent_pro = <cd_ent_pro>;

-- 3) Cheque item a item: quantos dos itens da entrada estão com qt_devolvida = qt_entrada
--    (devolução total do item) vs. parcial/zero — se TODOS os itens da nota estiverem em
--    devolução total, é a mesma assinatura do bug
SELECT ip.cd_produto, p.ds_produto, ip.qt_entrada, ip.qt_devolvida
FROM dbamv.itent_pro ip JOIN dbamv.produto p ON p.cd_produto = ip.cd_produto
WHERE ip.cd_ent_pro = <cd_ent_pro> ORDER BY ip.qt_devolvida DESC;
```
Compare o `NR_DOCUMENTO` e `VL_TOTAL` de cada `CD_DEVOLUCAO` com a **NF física real** que o
fornecedor emitiu (peça o DANFE/print pro usuário) — o lote cujo `VL_TOTAL` bate exatamente com o
valor da NF real é o correto; os demais lotes que reaproveitam o mesmo número de NF mas com valores
que não correspondem a documento fiscal nenhum são o erro.

## Por que não dá pra simplesmente excluir (e por que a tela trava)

A devolução **não é um flag isolado**: cada item do lote gera uma linha `CUSTO_MEDIO` do tipo
`DEVOLUCAO` que **efetivamente baixa o saldo de estoque** daquele produto (confirmado: baixa real de
quantidade, não só marcação — em itens de consumo corrente, isso pode significar produto que nunca
saiu fisicamente do hospital). Essa linha entra na **cadeia** de custo médio do produto (cada evento
carrega `QT_ESTOQUE_ANTES`/`VL_CUSTO_MEDIO_ANTES` do evento anterior). Se depois da devolução errada
o produto teve **novos movimentos de consumo** (o que é normal e imediato em item de giro rápido),
excluir o `DEV_FOR` teria que desfazer e recalcular a cadeia de custo médio de
**todos os produtos afetados** a partir daquela data — é isso, não falta de permissão, que trava a
exclusão pela tela em lotes assim (mesmo princípio de outros bloqueios no MV: o registro já tem
filhos/consequências posteriores, exclusão direta corrompe a cadeia).

```sql
-- Confirme se a baixa foi real (produto realmente saiu do saldo) e se já teve movimento depois:
SELECT cd_custo_medio, TO_CHAR(dt_custo,'dd/mm/yyyy') dt, qt_estoque_antes, qt_entrada, tp_custo_medio
FROM dbamv.custo_medio
WHERE cd_produto = <produto> AND cd_estoque = <estoque> AND dt_custo >= <data_devolucao_errada> - 1
ORDER BY cd_custo_medio;
```

## Encaminhamento (não fazer DELETE cru)

- **Nunca** apague `DEV_FOR`/`ITDEV_FOR` direto por SQL — o saldo de estoque e o custo médio de
  dezenas de produtos ficam órfãos/errados, sem contar itens que já foram vendidos/consumidos sobre
  o saldo já corrompido.
- O lote cujo valor bate com a NF real fica como está (é a devolução legítima).
- Para os lotes errados: **chamado MV** pedindo suporte para reverter/recalcular a cadeia de custo
  médio dos produtos afetados a partir da data da devolução errada — é rotina de suporte, não tela
  de usuário. Leve pronta a lista de `CD_DEVOLUCAO` errados + produtos afetados (a query acima já
  entrega isso) para agilizar o chamado.
- Cadastro de fornecedor: repare também se o CNPJ do emitente na NF bate com o `NR_CGC_CPF` cadastrado
  em `FORNECEDOR` pro `CD_FORNECEDOR` usado — é comum a mesma rede varejista faturar por filial/CNPJ
  diferente do cadastrado (não travou este caso, mas é droga adicional pra conferir/alinhar cadastro).
