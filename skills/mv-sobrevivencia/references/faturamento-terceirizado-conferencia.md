# Faturamento — Conferência de terceirizado por lista de atendimentos

Padrão para conferir a fatura de um terceirizado (caso real: terapia nutricional enteral/
parenteral — dietas, equipos, acessórios) contra o que está faturado no MV, para pagar só o
correto. O padrão se aplica a qualquer terceirizado cobrado por produto/item consumido.

## Regras aprendidas (caso real)

- **Escopo é por PRODUTO, não por prescritor.** Filtrar pelo médico prescritor corta
  pacientes cuja terapia foi prescrita por outro — dá muito menos gente. Escope pelos **produtos**
  do terceirizado (no caso: dietas + equipos de nutrição + acessórios, por nome de produto).
- **`TP_MVTO_ESTOQUE='P'` é genérico** (dispensação por prescrição de TODOS os prestadores), não é
  "produção do terceirizado". Não use isso como filtro de escopo sozinho.
- **Ancore na lista de atendimentos do terceirizado quando existir.** A relação deles costuma vir
  por planilha própria — extraia os atendimentos (ex. via `openpyxl`) e cruze com `IN (...)`. Foi o
  que destravou o caso real (bateu a quase totalidade dos atendimentos contra a conta).
- **Confira o status da conta** (`REG_FAT.SN_FECHADA`): contas **abertas** ainda recebem lançamentos →
  faturado < cobrado é esperado nelas. Pague pelas **fechadas**, segure as abertas.
- **Preços costumam bater** entre a fatura deles e o faturado — a divergência é de **quantidade/escopo
  de item**, não de preço.

## ⚠️ Armadilha crítica: valor por item NÃO é confiável (composição em linhas de componente)

O MV pode **lançar o valor de um item composto (ex.: nutrição parenteral) na linha de um
COMPONENTE/EQUIPO**, não numa linha única "produto final". Sintoma: um item de baixo custo
aparente (ex.: um equipo) aparece com um valor muito acima do normal em `ITREG_FAT` porque carrega
o valor da composição inteira. Consequência: **a soma por atendimento é real, mas o rateio
produto-a-produto é torto** → não dá para fazer "item-a-item" fiel direto do banco. O detalhe
autoritativo por item é a **conta na tela do MV**. Não force um "match 100%" automático — conferir
com o Faturamento a regra de "quais itens contam" e investigar a composição
(`MVTO_ESTOQUE` produção `tp='P'`, `CD_PRODUTO_MANIPULADO`, `QT_PRODUZIDA`, `VL_TOTAL`) antes.

## Chaves de faturamento (produto × faturado)

- `ITREG_FAT.CD_MVTO` = `MVTO_ESTOQUE.CD_MVTO_ESTOQUE`; `ITREG_FAT.CD_ITMVTO` = `ITMVTO_ESTOQUE.CD_ITMVTO_ESTOQUE`.
- **Sempre filtrar `ITREG_FAT.TP_MVTO='Produto'`** — as linhas `'Faturamento'` são rateio/repasse e
  duplicam valor; `'Diaria'`/`'Atendimento'` têm `CD_ITMVTO` nulo.
- Produto do item faturado: `ITREG_FAT.CD_ITMVTO → ITMVTO_ESTOQUE.CD_PRODUTO → PRODUTO.DS_PRODUTO`.
  Alternativa a investigar quando o rateio atrapalha: agregar por **`ITREG_FAT.CD_PRO_FAT`** (código de
  faturamento) em vez do produto de estoque.
- **Filtro de data**: `ITREG_FAT.DT_LANCAMENTO` no mês. Cuidado com consumo do mês lançado no mês
  seguinte (perde no filtro) — a fatura do terceirizado costuma ser por dia de consumo.
- "Movimento-âncora" (todos os itens `Produto` de um movimento que contém o item do terceirizado)
  **contamina com outros itens** batidos no mesmo movimento (ex.: medicação) — não é escopo limpo.
