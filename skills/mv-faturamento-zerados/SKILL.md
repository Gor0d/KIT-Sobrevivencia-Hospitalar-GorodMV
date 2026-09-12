---
name: mv-faturamento-zerados
description: Investigar e corrigir exames com Valor Total R$ 0,00 no Relatório de Produção por Convênio (SoulMV/MV ERP), via consultas diretas no Oracle (schema DBAMV). Use quando o usuário mencionar relatório de produção por convênio, exames zerados, R_PROD_RX_CONV_360, ou precificação de procedimentos no MV.
---

# Faturamento MV/SoulMV — Diagnóstico e Correção de Exames Zerados

Metodologia desenvolvida e validada em produção (hospital de médio porte, base DBAMV) para encontrar e corrigir exames que aparecem com
quantidade > 0 mas **Valor Total R$ 0,00** no "Relatório de Produção por Convênio"
(SoulMV - Sistema de Diagnóstico por Imagem, código de relatório tipo `R_PROD_RX_CONV_360`).

Sem acesso MCP direto ao banco, o trabalho é feito gerando SQL para o usuário rodar via
DBeaver (conexão Oracle) e colar o resultado de volta. Trate cada script com o cuidado de
quem está mexendo em banco de produção de faturamento hospitalar real. Prefira colar SQL
direto no chat em vez de criar um arquivo `.sql` novo para cada consulta pequena de
diagnóstico — reserve arquivos para os lotes de INSERT/UPDATE que o usuário vai reexecutar.

## Passo 0 — Entender o cenário com o usuário

Pergunte (ou confirme pelo relatório colado): convênio, período, e quais grupos de exame
concentram mais zerados (RX, US, TC, RM, Mamografia, Hemodinâmica, Cardiologia). Ataque
por ordem de maior impacto financeiro/quantidade primeiro, "um de cada vez", confirmando
o resultado no relatório antes de avançar pro próximo grupo.

## Passo 1 — Confirmar a tabela-chave e função de cálculo

O relatório recalcula o valor **ao vivo** (não lê de uma fatura já gravada) via a função
`DBAMV.CALC_VL_PROC_UNIT` (standalone, não é membro de pacote). Assinatura real:
```
CALC_VL_PROC_UNIT(TIPO_CONVENIO VARCHAR2, PROCEDIMENTO VARCHAR2, DT_REFERENCIA DATE,
  HR_REFERENCIA DATE, CONVENIO NUMBER, PLANO NUMBER, TIPO_ATENDE VARCHAR2,
  TIPO_ACOMODA NUMBER, FLAG_VALOR VARCHAR2, NCDFRANQUIA NUMBER DEFAULT NULL) RETURN NUMBER
```
- `TIPO_CONVENIO`: pegue de `DBAMV.CONVENIO.TP_CONVENIO` pro convênio em questão (ex: 'C').
  Só os valores 'C'/'P' chamam o motor de precificação completo (`VAL_PROC_FFCV`); 'A' e 'H'
  são atalhos que leem `procedimento_sus_valor` (ambulatorial/internação SUS).
- `FLAG_VALOR`: **só aceita 'U' (unitário/valor final), 'F' (filme), 'H' (honorário) ou 'C'
  (CH total) — qualquer outro valor (inclusive vazio) cai no ELSE e retorna 0 sempre**, mesmo
  que tudo mais esteja correto. Use 'U' para reproduzir o valor que aparece no relatório.
- `PLANO`/`TIPO_ATENDE`: não chute — pegue de um atendimento REAL do período (ver Passo 9).
  `TIPO_ATENDE` normalmente é 'E' (não 'A'), mas confirme sempre puxando um caso real.

Isso é ótimo pra corrigir dados: significa que **inserir preço retroativo no banco corrige o
relatório na hora**, sem precisar reprocessar nada (ver exceção rara no Passo 10).

Se for testar a função manualmente via SQL solto, ela depende de
`DBAMV.PKG_MV2000.LE_EMPRESA` estar setado — sempre rodar primeiro:
```sql
BEGIN DBAMV.PKG_MV2000.ATRIBUI_EMPRESA(1); END;
```
(Sem o `/` de terminador — DBeaver não usa isso, só SQL*Plus. Rode como bloco PL/SQL separado.)

## Passo 2 — Descobrir o código de faturamento do exame

