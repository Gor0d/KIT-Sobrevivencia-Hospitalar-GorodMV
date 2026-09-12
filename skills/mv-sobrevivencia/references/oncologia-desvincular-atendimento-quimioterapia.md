# Oncologia — Desvincular atendimento de sessão de quimioterapia p/ reagendar

Caso validado em produção (identificadores de paciente/atendimento/guia omitidos). Padrão:
paciente compareceu para quimioterapia mas precisou adiar **antes de iniciar o tratamento** (sem
acesso venoso, intercorrência, etc.) — pede-se "desvincular o atendimento do agendamento" para
poder reagendar.

## As tabelas e como se ligam

| Papel | Tabela | Chave / como identificar |
|---|---|---|
| O atendimento do dia | `ATENDIME` | `CD_ATENDIMENTO`; `TP_ATENDIMENTO='A'` (hospital-dia/ambulatorial p/ quimio) |
| O horário agendado (já ocupado) | `AGENDAMENTO_ONCOLOGICO` | `CD_ATENDIMENTO`, `CD_GUIA`, `CD_SOLIC_AGENDAMENTO`, `CD_ITEM_AGENDAMENTO`, `TP_STATUS` (domínio observado: A=Atendido, C=Cancelado, G=Agendado — F=Falta está documentado mas pode não ocorrer na prática) |
| A solicitação-mãe (o "pedido" da sessão, criado pela prescrição) | `SOLIC_AGENDAMENTO` | `CD_SOLIC_AGENDAMENTO`, `CD_ATENDIMENTO` (da consulta/prescrição que originou), `CD_ITEM_AGENDAMENTO`, `NR_CICLO`/`NR_SESSAO`, **`TP_SITUACAO`** (domínio observado: A=Aguardando, C=Cancelado, G=Agendado) |
| Horários livres do recurso | `AGENDA_ONCOLOGICA` | `CD_RECURSO_ONCOLOGICO`, `DH_INICIO_LIVRE`/`DH_FINAL_LIVRE` |
| Cadastro do box/sala | `RECURSO_ONCOLOGICO` | `TP_RECURSO` ('QUI'=quimio/'RAD'=radio/'FAR'=farmácia), `SN_ATIVO`, dias/horários de funcionamento |
| Prescrição médica da sessão (se já chegou a abrir) | `PRE_MED` | `CD_ATENDIMENTO`; **`SN_MEDICAMENTO_ADMINISTRADO`** diz se o quimioterápico já foi de fato aplicado |
| Evolução/checagem do fluxo de tratamento | `REGISTRO_FLUXO_ONCOLOGIA` | por `CD_PRE_MED`; `TP_REGISTRO_FLUXO_ONCOLOGIA`: S=Válido, N=Não Válido, **A=Aguardando**, R=Reavaliação Médica |

## Passo 0 (sempre primeiro): existe medicamento já administrado?

```sql
SELECT CD_PRE_MED, SN_FECHADO, SN_MEDICAMENTO_ADMINISTRADO, SN_INTERROMPER_SESSAO,
       DS_JUSTIFICATIVA_INTERROMPER, NR_CICLO, NR_SESSAO
FROM DBAMV.PRE_MED WHERE CD_ATENDIMENTO = <atend>;
```
- **Nenhuma linha / `SN_MEDICAMENTO_ADMINISTRADO` vazio ou 'N'**: tratamento não começou de fato — é
  seguro tratar como reagendamento simples (segue o roteiro abaixo).
- **`SN_MEDICAMENTO_ADMINISTRADO='S'` ou existe evolução de intercorrência em
  `REGISTRO_FLUXO_ONCOLOGIA`/`DS_JUSTIFICATIVA_INTERROMPER`**: o processo já começou (acesso puncionado,
  intercorrência evoluída) — **isso não é mais um simples "desvincular"**. Antes de tocar em qualquer
  vínculo, leia a evolução clínica registrada e confirme com o médico solicitante se o pedido é
  reagendar a SESSÃO (sem prejuízo do que já foi feito/registrado) ou se precisa também interromper/
  encerrar formalmente o atendimento em curso pela tela clínica (não só destravar o agendamento).

