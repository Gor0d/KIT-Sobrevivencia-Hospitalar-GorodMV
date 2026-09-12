# Faturamento — Consulta ambulatorial com 2 procedimentos (caso real)

Sintoma: consulta de especialista de um convênio fatura **2 procedimentos** — a consulta GENÉRICA
(`00010014` CONSULTA EM CONSULTORIO) **+** a de ESPECIALIDADE (`0101xx` CONSULTA - COM &lt;espec&gt;) —
quando deveria ser só a de especialidade. Caso real: **Convênio A**; num convênio de comparação
(**Convênio B**) não ocorre — útil para descartar hipóteses (ver diagnóstico abaixo).

## Onde olhar
- Consultas ambulatoriais ficam em **`ITREG_AMB`** (não `ITREG_FAT`, que é internação). Chaves:
  `CD_ATENDIMENTO`, `CD_REG_AMB` (a conta), `CD_LANCAMENTO`, `CD_PRO_FAT`, `CD_CONVENIO`,
  `CD_PRESTADOR`, `CD_ATI_MED`, `SN_FECHADA` (do item), `HR_LANCAMENTO`, `TP_MVTO`,
  `SN_REGRA_LANCAMENTO`/`CD_REGRA_*`/`CD_REGRA_SUBSTITUICAO_PROCED`, `CD_IT_AGENDA_CENTRAL`.
  A conta é **`REG_AMB`** (`SN_FECHADA`, `CD_REMESSA`). Genérica = `00010014`/`10101012`;
  especialidade = `CD_PRO_FAT LIKE '0101%'`.
- Achar duplicados: agrupar por atendimento com `HAVING SUM(genérica)>0 AND SUM(especialidade)>0`.

## Diagnóstico (o que já foi descartado)
- Ambos vêm do **próprio atendimento** (`TP_MVTO='Atendimento'`), **mesmo instante/usuário**, **sem
  regra** (`SN_REGRA_LANCAMENTO='N'`, `CD_REGRA_*` nulos), **sem agenda** (`CD_IT_AGENDA_CENTRAL` nulo).
  A especialidade deriva da **especialidade do prestador**; a `CD_ATI_MED` costuma vir genérica ('07'=CLINICO).
- **NÃO é config do convênio.** Comparando Convênio A × Convênio B, nenhum flag de `CONVENIO` gera isso: os que
  diferem (`SN_RETORNO_*_AMB`, `SN_GUIA`, `SN_FECHA_AMB_SEM_IMPRIMIR`) são de **retorno grátis/guia/
  impressão**. `REGRA_SUBSTITUICAO_PROCED` está **vazia** p/ o convênio afetado. As regras
  (`EMPRESA_CON_PLA.CD_REGRA`) diferem, mas as linhas saem **sem regra aplicada**.
- **Não** se concentra em setor/prestador (espalhado). Afeta uma minoria das consultas (na amostra
  observada, ~5%) — na maioria a especialidade substitui a genérica corretamente; em alguns, as duas ficam.
- **Conclusão: é comportamento do MV** (a substituição genérica→especialidade falha em parte dos casos)
  → **prevenção = CHAMADO MV**. Não há botão no convênio que corrija sem quebrar os casos certos.
  Para achar o gatilho exato, **reproduzir 1 caso ao vivo** (observar a especialidade/ati_med escolhida
  no cadastro do atendimento).

## Remediar o que já foi lançado (contas ABERTAS)
Backup + DELETE da genérica só nas contas **abertas** que TAMBÉM têm a especialidade na MESMA conta
(`EXISTS ... e.cd_reg_amb = ia.cd_reg_amb AND e.cd_pro_fat LIKE '0101%'`). **Testar 1 conta na tela
antes do lote** (apagar o lançamento 1 deixa gap no nº de lançamento — confirmar recálculo). Contas
**FECHADAS**: pela tela (reabrir/excluir lançamento). Base viva: a contagem muda entre dias (contas
abrem/fecham) — o `SN_FECHADA='N'`+`EXISTS` pega o estado atual; rodar periodicamente até o MV corrigir.
```sql
CREATE TABLE dbamv.bkp_itregamb_dup AS
SELECT ia.* FROM dbamv.itreg_amb ia
WHERE ia.cd_convenio=<conv> AND ia.cd_pro_fat IN ('00010014','10101012') AND ia.sn_fechada='N'
  AND EXISTS (SELECT 1 FROM dbamv.itreg_amb e WHERE e.cd_reg_amb=ia.cd_reg_amb AND e.cd_pro_fat LIKE '0101%');
-- DELETE com a MESMA condição; COMMIT só após validar (nenhum atend. com genérica+especialidade juntas).
```

---

# Faturamento — Consultas de OUTROS atendimentos caindo numa conta só (retorno mal configurado)

