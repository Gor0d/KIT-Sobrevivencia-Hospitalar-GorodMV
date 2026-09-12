# Auditoria de acesso ao prontuário (LGPD)

Para responder "quem acessou / quem imprimiu o prontuário do paciente X, com horário".
Metodologia validada em caso real (nome e número do paciente omitidos por LGPD).

## Tabela principal: `PW_AUDITORIA_PRONTUARIO_VIP`

Audita acessos ao prontuário de pacientes marcados como **sigilosos/VIP**. Colunas úteis:
- `CD_AUDITORIA_PRONTUARIO_VIP` — PK sequencial (= **ordem cronológica** dos eventos).
- `CD_ATENDIMENTO` — o atendimento (não o paciente; cuidado: o número que o usuário chama de
  "prontuário" costuma ser o **atendimento**, não `CD_PACIENTE`).
- `CD_USUARIO_AUDITORIA` — login (ex.: `M#####`, `F#####`, `DBAMV`).
- `TP_AUDITORIA_PRONTUARIO` — tipo de ação. Códigos possíveis: ACE(acesso), ALT, INC, EXC, IMP
  (impressão), COP, etc. Confirme quais realmente ocorrem na sua base — em pelo menos uma
  instalação observada, só `ACE` aparece na prática; a ação `IMP` (impressão) nunca é gerada.
- `VL_AUDITORIA` — **o detalhe traz o NOME do prestador** embutido no texto, então não precisa de
  tabela de usuário. Dois padrões:
  - `"Tentativa de acesso do prestador NOME por senha"` = **tentativa** (tela de senha).
  - `"Acesso pelo prestador NOME ao prontuário por senha mediante configuração"` = **acesso concedido**.
- `NM_PERFIL_USUARIO` — perfil (MEDICO, ENFERMEIRO, TECNICO DE ENFERMAGEM, AUDITOR_INTERNO,
  ADM SOMENTE LEITURA, FARMÁCIA...).
- `NM_MAQUINA` — IP da estação.
- `TZ_AUDITORIA_PRONTUARIO` — timestamp, **frequentemente NULO** (ver limitação).

Extrair o nome do prestador do detalhe:
```sql
TRIM(REGEXP_SUBSTR(vl_auditoria, 'prestador (.*?)( por senha| ao prontu)', 1, 1, 'i', 1))
```
Classificar o evento:
```sql
CASE WHEN UPPER(vl_auditoria) LIKE 'ACESSO PELO PRESTADOR%' THEN 'ACESSO CONCEDIDO'
     WHEN UPPER(vl_auditoria) LIKE 'TENTATIVA%' THEN 'Tentativa' ELSE ... END
```

## Limitação nº 1: sem horário de relógio

`TZ_AUDITORIA_PRONTUARIO` pode vir **100% NULO** para os atendimentos consultados (confirme com
`COUNT(*)` vs `COUNT(tz_auditoria_prontuario)`). Sem ele, **ordene por `CD_AUDITORIA_PRONTUARIO_VIP`
(PK sequencial)** — reflete fielmente a ordem cronológica (mais antigo → mais recente), mesmo sem
hora exata. `PW_CONTAB_ACESSO_PRONTUARIO` (que teria `DH_ACESSO`) e `LOG_ACESSO_PEP` (que teria
`DH_LOG_ACESSO_PEP`) tendem a estar **vazias** — cheque, mas não conte com elas.

## Limitação nº 2: impressão pode não ser auditável

"Quem imprimiu" pode **não ser rastreável**, dependendo da instalação. Fontes a verificar e o que
costumam ter:
- `PW_AUDITORIA_PRONTUARIO_VIP` — pode só ter ação `ACE`, nunca `IMP`.
- `IMPRESSAO` — é só o **spooler** (etiquetas/mapas de farmácia); **sem vínculo a paciente/atendimento**.
- `LOG_ACESSO_PEP`, `AUTORIZACAO_ACESSO_PRONTUARIO` — costumam estar **vazias**.
- `REGISTRO_DOCUMENTO` (tem `SN_IMPRESSO` + `CD_ATENDIMENTO`) — confira se tem registros para os
  atendimentos do caso; em pelo menos uma instalação observada, não tinha.

Declare isso com honestidade no relatório e recomende **abrir chamado MV** para habilitar a
auditoria de impressão (ação IMP vinculada a paciente/atendimento/usuário) e investigar o
timestamp nulo (sem data-hora, a trilha perde valor probatório).

## Leitura dos resultados

- **`DBAMV` / usuário "não utilizar modelo de prestador"** = usuário técnico/genérico do sistema
  (login automático), não é pessoa nominal — separe do restante.
- Acessos **posteriores à alta** importam (paciente já saiu e alguém abriu o prontuário). Como a
  base é **produção ao vivo**, o `MAX(seq)` pode crescer entre consultas — reextraia na data de
  fechamento e avise que novos eventos podem surgir.
- Destaque quem tem mais **"acessos concedidos"** e quem gerou o **evento mais recente** (maior seq).

## Consulta base (cronologia)
```sql
SELECT cd_atendimento, cd_auditoria_prontuario_vip seq, cd_usuario_auditoria usuario,
       TRIM(REGEXP_SUBSTR(vl_auditoria,'prestador (.*?)( por senha| ao prontu)',1,1,'i',1)) prestador,
       nm_perfil_usuario perfil, nm_maquina maquina,
       CASE WHEN UPPER(vl_auditoria) LIKE 'ACESSO PELO PRESTADOR%' THEN 'ACESSO CONCEDIDO'
            WHEN UPPER(vl_auditoria) LIKE 'TENTATIVA%' THEN 'Tentativa' ELSE SUBSTR(vl_auditoria,1,60) END evento
FROM dbamv.pw_auditoria_prontuario_vip
WHERE cd_atendimento IN (...) ORDER BY cd_atendimento, cd_auditoria_prontuario_vip;
```
Confirme o paciente e os atendimentos primeiro (`ATENDIME` → `CD_PACIENTE`, `DT_ATENDIMENTO`,
`DT_ALTA`) e valide o nome em `PACIENTE`.

## Ao documentar um caso real nesta skill (ou em relatório para terceiros)

Nunca inclua nome de paciente, número de prontuário/atendimento ou qualquer identificador
específico — descreva o padrão ("caso validado", "instalação X observou Y"), nunca o caso em si.