## Roteiro (quando é reagendamento simples, sem medicamento administrado)

1. Achar o agendamento oncológico do atendimento:
   ```sql
   SELECT CD_AGENDAMENTO_ONCOLOGICO, CD_ATENDIMENTO, CD_GUIA, CD_SOLIC_AGENDAMENTO,
          CD_ITEM_AGENDAMENTO, TP_STATUS
   FROM DBAMV.AGENDAMENTO_ONCOLOGICO WHERE CD_ATENDIMENTO = <atend>;
   ```
2. Tentar excluir pela tela oficial **"Exclusão de Atendimento (Std)"** (use o motivo cadastrado
   equivalente a "paciente não realizou, remarcado"). **Deixe a tela fazer o trabalho** — ela cuida
   de guia/faturamento/TISS corretamente. Só intervir no banco se ela travar.
3. **Trava clássica**: `ORA-02292 ... (DBAMV.CNT_CD_GUIA_FK) violada - registro filho localizado`
   (pode vir acompanhada de `ORA-06502 buffer too small` — normalmente é só a trigger de mensagem de
   erro estourando o buffer ao formatar o aviso do próprio `ORA-02292`, não um segundo bug). A
   constraint é do **próprio** `AGENDAMENTO_ONCOLOGICO.CD_GUIA` — ou seja, o registro que trava a
   exclusão da guia é o mesmo agendamento que você já achou no passo 1. Confirmar qual tabela/coluna
   pertence a uma constraint pelo nome, quando o erro não diz:
   ```sql
   SELECT ac.TABLE_NAME, acc.COLUMN_NAME FROM ALL_CONSTRAINTS ac
   JOIN ALL_CONS_COLUMNS acc ON acc.CONSTRAINT_NAME = ac.CONSTRAINT_NAME AND acc.OWNER = ac.OWNER
   WHERE ac.CONSTRAINT_NAME = '<nome_da_constraint_do_erro>';
   ```
4. **Desbloqueio cirúrgico** (só solta a referência, não recria a lógica da tela):
   ```sql
   UPDATE DBAMV.AGENDAMENTO_ONCOLOGICO
   SET CD_GUIA = NULL
   WHERE CD_AGENDAMENTO_ONCOLOGICO = <id> AND CD_ATENDIMENTO = <atend> AND CD_GUIA = <guia>;
   COMMIT;
   ```
   Repetir a tela "Exclusão de Atendimento" — deve concluir. Se aparecer **outro** número no
   checklist (2°, 3°...), é outro FK filho — repita o passo 3 pra achar de qual tabela é.
5. **Efeito colateral a checar sempre depois**: a exclusão do atendimento **não reverte** o
   `TP_SITUACAO` da `SOLIC_AGENDAMENTO`-mãe. Ela fica presa em `'G'` (Agendado) sem nenhum
   `AGENDAMENTO_ONCOLOGICO` correspondente — sintoma na tela **"Solicitação de Agendamento"**: a
   linha aparece como "Agendado" mas não tem horário nenhum de fato marcado, e por isso não dá pra
   marcar o checkbox "Agendar?" de novo. Confirmar e corrigir:
   ```sql
   -- confirmar que não há AGENDAMENTO_ONCOLOGICO nenhum para essa solicitação:
   SELECT * FROM DBAMV.AGENDAMENTO_ONCOLOGICO WHERE CD_SOLIC_AGENDAMENTO = <solic>;  -- deve vir vazio
   UPDATE DBAMV.SOLIC_AGENDAMENTO SET TP_SITUACAO = 'A'
   WHERE CD_SOLIC_AGENDAMENTO = <solic> AND CD_ATENDIMENTO = <atend_original> AND TP_SITUACAO = 'G';
   COMMIT;
   ```
   Depois disso a linha vira "Aguardando" na tela e o usuário consegue marcar "Agendar?" e clicar em
   "Agendar" — **a criação do novo horário em si é feita pela tela, nunca por INSERT manual**
   (envolve conflito de box/recurso, intervalo mínimo entre sessões do protocolo e geração de guia
   nova; replicar isso em SQL cru arrisca box duplamente ocupado ou guia mal formada).