```sql
SELECT CD_EXA_RX, DS_EXA_RX, EXA_RX_CD_PRO_FAT
FROM DBAMV.EXA_RX
WHERE CD_EXA_RX IN (...); -- os codigos que aparecem zerados no relatorio (coluna da esquerda)
```
`EXA_RX_CD_PRO_FAT` é o código de faturamento (`CD_PRO_FAT`) — pode estar em formato AMB92
antigo (ex: `32030096`) ou CBHPM atual (ex: `40803090`). Não assuma qual é: os dois formatos
convivem no mesmo sistema, às vezes até para o mesmo grupo de exames.

## Passo 3 — Confirmar a tabela de faturamento certa (não assumir!)

Cada convênio tem uma "regra" (`CD_REGRA`) e cada grupo de procedimento (`CD_GRU_PRO`) roteia
para uma tabela de faturamento (`CD_TAB_FAT`) diferente via `ITREGRA`. **Não assuma que todo
grupo cai na mesma tabela** — confirme sempre, mesmo pra códigos "parecidos" com outros que
já funcionam:
```sql
SELECT p.CD_PRO_FAT, p.CD_GRU_PRO, r.CD_TAB_FAT
FROM DBAMV.PRO_FAT p
LEFT JOIN DBAMV.ITREGRA r ON r.CD_REGRA = <regra_do_convenio> AND r.CD_GRU_PRO = p.CD_GRU_PRO
WHERE p.CD_PRO_FAT IN (...);
```
Para achar `CD_REGRA` do convênio: `DBAMV.EMPRESA_CON_PLA` (por convênio + plano + empresa).

**Caso real**: um exame de cardiologia funcional (ergoespirometria = teste cardiopulmonar)
estava classificado no grupo de Pneumologia (grupo 29), roteando pra uma tabela totalmente
diferente (tabela "5", ~4000 preços cadastrados — não é tabela órfã/lixo) da usada pelos
exames de cardiologia "normais" (tabela 431). Isso é **legítimo** (não é erro de cadastro) —
antes de "corrigir" o grupo, confirme se a tabela alternativa é uma tabela real e populada
(`SELECT COUNT(*) FROM VAL_PRO WHERE CD_TAB_FAT = <tab>`) e se o código pertence
genuinamente àquela especialidade (`SELECT DS_PRO_FAT FROM PRO_FAT WHERE CD_GRU_PRO = <grupo>`
pra ver os vizinhos). Cateterismo cardíaco teve o mesmo padrão (grupo 40 → tabela 5).

## Passo 4 — Checar o que já existe (VAL_PRO e TAB_CONVENIO)

Existem DUAS fontes de preço, checadas nessa ordem pelo motor:

1. **`TAB_CONVENIO`** — preço negociado específico do convênio. Colunas reais (confirmadas
   em produção): `CD_CONVENIO, CD_PRO_FAT, DT_VIGENCIA, VL_TAB_CONVENIO, SN_USAR_INDICE,
   SN_ATIVO, SN_HORARIO_ESPECIAL, SN_FILME, CD_TAB_CONVENIO` (esse último é uma **chave
   surrogate gerada por sequence** — nunca copiar o valor de uma linha existente para outra;
   gerar um novo via `SELECT DBAMV.SEQ_TAB_CONVENIO.NEXTVAL FROM DUAL` ou achar a sequence
   certa com `SELECT SEQUENCE_NAME FROM ALL_SEQUENCES WHERE SEQUENCE_OWNER='DBAMV' AND
   UPPER(SEQUENCE_NAME) LIKE '%<TABELA>%'`). Não tem coluna `CD_TAB_FAT` — a regra vale
   independente de qual tabela de faturamento o grupo usa.
2. **`VAL_PRO`** — preço padrão da tabela de faturamento (fallback). Colunas: `CD_TAB_FAT,
   CD_PRO_FAT, DT_VIGENCIA, VL_TOTAL, VL_OPERACIONAL, VL_HONORARIO, SN_ATIVO, NM_USUARIO`.

```sql
SELECT * FROM DBAMV.VAL_PRO WHERE CD_TAB_FAT = <tab> AND CD_PRO_FAT IN (...) ORDER BY CD_PRO_FAT, DT_VIGENCIA;
SELECT * FROM DBAMV.TAB_CONVENIO WHERE CD_CONVENIO = <convenio> AND CD_PRO_FAT IN (...) ORDER BY CD_PRO_FAT, DT_VIGENCIA;
```

Se ambas vierem vazias em qualquer vigência: o código nunca foi precificado — vá para o Passo 6.
Se existir só com vigência futura (ex: `01/05/2026`) e o período do relatório for anterior:
esse é o problema mais comum — ver Passo 5.

## Passo 5 — O bug de vigência futura (o mais comum)

