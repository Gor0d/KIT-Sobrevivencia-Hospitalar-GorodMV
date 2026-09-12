# Faturamento SUS — BPA/exame de setor caindo sempre no MESMO prestador (fallback do setor, não quem atendeu)

Sintoma: exames/procedimentos de um setor específico saem no BPA/APAC **todos atribuídos a um único
prestador**, mesmo quando pacientes diferentes foram vistos por médicos diferentes. Dois casos reais
com a MESMA causa raiz: (1) exames de diagnóstico por imagem caindo no médico **prescritor** em vez
do executor; (2) exames de pacote de um setor de exames de especialidade (ex.: biomicroscopia,
mapeamento de retina, retinografia, tonometria em oftalmologia) caindo **todos em um único médico**,
independente de quem realmente atendeu.

## O mecanismo (`PRC_FFAS_LANCA_PSDI`)

A procedure decide `nCdPrestador` assim (ordem de prioridade):
```
cTpPrestador vem de CONFIG_FFAS.TP_IMPORT_PRESTADOR_PSDI (cursor filtra só por CD_MULTI_EMPRESA)
if cTpPrestador = 'L' then nCdPrestador := NVL(cd_prest_lau, cd_prest_set)   -- laudador
elsif cTpPrestador = 'E' then nCdPrestador := p_cd_prestador                -- executor/prescritor
end if
if nCdPrestador IS NULL then nCdPrestador := cd_prest_set                   -- fallback do SETOR
-- cd_prest_set = NVL(SET_EXA.cd_prestador_sus, SET_EXA.cd_prestador)
```
**`CONFIG_FFAS.TP_IMPORT_PRESTADOR_PSDI` é UM valor por EMPRESA INTEIRA** (confirmado pela estrutura
da tabela: chave é só `CD_MULTI_EMPRESA`, não tem coluna de setor) — **não dá pra ter um setor no
modo laudador e outro no modo executor ao mesmo tempo**. Se o valor não é `'L'` nem `'E'` (ex.: `'S'`),
cai sempre no fallback fixo do **setor** (`SET_EXA.CD_PRESTADOR`/`CD_PRESTADOR_SUS`) — **um único
médico cadastrado, igual para todo mundo que passa por aquele setor de exame**.

## ⚠️ Pista falsa: `SET_EXA.TP_ORIGEM_PREST_FAT`

Existe uma coluna com nome muito sugestivo (`TP_ORIGEM_PREST_FAT` = "origem do prestador a
faturar") na mesma tabela `SET_EXA`. **Não é o mecanismo do SUS.** Confirmado via busca em
`ALL_SOURCE`: só é referenciada pelos triggers `*_FFCV` (**Faturamento Convênio** — plano de saúde
privado), nunca por `PRC_FFAS_LANCA_PSDI`/`PACK_LANCA_FFAS` (FFAS = SUS). Não perca tempo mexendo
nela achando que resolve BPA/APAC.

## Diagnóstico — como confirmar que é isso (e não outra coisa)

1. Quebre a produção do setor por procedimento × prestador na competência; se um só prestador
   domina em vários procedimentos DIFERENTES do mesmo setor, com contagem parecida em cada um
   (assinatura de fallback fixo, não de gente atendendo de verdade), é esse mecanismo:
   ```sql
   SELECT e.cd_procedimento, e.cd_prestador, COUNT(*) qt
   FROM dbamv.eve_siasus e
   WHERE e.cd_multi_empresa=<emp> AND TRUNC(e.dt_eve_siasus,'MM')=TO_DATE('01/<mm>/<aaaa>','dd/mm/yyyy')
     AND (e.cd_setor=<setor> OR e.cd_setor_produziu=<setor>)
   GROUP BY e.cd_procedimento, e.cd_prestador ORDER BY e.cd_procedimento, qt DESC;
   ```
2. Confirme o fallback cadastrado:
   ```sql
   SELECT se.cd_setor, se.cd_set_exa, se.nm_set_exa, se.cd_prestador_sus, se.cd_prestador, p.nm_prestador
   FROM dbamv.set_exa se LEFT JOIN dbamv.prestador p ON p.cd_prestador=se.cd_prestador
   WHERE se.cd_setor=<setor>;
   ```
3. **Prove com DUAS fontes independentes** quantas linhas são genuinamente do prestador cadastrado
   vs. de outro médico — cruze contra o **atendimento real** (`ATENDIME.CD_PRESTADOR`, quem
   efetivamente viu o paciente) **e** contra o **pedido do exame** (`PED_RX.CD_PRESTADOR` via
   `EVE_SIASUS.CD_ITPED_RX → ITPED_RX.CD_PED_RX → PED_RX`, quem solicitou). As duas devem concordar
   quase exatamente — foi assim que se confirmou um dos casos reais (as duas fontes bateram acima
   de 99% das linhas). Se as duas fontes divergirem muito, investigue antes de corrigir — pode não
   ser o mesmo mecanismo.
   ```sql
   SELECT CASE WHEN a.cd_prestador=<fallback> THEN 'É DELE' ELSE 'É DE OUTRO' END situacao,
          COUNT(DISTINCT e.cd_atendimento) qt_atend, COUNT(*) qt_linhas
   FROM dbamv.eve_siasus e JOIN dbamv.atendime a ON a.cd_atendimento=e.cd_atendimento
   WHERE e.cd_multi_empresa=<emp> AND TRUNC(e.dt_eve_siasus,'MM')=TO_DATE('01/<mm>/<aaaa>','dd/mm/yyyy')
     AND (e.cd_setor=<setor> OR e.cd_setor_produziu=<setor>) AND e.cd_prestador=<fallback>
   GROUP BY CASE WHEN a.cd_prestador=<fallback> THEN 'É DELE' ELSE 'É DE OUTRO' END;
   ```

## As telas (não precisa SQL pra trocar o fallback)

| Tela | `cd_modulo` | Edita |
|---|---|---|
| **Setores de Exames** | `M_SETEXA_PSDI` (também `M_SETEXA`) | `SET_EXA` — inclusive o campo Prestador/Prestador SUS do setor |
| **Parâmetros** | `M_CONFIG_FFAS` | `CONFIG_FFAS` — inclusive `TP_IMPORT_PRESTADOR_PSDI` (empresa inteira, cuidado) |

Trocar **quem é o fallback fixo** de um setor: pela tela **Setores de Exames**, sem SQL. Mais seguro
que `UPDATE` direto (passa pelas validações da tela).

## O que a tela NÃO resolve — e a decisão que cabe ao setor clínico, não à TI

**Não existe, em lugar nenhum do código, um jeito de fazer o BPA/APAC seguir dinamicamente "quem
atendeu" por paciente dentro de um setor de exame.** A única variação por paciente possível é o
ramo `'E'` (executor/prescritor) do flag **empresa inteira** — e mexer nesse flag pra um setor
reabre o bug já corrigido em outro (ex.: imagem voltando a cair no prescritor). É um **trade-off
arquitetural real**, não falta de configuração. As duas saídas:
- **A) Fallback único "correto"**: setor clínico escolhe **1 responsável** pelos exames daquele
  setor, troca na tela Setores de Exames, resolve de vez, mas não reflete produtividade individual
  real por paciente.