## Achar horário livre para sugerir (somente leitura, ajuda a agilizar)

```sql
SELECT ao.CD_AGENDA_ONCOLOGICA, ao.DH_INICIO_LIVRE, ao.DH_FINAL_LIVRE, ao.CD_RECURSO_ONCOLOGICO,
       ro.DS_RECURSO_ONCOLOGICO
FROM DBAMV.AGENDA_ONCOLOGICA ao JOIN DBAMV.RECURSO_ONCOLOGICO ro
  ON ro.CD_RECURSO_ONCOLOGICO = ao.CD_RECURSO_ONCOLOGICO
WHERE TRUNC(ao.DH_INICIO_LIVRE) = DATE '<data>' AND ro.TP_RECURSO = 'QUI' AND ro.SN_ATIVO = 'S'
ORDER BY ao.CD_RECURSO_ONCOLOGICO, ao.DH_INICIO_LIVRE;
```

## Telas envolvidas (nomes confirmados ao vivo)

- **Recepção Oncológica** (`M_RECEPCAO_ONCOLOGIA`) — grade do dia por recurso/box; só tem
  "Atender"/"Confirmar-Retirar Falta", **não cancela** nada.
- **Exclusão de Atendimento (Std)** — exclui o atendimento e tenta excluir a guia associada; tem
  checklist de bloqueios (mostra qual FK travou, um por vez).
- **Manutenção de Guias (Std)** — "Central de Guias"; mexe na guia diretamente, cai na mesma trava
  de FK se a guia ainda estiver referenciada.
- **Solicitação de Agendamento** — lista as solicitações (`SOLIC_AGENDAMENTO`) por período/paciente,
  com checkbox "Agendar?" por item e botão "Agendar"; é aqui que se cria o horário novo de fato.

## Princípio geral do caso (reaproveitar)

Nunca reescrever manualmente a lógica de **criação** de agendamento/guia (alto risco, muita regra
de negócio escondida). É seguro fazer só o **desbloqueio pontual de uma referência órfã** (nulificar
uma FK específica, com WHERE amarrado no PK) para deixar a **tela oficial** terminar o trabalho —
sempre com SELECT de confirmação antes/depois, execução pelo próprio usuário (DBA/autorizado), nunca
pelo MCP (somente leitura).

## Variante: atendimento com prescrição/estoque/documento clínico REAIS (não é "não aconteceu nada")

Segundo caso validado (identificadores omitidos). Sintoma: paciente veio para quimio, mas **sem
acesso venoso possível** — médico solicitou reagendar. Diferença-chave do caso simples acima: aqui
os **acessos foram solicitados e a intercorrência foi evoluída/documentada** — ou seja, houve
atividade clínica real antes de abortar.

**Passo 0 sempre primeiro** (ver seção acima): checar `PRE_MED.SN_MEDICAMENTO_ADMINISTRADO`. Neste
caso vinha `NULL` em todas as prescrições (o quimioterápico em si não foi administrado), mas ao
tentar a tela **"Exclusão de Atendimento (Std)"** o checklist veio com **5 bloqueios**, não 1:
1. Solicitação de estoque pendente (materiais de acesso já pedidos ao almoxarifado).
2. **"Não é permitido a exclusão de atendimento que tenha prescrição médica"** — bloqueio por
   EXISTÊNCIA de `PRE_MED`, independente de medicamento administrado ou não.
