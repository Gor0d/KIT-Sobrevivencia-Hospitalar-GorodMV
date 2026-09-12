# Faturamento SUS — Guia/APAC com "identificação inválida" (série nova do gestor)

Sintoma: ao lançar uma **APAC** (ou AIH), o MV barra o número da guia com **"386: Guia com
Identificacao Invalida para Ambulatorio!"** e/ou **"ATENÇÃO: Guia (NNN...) com identificação
inválida."**. Causa raiz típica: o gestor (SES/SUS) criou uma **série nova** de numeração cujo
**5º dígito** (identificador do programa) o MV **ainda não conhece** (validação hardcoded).
Caso real validado: dígito **9** = componente "Créditos Financeiros" de um programa estadual de
especialistas (fonte oficial: CONASS — "Dígito Indicador do Programa / 5º dígito da APAC").
Número é `UF(2).Ano(2).**ID**(1).Sequência(7).DV(1)`.

## O identificador (5º dígito) e o que o MV espera
- **AIH (internação):** `1,3,5` · **APAC (ambulatorial):** `2,4,6,7`. Qualquer outro → "identificação
  inválida". A série nova (ex.: `9`) precisa ser **adicionada** às listas.
- Mapeamento de faixa (qual coluna/tipo): `2/7`→NORMAL, `4`→CNRAC, `6`→ELETIVA (APAC).

## SÃO DUAS rotinas de validação (as duas barram — patch nas duas)
O MV valida a guia em **dois pacotes independentes**; a tela chama os dois em sequência, então
corrigir só um troca de erro (some o 386, aparece o "identificação inválida"):

1. **`PACK_SUS.VALIDA_GUIA_SUS`** (antiga, portaria 567). Usa faixa da **`MULTI_EMPRESAS`** (colunas
   `NR_APAC_INICIAL/_CNRAC/_C_ELETIVA` + `_FINAL`) via `decode(substr(guia,5,1),...)`. Pontos:
   - identificação ambulatório: `if substr(cGuia,5,1) not in('2','4','6','7')` → add `'9'`;
   - cursor `cFaixAPAC`: nos **dois** `decode` (inicial e final), add ramo `, '9', faixas.NR_APAC_*_CNRAC`.
2. **`PKG_SUS_REGRA_GUIA`** (moderna). Usa `FAIXA_GUIA_SUS` **e** a `MULTI_EMPRESAS` (em `F_GUIA_IN_RANGE`):
   - `F_TIPO_INST_REGISTRO`: `IF V_ID IN('2','4','6','7')` → add `'9'` (retorna 'APAC');
   - `F_TIPO_GUIA_FAIXA`: `IF V_ID IN('2','7')` → add `'9'` (retorna 'NORMAL', casa com a faixa carregada);
   - `F_GUIA_IN_RANGE` cursor `cFaixAIH`: nos **dois** `decode`, add
     `, '9', faixas.NR_APAC_*_CNRAC`.

**Precedente MV**: a lista já foi estendida antes por PDA/atualização oficial do próprio MV.
Adicionar série nova é o mesmo procedimento oficial (identificador + coluna de faixa + ramo do
decode) → **é CHAMADO MV**. O patch manual abaixo é **ponte** e **é sobrescrito no próximo update
do MV**.

## Onde guardar a faixa da série nova (a gambiarra consciente)
`MULTI_EMPRESAS` tem **uma faixa (início/fim) por dígito, por empresa** — não tem coluna para a série
nova. Se a coluna **CNRAC** (dígito 4) estiver **nula/sem uso** na empresa, reutiliza ela: mapeia o
decode do dígito novo → `NR_APAC_*_CNRAC` e popula
`UPDATE MULTI_EMPRESAS SET nr_apac_inicial_cnrac=<ini>, nr_apac_final_cnrac=<fim> WHERE cd_multi_empresa=<e>`.
Além disso, carregue a faixa também na **`FAIXA_GUIA_SUS`** (a rotina moderna lê ela): 2 linhas
(início+fim), `TP_INSTRUMENTO='APAC'`, `TP_GUIA='NORMAL'`, competência, laudo. `FAIXA_GUIA_SUS` **não
tem coluna de convênio** — é pool por empresa/competência/instrumento; a `P_VALIDA_FAIXA_GUIA` faz
`P_GUIA BETWEEN MIN e MAX` filtrando só por `TP_INSTRUMENTO`, então um número dentro do início/fim passa.
- **Limite da gambiarra:** como a faixa é por **empresa** (não por convênio/gestor), dois gestores
  diferentes que usem a MESMA série (mesmo dígito) na MESMA empresa **não cabem** numa coluna única
  — colidem. Confirme que só um contrato usa o dígito naquela empresa antes de reutilizar uma
  coluna livre. Se dois gestores forem usar o mesmo dígito na mesma empresa → **só chamado MV**.

## DV (dígito verificador) — valide antes
Rotina de dígito verificador do `PACK_SUS`: `DV(pos13) = mod(substr(guia,1,12),11)` (se ≥10, −10).
Cheque por SELECT antes de carregar a faixa, senão troca "identificação" por "dígito verificador
inválido" (389).

## Aplicar o patch no DBeaver — ARMADILHA CRÍTICA
- **NÃO use o "Compile Package" da árvore** para aplicar edições: ele **recompila o fonte JÁ GRAVADO
  (o antigo)** e diz "compiled successfully" **sem salvar suas mudanças**. Confirme via MCP que as
  linhas realmente mudaram mesmo após um "sucesso" desses.
- **Edite na aba "Corpo"** (ou num script `CREATE OR REPLACE PACKAGE BODY ... END;`) e use
  **Salvar → botão "Executar"** do diálogo "Aplicar alterações" (ou **Alt+X** = executar script). Isso
  roda o `CREATE OR REPLACE` e **persiste**. Sempre reconfira via MCP (`all_source` tem o dígito
  novo? `status`=VALID?).
- Faça **todas as edições de um pacote de uma vez** antes de executar (cada execução recompila e
  reinicia o ciclo abaixo).

## Pós-recompilação: ORA-06508 / 04068 é ESPERADO
Recompilar um pacote invalida os **dependentes** e **descarta o estado** das sessões abertas:
- Dependentes inválidos: recompile (`ALTER PACKAGE dbamv.<pkg> COMPILE BODY;`). Um pacote
  dependente pode invalidar **sem ter erro real** → só recompilar volta a VALID. Cheque
  `ALL_ERRORS`: pacotes com erro real (de módulos fora do seu escopo) costumam **já estar
  inválidos antes** — não mexa neles.
- **`ORA-04068/04061/06508` na tela = estado de pacote descartado.** A sessão do MV aberta durante a
  recompilação precisa **fechar e reabrir o MV** (o Forms segura o estado do pacote). Regra: recompilou
  pacote → quem estiver com o sistema aberto **reabre**.

## Validação via MCP (leitura)
```sql
-- 3 pontos com o dígito novo + status
SELECT line, TRIM(text) FROM all_source WHERE owner='DBAMV' AND name='PKG_SUS_REGRA_GUIA'
  AND type='PACKAGE BODY' AND (text LIKE '%''9''%'); -- confira F_TIPO_INST_REGISTRO / F_TIPO_GUIA_FAIXA / cFaixAIH
SELECT object_name,object_type,status FROM all_objects WHERE owner='DBAMV'
  AND object_name IN ('PACK_SUS','PKG_SUS_REGRA_GUIA','PACK_LANCA_FFAS') AND object_type LIKE 'PACKAGE%';
-- faixa na MULTI_EMPRESAS (coluna reutilizada) e na FAIXA_GUIA_SUS
```