**Sintoma diferente do de cima** (aquele era genérica+especialidade no MESMO atendimento). Aqui:
o usuário abre um atendimento e vê, na conta dele, consultas que pertencem a **outros
atendimentos** — inclusive de **especialidades/prestadores diferentes** (ex.: um urologista e um
cardiologista na mesma conta). Caso real: Convênio A.

**Diferença do sintoma anterior:** aquele foi descartado como "config do convênio" olhando as flags
`SN_RETORNO_*_AMB` — isso vale só para *aquele* sintoma. Para ESTE sintoma (consolidação entre
atendimentos), as flags de retorno **SÃO a causa**.

## O mecanismo de retorno (tabela `CONVENIO`)
- `NR_DIAS_RETORNO` (janela, ex.: 30 dias) + critérios `SN_RETORNO_<X>_AMB` (`ESPECIALID`,
  `PRESTADOR`, `CID`, `PROCED`, `SERVICO`, `LIVRE`) + `TP_RETORNO_ATEND_AMB`.
- **⚠️ Cuidado com a semântica — é fácil ler ao contrário.** A comparação de cada critério, lendo o
  código-fonte real (trigger que dispara em `UPDATE` de
  `cd_convenio/tp_atendimento/cd_prestador/cd_pro_int/cd_especialid/cd_servico/cd_ser_dis` em
  `ATENDIME`, chamando a rotina de checagem de retorno), é feita assim (exemplo prestador, mesmo
  padrão para especialidade/procedimento/serviço/CID):
  ```sql
  Decode(convenio.sn_retorno_prestador_amb, 'S', atendime.cd_prestador, '1')  -- candidato
     Like
  Decode(convenio.sn_retorno_prestador_amb, 'S', pPrestador,          '1')  -- atendimento novo
  ```
  Se o flag é `'S'`, os dois lados do `LIKE` viram o **valor real** → só bate se forem iguais →
  **`'S'` EXIGE coincidência**. Se o flag é `'N'` (ou qualquer coisa ≠ `'S'`), os dois lados
  viram a string literal `'1'` → sempre bate → **`'N'` IGNORA o critério por completo** (não
  compara nada, qualquer valor "bate"). **Semântica correta: `'S'` = exige igual; `'N'` = não
  checa esse critério.** Um teste empírico rápido comparando só dois convênios pode sugerir o
  oposto por coincidência de outros fatores — **sempre confirme lendo o código-fonte
  (`ALL_SOURCE`) antes de mudar um flag em produção**, não só por comparação estatística.
- **`TP_RETORNO_ATEND_AMB='E'`** = a consulta-retorno é faturada no atendimento de **origem** (a 1ª
  conta), por isso "os outros caem nela". O atendimento-retorno pode nem ficar com `SN_RETORNO='S'`
  (a marcação em `ATENDIME.SN_RETORNO`/`CD_ATENDIMENTO_ORIGINAL` nem sempre é gravada) e ainda assim
  o item é re-etiquetado com o nº do atendimento de origem.

## Diagnóstico (queries-chave)
- Contas segurando vários atendimentos (mesmo paciente = consolidação; **pacientes diferentes =
  bug grave**, cheque sempre):
  ```sql
  SELECT ia.CD_REG_AMB, COUNT(DISTINCT ia.CD_ATENDIMENTO) n_atend,
         COUNT(DISTINCT a.CD_PACIENTE) n_pac, COUNT(DISTINCT a.CD_ESPECIALID) n_esp
  FROM dbamv.itreg_amb ia JOIN dbamv.atendime a ON a.cd_atendimento=ia.cd_atendimento
  WHERE ia.cd_convenio=<c> AND ia.hr_lancamento>=DATE '<ini>'
  GROUP BY ia.cd_reg_amb HAVING COUNT(DISTINCT ia.cd_atendimento)>1;
  ```
- **Casos "re-etiquetados" que a query acima NÃO pega** (o item foi gravado já com o nº do
  atendimento de origem → aparece como 1 atendimento só): procure contas com **2+ códigos de
  consulta distintos** `LIKE '0101%'` → duas especialidades na mesma conta:
  ```sql
  SELECT cd_reg_amb FROM dbamv.itreg_amb WHERE cd_convenio=<c> AND cd_pro_fat LIKE '0101%'
    AND hr_lancamento>=DATE '<ini>' GROUP BY cd_reg_amb HAVING COUNT(DISTINCT cd_pro_fat)>1;
  ```
- `PRO_FAT.DS_PRO_FAT` traduz o código de cada especialidade lançada.

## Correção
```sql
-- de preferência pela tela (Cadastro do Convênio -> aba Retorno)
UPDATE dbamv.convenio SET SN_RETORNO_ESPECIALID_AMB='S', SN_RETORNO_PRESTADOR_AMB='S'
WHERE cd_convenio=<c>;   -- passa a exigir mesma especialidade + mesmo prestador para ser retorno
```
Regra de negócio típica: **especialidade/prestador diferente = guia separada**; retorno legítimo é
mesmo médico/mesma especialidade em X dias. Confirme com o faturamento a regra contratual antes de
mudar o flag — e releia a seção de semântica acima: **`'S'` é quem exige coincidência**, não `'N'`.