3. Movimentação de estoque já existe.
4. Mesma trava de guia (`CNT_CD_GUIA_FK`) do caso simples.
5. **"Não foi possível excluir o(s) documento(s) clínico(s)... existe documento clínico"** (PEP) —
   a evolução da intercorrência já é documento clínico real.

**Isso é sinal de que "Exclusão de Atendimento" é a ferramenta ERRADA aqui.** Aquela tela é para
atendimento que "não aconteceu nada" (0 prescrição, 0 documento). Quando há prescrição/estoque/
documento clínico reais, **forçar os 5 bloqueios até conseguir excluir apagaria histórico clínico
legítimo** (o registro de que o acesso foi tentado e falhou). **Pare e confirme com o usuário se ele
quer mesmo destruir esse histórico** antes de seguir — no caso real, a decisão foi **manter o
atendimento intacto** e resolver só a parte financeira/agenda:

1. **Remover os lançamentos da conta ambulatorial aberta** (`ITREG_AMB`, `TP_MVTO='Produto'`,
   `SN_FECHADA='N'`) — script aceitável (mesmo padrão de outro caso desta skill: backup + DELETE,
   conta aberta), **não** reverte estoque (material descartável usado numa tentativa não volta pro
   estoque, e não deveria).
   ```sql
   CREATE TABLE DBAMV.BKP_ITREGAMB_<atend> AS SELECT * FROM DBAMV.ITREG_AMB WHERE CD_ATENDIMENTO = <atend>;
   DELETE FROM DBAMV.ITREG_AMB WHERE CD_ATENDIMENTO = <atend>;
   COMMIT;
   ```
2. **Cancelar a guia pela tela** ("Manutenção de Guias (Std)") — **não por SQL**. `GUIA.TP_SITUACAO`
   **tem sim um código `'C'` (Cancelada)**, mas o mecanismo real de chegar lá passa por rotina da
   tela (pode envolver módulo TISS de cancelamento); um `UPDATE` cru arrisca deixar a guia com o
   flag certo mas sem o cancelamento TISS correspondente, se ela já tiver sido enviada. Validação
   depois: `SELECT CD_GUIA, TP_SITUACAO FROM DBAMV.GUIA WHERE CD_GUIA=<guia>;` → esperado `'C'`.
3. **Cancelar o agendamento oncológico direto por SQL** (aqui é seguro — é só um flag, sem FK
   envolvida, atendimento não está sendo excluído):
   ```sql
   UPDATE DBAMV.AGENDAMENTO_ONCOLOGICO SET TP_STATUS = 'C'
   WHERE CD_AGENDAMENTO_ONCOLOGICO = <id> AND CD_ATENDIMENTO = <atend> AND TP_STATUS = 'A';
   COMMIT;
   ```
4. **Repor a solicitação-mãe para Aguardando** (mesmo passo 5 do caso simples):
   ```sql
   UPDATE DBAMV.SOLIC_AGENDAMENTO SET TP_SITUACAO = 'A'
   WHERE CD_SOLIC_AGENDAMENTO = <solic> AND TP_SITUACAO = 'G';
   COMMIT;
   ```

**Ordem importa**: fazer 1 e 2 pela tela ANTES de 3/4 — não é estritamente uma dependência técnica
observada, mas evita ficar com guia cancelada apontando pra agendamento ainda ativo (ou vice-versa)
enquanto o caso está pela metade.

### Regra de decisão (qual variante usar)
- **0 prescrição + 0 documento clínico** (nada aconteceu) → pode seguir com "Exclusão de Atendimento"
  até o fim (variante simples acima).
- **Qualquer prescrição/estoque/documento clínico real** → **não** force a exclusão do atendimento.
  Confirme o objetivo com o usuário e resolva só guia (tela) + itens de conta abertos (script com
  backup) + status do agendamento/solicitação (script pontual), preservando o atendimento como
  registro clínico.