- **B) Reconciliação periódica por SQL** (mantém produtividade real por médico): não tem como evitar
  o lançamento nascer errado, só corrigir depois — script de correção roda por competência, sourced
  em `ATENDIME.CD_PRESTADOR`, ver padrão abaixo. Fix definitivo = **chamado MV** pedindo
  `TP_IMPORT_PRESTADOR_PSDI` (ou equivalente) configurável por setor, não só por empresa.

## Correção retroativa (opção B) — segura mesmo com competência já remessada

```sql
-- Backup, depois UPDATE reatribuindo ao ATENDIME.CD_PRESTADOR real, só onde diverge do fallback:
UPDATE dbamv.eve_siasus e
SET e.cd_prestador = (SELECT a.cd_prestador FROM dbamv.atendime a WHERE a.cd_atendimento=e.cd_atendimento)
WHERE e.cd_multi_empresa=<emp> AND TRUNC(e.dt_eve_siasus,'MM')=TO_DATE('01/<mm>/<aaaa>','dd/mm/yyyy')
  AND (e.cd_setor=<setor> OR e.cd_setor_produziu=<setor>) AND e.cd_prestador=<fallback>
  AND EXISTS (SELECT 1 FROM dbamv.atendime a WHERE a.cd_atendimento=e.cd_atendimento
              AND a.cd_prestador IS NOT NULL AND a.cd_prestador<><fallback>);
```
**Se a competência já foi remessada** (`EVE_SIASUS.CD_REMESSA` preenchido — confira antes), este
UPDATE **não reenvia nada ao gestor** — o valor total faturado não muda. Ele corrige só a
**atribuição interna de produtividade/repasse por médico** (quem aparece como responsável nos
relatórios internos). Isso é importante deixar claro pro usuário: não é "consertar a fatura", é
"consertar quem recebe o crédito da produção".

## Automatizar (job) — cuidados antes de agendar

Se decidirem por reconciliação periódica automática (`DBMS_SCHEDULER`), os riscos a mapear antes:
- **Criar/rodar job precisa de privilégio DBA**, não passa pelo MCP (nem a criação nem a execução) —
  precisa ser feito direto por quem tem acesso elevado.
- **Não rodar sobre competência ainda aberta/quente** (dia corrente) — o atendimento pode mudar
  depois; rodar só sobre dado já assentado (ex.: fim da competência, ou D-2/D-3 pra trás).
- **Checar se existe rotina noturna do próprio MV que reprocessa `EVE_SIASUS`** antes de agendar —
  senão o job criado e algum processo interno podem brigar (sobrescrever um ao outro).
- Prefira, se possível, um job que **só alerta/loga** (gera lista pra revisão humana) em vez de
  `UPDATE` automático sem ninguém olhando — mesmo princípio de todo o resto desta skill: escrita em
  produção sempre revisada antes do commit.

## Comunicação

- Consultas de diagnóstico: cole o SQL direto no chat; reserve arquivos para o que o usuário vai
  guardar/reexecutar.
- Em ação de risco (financeiro, cancelamento, alteração em produção): confirme o alvo, dê o passo
  pela tela + SQL de **validação somente leitura**, e seja honesto sobre limitações em vez de
  inventar dado.