**Ressalvas:** (1) é flag do convênio inteiro, vale só para lançamentos **novos**; (2) o backlog já
consolidado **não se desfaz sozinho** — separar pela tela (reabrir conta + re-lançar cada
atendimento na sua guia); (3) distinga **Grupo A** (mesmo paciente/mesma especialidade, ex.:
nefrologia/diálise — pode ser conta mensal legítima, avaliar contrato) de **Grupo B** (2
especialidades diferentes na conta — erro claro, separar sempre).

## ⚠️ São DOIS mecanismos independentes de consolidação — cheque os dois

Corrigir só o retorno **não resolve tudo**. Existe um segundo mecanismo, e o próprio MV o denuncia
numa mensagem: *"Transferência de itens para atendimento anterior dentro de 24hs. Os itens do
atendimento X foram transferidos para atendimento Y"*.

| Mecanismo | Janela | Sensível à especialidade? | Pega | Flag |
|---|---|---|---|---|
| **Retorno** | `NR_DIAS_RETORNO` (ex.: 30 dias) | Sim (via `SN_RETORNO_ESPECIALID_AMB`) | recorrentes mesma esp. (ex.: nefrologia/diálise) | `CONVENIO.SN_RETORNO_ESPECIALID_AMB` + `SN_RETORNO_PRESTADOR_AMB` |
| **Transferência 24h** | **24h (fixa na rotina)** | **NÃO — ignora especialidade** | 2 atendimentos do **mesmo dia**, inclusive **especialidades diferentes** | **`EMPRESA_CONVENIO.SN_TRANSF_MESMO_ATEND_AMB`** (chave `CD_MULTI_EMPRESA`+`CD_CONVENIO`; variantes `_EXT`/`_URG`) |

Os casos **cross-especialidade do mesmo dia** são da **transferência 24h**, não do retorno. A janela
de 24h parece **fixa** (não há coluna de horas) — só liga/desliga.
```sql
UPDATE dbamv.empresa_convenio SET SN_TRANSF_MESMO_ATEND_AMB='N'
WHERE cd_convenio=<c> AND cd_multi_empresa=<e>;   -- para de puxar itens pro atendimento anterior
```
**Ressalva:** essa flag costuma vir `'S'` em vários convênios (padrão do hospital) e serve para um
caso legítimo — mesmo encontro aberto como 2 atendimentos por engano (re-cadastro) é reunificado.
Desligar mantém tudo separado (o que se quer p/ guia por especialidade), mas também os re-cadastros
legítimos. Confirme com o faturamento. **Diagnóstico rápido de qual mecanismo agiu:** veja a
distância entre as datas dos atendimentos irmãos — **mesmo dia/≤24h = transferência**; **dias/semanas
= retorno**.

## ⚠️ Addendum: cuidado ao "corrigir" a semântica do flag de retorno

Num caso real, uma correção anterior setou os dois flags de retorno para `'N'`, acreditando (por
uma leitura invertida da semântica) que isso passaria a EXIGIR coincidência. Pela leitura correta
do código-fonte (seção acima), `'N'` na verdade **desliga a checagem** — o oposto do pretendido.
Resultado: o motor de retorno passou a marcar como retorno **qualquer** atendimento ambulatorial do
mesmo paciente/convênio dentro da janela de dias, **sem checar especialidade nem prestador**.

**Como confirmar que foi isso** (prova estatística): meça, por dia, quantos atendimentos foram
marcados `SN_RETORNO='S'` **sem nenhum atendimento anterior de mesma especialidade+prestador** nos
dias da janela (ou seja, marcados errado sob a regra pretendida). Um salto abrupto na taxa diária
exatamente na data da mudança de flag confirma a causa raiz. Cheque também
`ATENDIME.NM_USUARIO_RETORNO` — se a grande maioria dos casos errados estiver com esse campo nulo
(o campo que registraria uma marcação manual), confirma que é o motor automático, não erro de
operador. Fique atento a consultas faturadas por um código "quase-zero" de retorno em vez do valor
real — é perda de receita concreta, não só problema de trilha.

**Fix:** reverter os dois flags para `'S'` (ver SQL corrigido na seção "Correção" acima). Isso
**não desfaz** os atendimentos já marcados errado enquanto o flag esteve invertido — o trigger só
GRAVA `'S'`, nunca reverte para `'N'` sozinho, então os casos já marcados errado precisam de
correção manual/lote via `UPDATE` direto em `ATENDIME.SN_RETORNO` (confirmar com o suporte MV se há
efeito colateral em outra tabela antes de fazer isso em lote).