O motor de preço exige `DT_VIGENCIA <= data_do_exame`. Uma linha datada no futuro é invisível
para exames passados — **e pior**: se existir uma linha de `TAB_CONVENIO` futura para aquele
convênio+código (mesmo que `VAL_PRO` tenha uma linha válida), o motor parece travar em zero
em vez de cair para `VAL_PRO` (comportamento tipo "existe regra específica, mas não vigente
= zero", em vez de "não existe regra específica, cai pro padrão"). **Sintoma**: você corrige o
`VAL_PRO` e o relatório continua zerado — sempre suspeitar de `TAB_CONVENIO` futuro travando.

**Fix**: copiar a linha existente (seja de `VAL_PRO` ou `TAB_CONVENIO`) para uma vigência
retroativa que cubra o período do relatório. Usar `01/01/2026` (ou o primeiro dia do ano em
questão) como padrão — cobre qualquer mês daquele ano, sem precisar de uma linha por mês.
Prefira `INSERT ... SELECT` copiando a linha existente em vez de digitar valores à mão
(evita esquecer coluna obrigatória e garante consistência):
```sql
INSERT INTO DBAMV.VAL_PRO (<colunas>)
SELECT <colunas, com DT_VIGENCIA trocado>
FROM DBAMV.VAL_PRO
WHERE CD_TAB_FAT = <tab> AND CD_PRO_FAT IN (...) AND DT_VIGENCIA = TO_DATE('<data_futura>','DD/MM/YYYY');
```
Isso é seguro porque o relatório recalcula ao vivo (Passo 1) — não reescreve fatura histórica.

**Cuidado com duplicidade**: se rodar o mesmo INSERT retroativo duas vezes sem querer (Alt+X
disparado 2x, ou reexecução), pode gerar duas linhas para a mesma `DT_VIGENCIA` (às vezes sem
violar PK porque a chave inclui uma coluna surrogate tipo `CD_TAB_CONVENIO`). Depois de rodar,
sempre confirme com um `SELECT` filtrado pelo `NM_USUARIO`/tag quantas linhas realmente existem
para aquela vigência exata — se vier mais de uma, apague a duplicata antes de seguir (mas note:
duplicidade sozinha não costuma ser a causa raiz de zero — ver Passo 10).

Se der `ORA-01400 (não é possível inserir NULL)`: a tabela tem coluna NOT NULL fora da sua
lista — rode `SELECT COLUMN_ID, COLUMN_NAME, DATA_TYPE, NULLABLE FROM ALL_TAB_COLUMNS WHERE
OWNER='DBAMV' AND TABLE_NAME='<tabela>' ORDER BY COLUMN_ID` pra pegar a lista completa de
uma vez (evita ficar caçando coluna por coluna).

Se der `ORA-00001 (restrição exclusiva violada)`: pode ser (a) já existe linha idêntica —
benigno, ignorar/pular; ou (b) você copiou uma coluna que na verdade é chave surrogate
(sequence) — ver nota sobre `CD_TAB_CONVENIO` acima.

## Passo 6 — Sourcing de valor quando nunca existiu preço

Quando não há nenhuma linha em nenhuma tabela/vigência, precisa de uma fonte de referência:

- **Tabela Conecta** (planilha de depara AMB→CBHPM específica da instituição, se existir) —
  dá o código CBHPM alvo a partir do código AMB antigo.
- **Lista Referencial 2010** (PDF em formato AMB, código pontuado `XX.XX.XXX-X` — convertível
  de um `CD_PRO_FAT` de 8 dígitos via `f"{c[0:2]}.{c[2:4]}.{c[4:7]}-{c[7]}"`). Extrair texto
  com `pypdf` uma vez e reutilizar o `.txt`.
- **Código "irmão" já precificado** — o mais confiável quando existe: procure no mesmo
  relatório um código de descrição clinicamente equivalente que já tenha valor > 0, e use
  como referência cruzada. Isso pega correções/renegociações que a Lista 2010 (congelada em
  2010) não reflete.
- **Equivalência por PORTE CBHPM** — quando não há irmão clínico óbvio nem valor na Lista,
  descubra o **porte CBHPM** do código (ex: pesquisando na web o código no formato pontuado,
  `41.10.106-5` → tabela CBHPM; o porte vem tipo "3B", "3C"). O hospital costuma precificar
  por equivalência de porte, então ache OUTRO código já precificado com o **mesmo porte** e
  use o mesmo valor. Caso real: "Espectroscopia por RM" (41101065, porte 3B) não tinha
  referência nenhuma — mas "RM ATM" (41101103) é porte 3B também e já valia R$555,28 no
  hospital, então espectroscopia = R$555,28. Muito mais defensável que estimar um valor solto.
  Fontes úteis de porte/CBHPM: orientacaomedicaessencial.com.br, abcdi.org.br.

**Regra de ouro, validada e reforçada nesse projeto por duas vezes**: a Lista Referencial 2010
é confiável para RX e US neste sistema (bateu quase exato com valores já oficiais do banco),
mas **não é confiável para TC** (chegou a divergir +58% de códigos já negociados) — sempre
cruzar com um código-irmão já ativo antes de confiar cegamente num valor de lista antiga.
Nunca insira um valor "no achismo" em tabela de faturamento de produção — se não tiver uma
fonte confiável (nem lista, nem irmão), **pare e pergunte ao usuário / gere um documento para
o setor de faturamento confirmar**, em vez de arriscar.

## Passo 7 — A pegadinha do FILME (custo de filme/m²)

Algumas modalidades (RX, TC, Mamografia — não costuma valer para US "puro") têm custo de
filme cadastrado em `DBAMV.FILME_TAB` (chave: `CD_TAB_FAT + CD_PRO_FAT`; colunas
`NR_INCIDENCIAS, QT_M2_FILME`). **Sempre checar essa tabela antes de finalizar qualquer
valor**:
```sql
SELECT * FROM DBAMV.FILME_TAB WHERE CD_TAB_FAT = <tab> AND CD_PRO_FAT IN (...);
```

Se existir uma linha de `FILME_TAB` para o código, o motor de preço **soma o custo do filme
automaticamente em cima do valor gravado** — então o valor que você grava em `VAL_PRO` (ou em
`TAB_CONVENIO` com `SN_FILME='S'`) precisa já vir **líquido, sem o filme**, senão o exame sai
mais caro que o correto (double-counting). O jeito mais seguro de achar o valor líquido certo:

1. Achar um código-irmão já ativo, com a MESMA `QT_M2_FILME`, e comparar o valor gravado em
   `VAL_PRO`/`TAB_CONVENIO` (bruto, líquido de filme) contra o valor que aparece de fato no
   relatório (com filme somado). A diferença ÷ `QT_M2_FILME` dá a taxa por m² praticada
   (nesse projeto, girou em torno de **R$ 21,70/m²**, consistente em RX/TC/Mamografia/RM —
   mas **recalibre por instituição/ano**, não assuma esse número fixo em outro contexto).
2. Aplicar: `valor_a_gravar = valor_total_desejado - (QT_M2_FILME × taxa_por_m2)`.

A Lista Referencial 2010, quando extraída de PDF com múltiplas colunas coladas (sem espaço
entre células), costuma imprimir na mesma linha, na ordem: `CH | Quant CH | Valor Total (R$) |
Valor Parcial (R$) | FILME (M²) | valor líquido pós-filme`. Ou seja, **o último número da
linha já é o valor líquido de referência** (mas trate como aproximação — a Lista pode divergir
do valor realmente negociado hoje, principalmente em TC; sempre cruze com Passo 6).

**Importante**: se o código NÃO tem linha em `FILME_TAB`, não desconte nada — usar o valor
líquido nesse caso deixaria o exame mais barato que o correto.

### Filme-em-dobro por `SN_FILME` mal setado (armadilha silenciosa)

Num mesmo convênio, os códigos de uma modalidade coexistem em DOIS padrões válidos de
cadastro na `TAB_CONVENIO`, e você tem que respeitar o padrão de cada linha:
- **`SN_FILME='N'`** → o `VL_TAB_CONVENIO` já é o **valor TOTAL** (filme embutido). Ex.: cervical
  gravada 651,08 / 'N' → sai 651,08. ✔
- **`SN_FILME='S'`** → o `VL_TAB_CONVENIO` tem que ser o **valor PARCIAL** (sem filme); o motor
  soma o filme por cima. Ex.: bacia gravada 558,00 / 'S' → 558 + 102,08 = 660,08. ✔

O bug aparece quando uma linha tem **`SN_FILME='S'` MAS o valor gravado é o total** (já com
filme): o motor soma o filme DE NOVO. Caso real (crânio, código `36010014`): gravado 642,60
(≈total) com `SN_FILME='S'` → 642,60 + 102,08 = **744,68**, quando o oficial é **642,08**.
Fix: gravar o **parcial** (540,00) mantendo `SN_FILME='S'` → 540 + 102,08 = 642,08.

**Como diagnosticar rápido:** liste os códigos-irmãos da modalidade lado a lado
(`SELECT CD_PRO_FAT, VL_TAB_CONVENIO, SN_FILME FROM TAB_CONVENIO WHERE CD_CONVENIO=<x> AND
CD_PRO_FAT LIKE '<prefixo>%'`). Um código cujo `VL_TAB_CONVENIO` está no mesmo patamar dos
**totais** dos vizinhos MAS com `SN_FILME='S'` (enquanto os que exibem certo estão em 'N' ou
têm base menor) é quase sempre filme dobrado.

### Valide contra o referencial OFICIAL do convênio, não contra o próprio sistema

Lição do caso acima: o valor tinha sido "validado" olhando só o que o sistema mostrava — mas o
sistema estava com o filme dobrado. **O sistema não é fonte de verdade do valor negociado.**
Sempre cruze com a **lista referencial impressa/PDF do próprio convênio** (que costuma trazer,
por código: `CH | Quant CH | Valor Parcial | FILME (M²) | FILME (R$) | Valor Total`). O
**Valor Total** dessa lista é o alvo final que tem que sair no relatório; o **Valor Parcial** é o
que se grava quando `SN_FILME='S'`. Observações da lista importam (ex.: "contraste paramagnético
cobrado à parte" → o exame "com contraste" fatura o MESMO valor do base, e o contraste vai em
linha separada; 2º segmento no mesmo período = 80%; estudo dinâmico = +50%). Códigos que não
existem na lista oficial (ex.: sela túrcica, ossos temporais) costumam herdar a faixa do estudo
equivalente mais próximo — sela e mastoides = faixa de crânio, no caso acima.

## Passo 8 — Higiene de execução no DBeaver

- Rodar o script inteiro com **Alt+X**, não Ctrl+Enter (que roda só uma instrução) — evita
  `ORA-00900`/`ORA-00933` por causa de blocos PL/SQL ou múltiplas instruções.
- Comentário `--` deve ficar em linha própria, nunca na mesma linha do `;` anterior.
- Blocos PL/SQL (`BEGIN...END;`) não usam `/` como terminador no DBeaver (isso é só
  SQL*Plus) — rode o bloco sozinho, sem `/` na linha seguinte, senão dá `PLS-00103`.
- Gerar um script de rollback (reverso do UPDATE/INSERT) **antes** de rodar qualquer lote
  grande, como rede de segurança.
- Nunca sugerir/rodar `DELETE` em tabela de preço de produção sem confirmar o escopo exato
  com o usuário antes — e sem ter o valor certo já em mãos para reinserir na hora.
- Depois de qualquer lote, gerar uma query de confirmação (`SELECT` filtrado pelo
  `NM_USUARIO`/tag usado no INSERT) antes de considerar o lote concluído — não confiar
  apenas na ausência de erro na tela do DBeaver (a transação pode não ter comitado, ou o
  usuário pode ter rodado só parte do script).
- Usar uma tag identificável em `NM_USUARIO` (ex: `MIGRACAO_CBHPM_2026_LOTEn`) em cada lote
  de INSERT — facilita auditoria e reversão seletiva depois.

## Passo 9 — Testando a função de cálculo com parâmetros REAIS (não chutados)

Quando o preço parece certo em tudo (tabela certa, vigência certa, sem duplicidade) e o
exame CONTINUA zerado, teste `CALC_VL_PROC_UNIT` diretamente (Passo 1) — mas **não chute os
parâmetros PLANO/TIPO_ATENDE**, puxe de um atendimento real do período pra não confundir
"parâmetro errado no meu teste" com "bug de verdade":
```sql
SELECT a.CD_ATENDIMENTO, a.CD_CONVENIO, a.CD_CON_PLA, a.TP_ATENDIMENTO,
       p.CD_PED_RX, i.CD_EXA_RX, i.DT_REALIZADO, i.SN_COBRADO, i.SN_REALIZADO,
       i.NR_FATURADO, i.CD_PRESTADOR
FROM DBAMV.ITPED_RX i
JOIN DBAMV.PED_RX p ON p.CD_PED_RX = i.CD_PED_RX
JOIN DBAMV.ATENDIME a ON a.CD_ATENDIMENTO = p.CD_ATENDIMENTO
WHERE i.CD_EXA_RX = <codigo>
AND a.CD_CONVENIO = <convenio>
AND i.DT_REALIZADO BETWEEN <inicio> AND <fim>;
```
Compare o mesmo conjunto de campos entre um exame que funciona e um que não funciona — se
forem estruturalmente idênticos (mesmo plano, tipo de atendimento, prestador, flags de
faturamento), isso descarta diferença de dado/registro como causa.

Compare também as flags de cadastro do próprio `EXA_RX` (`TP_SEXO, SN_ATIVO,
SN_LANCA_EXAME_PRINCIPAL, SN_INCLUIR_ACRESC, SN_ECOCARDIOGRAMA, SN_PAG_UNIC_EXAME,
SN_FATURA_EXAME_SUS`) entre o código problema e um código-irmão que funciona — mais um ponto
de comparação pra descartar erro de cadastro.

## Passo 10 — Preço certo, tabela certa, e MESMO ASSIM zero: as duas causas reais

Quando o preço existe na tabela certa, sem duplicidade/bloqueio, e o exame continua zerado,
há DUAS causas-raiz frequentes (ambas confirmadas em produção e corrigíveis via banco). Antes
de achar que é "bug do relatório" ou "timing de processamento", cheque estas duas:

### 10a — Split torto do VL_OPERACIONAL (o mais traiçoeiro)

**Se, no `VAL_PRO`, `VL_OPERACIONAL` for diferente (principalmente maior) que `VL_TOTAL`, o
motor de cálculo retorna ZERO** — mesmo com a linha ativa e vigente. Sintoma clássico: um
código zerado cujo `VAL_PRO` tem, ex., `VL_TOTAL=114, VL_OPERACIONAL=100,13` (ou pior,
`VL_TOTAL=347,70, VL_OPERACIONAL=480`). Compare com um código-irmão que funciona: o que
funciona quase sempre tem `VL_TOTAL = VL_OPERACIONAL` (sem split) e `VL_HONORARIO=0`.

Isso costuma ser resíduo de inserts anteriores mal-feitos (um `MIGRACAO_*` antigo que gravou
um split inconsistente). **Fix:**
```sql
UPDATE DBAMV.VAL_PRO SET VL_OPERACIONAL = VL_TOTAL, VL_HONORARIO = 0
WHERE CD_TAB_FAT = <tab> AND CD_PRO_FAT = '<codigo>' AND DT_VIGENCIA >= TO_DATE('01/01/2026','DD/MM/YYYY');
```
Acende na hora. **Regra derivada disso, para TODO insert de VAL_PRO: sempre gravar
`VL_TOTAL = VL_OPERACIONAL` e `VL_HONORARIO = 0`**, a não ser que uma linha oficial pré-existente
comprove outro split. Nunca replicar "fielmente" um split invertido de origem duvidosa.

### 10b — Data do ATENDIMENTO anterior à vigência do preço

**O relatório precifica pela data de ABERTURA do atendimento (`ATENDIME.DT_ATENDIMENTO`), não
pela data de realização do exame (`ITPED_RX.DT_REALIZADO`).** Um exame realizado em março, mas
de um atendimento aberto em dezembro do ano anterior (internação longa, ou paciente admitido
antes), é precificado com a data de dezembro — se o preço retroativo só começa em 01/01,
zera. Confirme puxando as duas datas:
```sql
SELECT i.CD_EXA_RX, i.DT_REALIZADO, a.CD_ATENDIMENTO, a.DT_ATENDIMENTO, a.TP_ATENDIMENTO
FROM DBAMV.ITPED_RX i
JOIN DBAMV.PED_RX p ON p.CD_PED_RX = i.CD_PED_RX
JOIN DBAMV.ATENDIME a ON a.CD_ATENDIMENTO = p.CD_ATENDIMENTO
WHERE a.CD_CONVENIO=<conv> AND i.CD_EXA_RX IN (...) AND i.DT_REALIZADO BETWEEN <ini> AND <fim>;
```
Se `DT_ATENDIMENTO` for anterior à vigência do preço, **estenda o preço mais pra trás** (ex:
`VAL_PRO`/`TAB_CONVENIO` @ 01/01 do ano anterior). Prova rápida via função: chame
`CALC_VL_PROC_UNIT` com a `DT_ATENDIMENTO` real — se der 0 e com a data de realização der o
valor, é este o caso. **Implicação geral: prefira vigências retroativas bem largas (ex:
01/01 de um ou dois anos antes) para cobrir atendimentos abertos antes do período do relatório.**
Um bom diagnóstico de sintoma: o MESMO código funciona num setor e zera em outro (setores
diferentes = atendimentos diferentes = datas de abertura diferentes; ex: clavícula que funciona
no RX-HDL mas zera no RX-HJD porque o atendimento do HJD abriu antes da vigência).

### 10c — Quirk residual raro

Há um caso-limite observado em que, mesmo com preço ativo e vigente cobrindo a `DT_ATENDIMENTO`,
a função retorna 0 para uma data específica de mês anterior ao período (ex: retornou 22,72 para
09/03 mas 0 para 23/02, com `TAB_CONVENIO` ativa desde 01/01 do ano anterior). Não foi possível
resolver via dado — é interno ao motor (`VAL_PROC_FFCV`, ~3752 linhas). Se sobrar só isso e for
baixo valor, documente e siga; se for material, é caso de suporte MV.

### Sobre o teste da função `CALC_VL_PROC_UNIT`

É ótimo para RX/TC/RM, mas **não é confiável para alguns grupos** (cardiologia/Cardius,
internação): retorna 0 mesmo para códigos que funcionam no relatório (confirmado: 40901106
Ecocardiograma dá 0 na função com os parâmetros padrão, mas aparece com valor no relatório).
Para esses grupos, NÃO conclua "está quebrado" a partir de um 0 na função — diagnostique pela
comparação direta de dados de preço (`VAL_PRO`/`TAB_CONVENIO`) contra um irmão que funciona.

## Passo 11 — Multi-convênio: o trabalho é por TABELA/REGRA, não por convênio

Quando aparecerem zerados em OUTROS convênios (não só o principal), a chave é: **o preço é por
tabela de faturamento (`CD_TAB_FAT`), e cada convênio mapeia grupos → tabela via sua `CD_REGRA`**.
Vários convênios compartilham a mesma regra → mesma tabela → mesmo preço. Então resolver uma
tabela cobre todos os convênios daquela regra de uma vez.

**Mapa do terreno** — liste convênios e a regra de cada um, e veja a tabela por grupo:
```sql
SELECT DISTINCT c.CD_CONVENIO, c.NM_CONVENIO, e.CD_REGRA
FROM DBAMV.CONVENIO c
LEFT JOIN DBAMV.EMPRESA_CON_PLA e ON e.CD_CONVENIO = c.CD_CONVENIO
WHERE c.SN_ATIVO = 'S' ORDER BY c.CD_CONVENIO;
-- e a tabela por grupo de imagem:
SELECT CD_REGRA, CD_GRU_PRO, CD_TAB_FAT FROM DBAMV.ITREGRA
WHERE CD_GRU_PRO IN (32,33,34,36,20,29,40) AND CD_REGRA IN (<regras dos convênios de interesse>);
```
(Não use `LISTAGG(DISTINCT ...)` — não é suportado nessa versão; dá ORA-30482.)

Para achar a tabela de um convênio direto (sem hardcodar a regra), derive a regra do convênio:
```sql
... JOIN DBAMV.ITREGRA r ON r.CD_GRU_PRO = p.CD_GRU_PRO
WHERE ... AND r.CD_REGRA IN (SELECT DISTINCT CD_REGRA FROM DBAMV.EMPRESA_CON_PLA WHERE CD_CONVENIO = <conv>);
```

### O mecanismo do ÍNDICE (crucial fora do convênio principal)

Muitos convênios têm um **`CD_INDICE`** (em `EMPRESA_CON_PLA`) que o motor aplica sobre a base da
tabela. Por isso vários convênios têm base de tabela antiga (1992/2012/CH) e mesmo assim mostram
valor atual no relatório — o índice ajusta. E um código **sem base** dá zero (índice × nada = 0).
Descubra o índice: `SELECT DISTINCT CD_REGRA, CD_INDICE FROM DBAMV.EMPRESA_CON_PLA WHERE CD_CONVENIO=<conv>`.

**Você NÃO precisa decodificar o fator do índice.** O jeito robusto de precificar um código CBHPM
zerado: **copie a base do código AMB equivalente que já funciona na MESMA tabela** — aí o índice
faz o mesmo ajuste nos dois, e o código zerado passa a valer igual ao irmão. Ex: `40801012`
(crânio CBHPM, zerado) recebe a base de `32010010` (crânio AMB, priceado). Use `INSERT ... SELECT`
copiando a linha do AMB (pega VL_TOTAL/VL_OPERACIONAL/VL_HONORARIO e a vigência antiga que cobre
tudo), trocando só o `CD_PRO_FAT`. Os AMB↔CBHPM equivalentes de RX/US/TC/RM são os mesmos da
Tabela Conecta / do arquivo RESTAURA do projeto principal.

### Convênio com MÚLTIPLAS regras/planos (o `CD_CON_PLA` decide)

Alguns convênios (ex: GEAP, PARTICULAR) têm vários planos, cada um com uma regra → tabela
diferente. Aí o mapeamento por regra retorna VÁRIAS tabelas para o mesmo código. Para saber qual
tabela um exame zerado realmente usa, puxe o **`CD_CON_PLA` do atendimento** e resolva a regra
por ele — não assuma uma tabela só:
```sql
SELECT i.CD_EXA_RX, i.DT_REALIZADO, a.DT_ATENDIMENTO, a.CD_CON_PLA
FROM DBAMV.ITPED_RX i JOIN DBAMV.PED_RX p ON p.CD_PED_RX=i.CD_PED_RX
JOIN DBAMV.ATENDIME a ON a.CD_ATENDIMENTO=p.CD_ATENDIMENTO
WHERE i.CD_EXA_RX=<cod> AND a.CD_CONVENIO=<conv> AND i.DT_REALIZADO BETWEEN <ini> AND <fim>;
-- depois: SELECT CD_REGRA,CD_INDICE FROM EMPRESA_CON_PLA WHERE CD_CONVENIO=<conv> AND CD_CON_PLA=<plano>;
```
Caso real GEAP: o mesmo código torax existia na tabela 430 mas faltava na 81; o exame zerado era
de um plano que roteava pra 81 → bastava adicionar o código na 81.

### AMB vs CBHPM: às vezes o zerado é o AMB e o repoint NÃO é seguro

O padrão comum é: exame aponta pra código AMB legado sem preço, e o certo é apontar pro CBHPM.
MAS o inverso também ocorre — um exame que aponta pra AMB, com o CBHPM sendo o "correto". Antes de
**repontar EXA_RX** (que muda o código de faturamento para TODOS os convênios de uma vez), COMPARE
os dois códigos nas tabelas afetadas: o código CBHPM pode ter dado PIOR (ex: split invertido
VL_OPERACIONAL > VL_TOTAL, que zera) e o repoint quebraria convênios onde o exame hoje funciona.
Caso real: `40805026` (CBHPM) tinha 12,88/18,20 (operacional > total) na tabela 431 — repontar o
949 para ele quebraria o convênio principal. Regra: **fix localizado (precificar/copiar na tabela do convênio
com problema) é quase sempre mais seguro que repontar EXA_RX**; deixe o repoint para um projeto
planejado, e só depois de limpar os splits dos próprios códigos CBHPM.

### Diferenças por convênio a ter em mente
- **Cada convênio paga tarifa própria** — NUNCA use o valor de um convênio para outro (o usuário
  vai reclamar, com razão). Use o irmão priceado NA TABELA DAQUELE convênio, ou a tarifa negociada
  dele. Se só existir valor em outra tabela, é referência fraca → provisório + validação.
- Alguns convênios têm **RM/TC flat** (ex: IASB = R$450 por RM, R$260 por TC região única) — aí é
  só copiar o valor plano do irmão. Outros variam por estudo.
- **Regra 101 (no convênio principal)** é compartilhada por Particular/Gratuidade/Empregados — esses
  provavelmente já foram corrigidos "de brinde" pelo trabalho na tabela 431.
- **Tabelas podem ser divididas por grupo**: ex. Bradesco/Mediservice (regra 116) usa tabela 9
  para RX/US mas tabela 74 para TC/RM. Confirme a tabela POR GRUPO, não assuma uma só.

### O split-zero também aparece em linhas de REPREÇO (vigência nova)
Um caso real multi-convênio: o código tinha base boa em 2024 (766,58/766,58) mas ganhou uma linha
de **repreço em 2026 com VL_OPERACIONAL=0** (721,59/0) — e como o exame de 2026 pega a vigência
mais recente, zerava. Fix: `UPDATE ... SET VL_OPERACIONAL = VL_TOTAL` na linha da vigência nova.
**Radar**: quando um convênio repricou em 2026 e alguns códigos zeram, suspeite de linha nova com
operacional 0. E note que a leitura do split varia por tabela/convênio (uns leem VL_TOTAL, outros
VL_OPERACIONAL) — por isso o mais seguro é sempre deixar **VL_TOTAL = VL_OPERACIONAL**.

## Comunicação com o usuário

- Prefira colar SQL direto no chat em vez de criar um arquivo novo para cada consulta pequena
  de diagnóstico — reserve arquivos `.sql` para os lotes de INSERT/UPDATE que o usuário vai
  de fato guardar/reexecutar.
- Quando o valor correto for incerto (sem fonte confiável), gere um documento objetivo
  (Markdown, e opcionalmente um PDF via Chrome headless — `chrome.exe --headless
  --disable-gpu --no-pdf-header-footer --print-to-pdf=<arquivo>.pdf <arquivo>.html`, escrever
  primeiro num diretório de scratch e depois copiar pro projeto, já que o Chrome pode negar
  escrita direto em caminhos com acentuação/espaço) para apresentar ao setor de faturamento,
  com a lista de códigos pendentes, volumes, e a pergunta específica que precisa de resposta
  — não insira valor adivinhado em produção.
