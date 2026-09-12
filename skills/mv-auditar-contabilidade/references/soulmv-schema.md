# Schema Soul MV confirmado

Fonte: inspeção read-only realizada em 23/07/2026 no banco `ORASML`, serviço `sml`,
schema corrente `DBAMV`. Confirmar novamente no ambiente de cada tarefa.

## Produtos e classificação

- `DBAMV.PRODUTO`: `CD_PRODUTO`, `DS_PRODUTO`, `TP_ATIVO`, `DT_CADASTRO`,
  `CD_NCM`, `CD_ESPECIE`, `CD_CLASSE`, `CD_SUB_CLA`, `CD_ITEM_RES`,
  `CD_USUARIO_INC`, `DT_INC_USUARIO`, `CD_USUARIO_ALT`, `DT_ALT_USUARIO`.
- `DBAMV.ESPECIE`: chave `CD_ESPECIE`, descrição `DS_ESPECIE`, possível
  `CD_ITEM_RES`.
- `DBAMV.CLASSE`: chave composta `CD_ESPECIE`, `CD_CLASSE`, descrição
  `DS_CLASSE`, possível `CD_ITEM_RES`.
- `DBAMV.SUB_CLAS`: chave composta `CD_ESPECIE`, `CD_CLASSE`, `CD_SUB_CLA`,
  descrição `DS_SUB_CLA`, indicação `SN_PROD_PERMANENTE`, possível `CD_ITEM_RES`.
- `DBAMV.ITEM_RES`: `CD_ITEM_RES`, `DS_ITEM_RES`, `SN_ATIVO`.
- `DBAMV.UNI_PRO`: `CD_UNI_PRO`, `CD_PRODUTO`, `CD_UNIDADE`, `DS_UNIDADE`,
  `VL_FATOR`, `SN_ATIVO`.
- `DBAMV.EST_PRO`: confirmar colunas por dicionário antes do uso.

O item de resultado pode existir em mais de um nível classificatório. Não usar somente
`PRODUTO.CD_ITEM_RES` como verdade universal e não preencher conta quando o campo estiver nulo.

## Compras

- `DBAMV.ORD_COM`: `CD_ORD_COM`, `CD_SOL_COM`, `DT_ORD_COM`, `TP_SITUACAO`,
  `SN_AUTORIZADO`, `USUARIO_AUTORIZADOR`, `CD_ID_USUARIO_AUTORIZOU`,
  `CD_USUARIO_CRIADOR_OC`, `CD_FORNECEDOR`, `VL_TOTAL`.
- `DBAMV.ITORD_PRO`: `CD_ORD_COM`, `CD_PRODUTO`, `CD_UNI_PRO`, `QT_COMPRADA`,
  `QT_RECEBIDA`, `VL_UNITARIO`, `VL_TOTAL`, `NM_USUARIO`, `NR_ITEM`.
- `DBAMV.SOL_COM` e `DBAMV.ITSOL_COM`: confirmar o contrato estrutural específico
  antes de implementar a cadeia de solicitações.

Interpretar `NM_USUARIO` como usuário associado ao item, não como responsável confirmado
pela decisão.

## Entradas

- `DBAMV.ENT_PRO`: `CD_ENT_PRO`, `CD_ORD_COM`, `DT_ENTRADA`, `DT_RECEBIMENTO`,
  `CD_USUARIO`, `CD_USUARIO_RECEBIMENTO`, `CD_FORNECEDOR`, `NR_DOCUMENTO`, `VL_TOTAL`.
- `DBAMV.ITENT_PRO`: `CD_ITENT_PRO`, `CD_ENT_PRO`, `CD_PRODUTO`, `CD_UNI_PRO`,
  `QT_ENTRADA`, `QT_TOMBADO`, `VL_UNITARIO`, `VL_TOTAL`, `NR_ITEM`.
- `DBAMV.LOT_PRO`: confirmar a chave e os vínculos pelo dicionário.

## Patrimônio

- `DBAMV.BENS`: `CD_BEM`, `CD_ENT_PRO`, `CD_ITENTPRO`, `DS_BEM`, `DS_PLAQUETA`,
  `DT_TOMBAMENTO`, `DT_BAIXA`, `SN_NATUREZA_PERMANENTE`, `VL_COMPRA`,
  `CD_MULTI_EMPRESA`.
- `DBAMV.LANCAMENTO_PATRIMONIO` e `DBAMV.V_LANCAMENTO_PATRIMONIO`: confirmar
  colunas de lançamento e conta antes de qualquer associação contábil.

Ausência em `BENS` pode significar prazo operacional, vínculo diferente ou falta de tombamento.
Apresentar como possível pendência até validação do Patrimônio.

## Auditoria e usuários

- `DBAMV.AUDIT_SUPRIMENTOS`: 332 colunas no ambiente inspecionado. Sempre filtrar por
  objeto, chave e período; nunca fazer leitura ampla.
- `DBASGU.USUARIOS`: diretório de usuários. Não confundir login técnico com pessoa física.

## Descoberta de 23/07/2026

Os produtos 21750 e 28618 existem e estavam inativos. As chaves 124210 em `ORD_COM` e
195556 em `ENT_PRO` não existiam em `ORASML`; não usar esses documentos para homologar
esse ambiente sem nova confirmação.

A base tinha última entrada em 22/06/2024, última ordem em 17/10/2025 e último
tombamento em 12/03/2024. Casos piloto confirmados:

- entrada 155686 → ordem 103923 → solicitação 16178;
- entradas 155678–155680 sem ordem vinculada;
- bem 6602 → entrada 136733 → item 526026 → ordem 93623 → produto 38393.

No caso do bem 6602, a entrada registra quantidade 5 e `QT_TOMBADO = 1`. Tratar a
diferença apenas como possível pendência até conferir todos os bens, agregações, baixas
e lançamentos patrimoniais.

## Descoberta PRD de 23/07/2026

O serviço `prd` identificou banco `cdbprd1`, schema `DBAMV`, com entradas e ordens na
data da coleta. Foram observadas diferenças de versão: `PRODUTO` com 106 colunas,
`ITORD_PRO` com 43, `ENT_PRO` com 81 e `ITENT_PRO` com 53.

Pilotos confirmados:

- entrada 197418 → produto inativo 41761, sem ordem no vínculo direto;
- entrada 197395 → ordem 125226 → solicitação 23577 → produto 34256;
- bem 11691 → entrada 196870 → ordem 124746 → produto inativo 51635, com quantidade
  recebida e tombada igual a 1.

Não inferir o significado dos códigos `ME`, `MA`, `OP` e `OU` de
`SUB_CLAS.SN_PROD_PERMANENTE` sem validação funcional.
