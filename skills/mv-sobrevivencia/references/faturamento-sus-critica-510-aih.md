# Faturamento SUS — Crítica 510 AIH "Não foi encontrado item compatível" (compat SIGTAP faltando)

Sintoma: ao fechar/criticar uma AIH, o MV acusa **"510: ATENÇÃO: Não foi encontrado nenhum item
compatível para o procedimento NNNNNNNNNN."**. Causa comum: um exame (ex.: anatomopatológico) que
acompanha uma cirurgia — a carga do SIGTAP veio SEM o conjunto de compatibilidade cirúrgica, então
toda AIH com o exame + uma cirurgia ainda não pareada bate no 510.

## Onde nasce a crítica
Procedure **`PRC_FFIS_VALIDA_FINAL_2`** (mensagem '510:...'). Ela **percorre os itens da conta**
(`ITREG_FAT`) e, para cada item, consulta **`PROCEDIMENTO_SUS_COMPAT_P321`** buscando um "par"
que precisa estar presente na mesma conta:
- direção: `cd_procedimento = <a cirurgia>` · `cd_procedimento_compativel = <o item>`;
- exige `tp_compatibilidade IN ('1','5')` **e** a cirurgia com `PROCEDIMENTO_REGISTRO_VIGENCIA`
  `cd_instrumento_registro IN ('03','04','05')`, vigente na competência;
- se acha linhas de compat mas **nenhuma** cirurgia-par está na conta → dispara 510 para o item.
Então o 510 do exame = "existe a cirurgia na conta, mas falta o par (cirurgia→exame) na P321".

⚠️ **`PROCEDIMENTO_SUS_COMPAT_P321` é a tabela que a AIH lê** — não a `PROCEDIMENTO_SUS_COMPAT`
(base). Cadastrar/limpar na base não muda a crítica. tp_registro '03' (cirurgia) → '07' (exame).

## Stopgap (o que destrava) — INSERT data-driven na P321
Cria o par para as cirurgias que **realmente** cruzam com o exame. Escopo recomendado: **histórico
completo** (todas as cirurgias que já geraram o exame), não só o ano corrente — assim a recorrência
some (só volta se surgir cirurgia inédita). Padrão (idempotente, auto-protegido):
```sql
INSERT INTO dbamv.procedimento_sus_compat_p321
  (cd_procedimento, tp_registro, cd_procedimento_compativel, tp_registro_compativel,
   tp_compatibilidade, qt_maxima, dt_vigencia, sn_ativo, dt_validade_inicial, dt_validade_final)
SELECT s.cir,'03','<codigo_exame>','07','1',1,
       TO_DATE('01/07/2024','dd/mm/yyyy'),'S',TO_DATE('01/07/2024','dd/mm/yyyy'),NULL
FROM (SELECT DISTINCT rf.cd_procedimento_realizado cir FROM dbamv.reg_fat rf
      WHERE rf.cd_reg_fat IN (SELECT DISTINCT cd_reg_fat FROM dbamv.itreg_fat
                              WHERE cd_procedimento='<codigo_exame>')) s
WHERE s.cir IS NOT NULL
  AND EXISTS (SELECT 1 FROM dbamv.procedimento_registro_vigencia prv
              WHERE prv.cd_procedimento=s.cir AND prv.cd_instrumento_registro IN ('03','04','05'))
  AND NOT EXISTS (SELECT 1 FROM dbamv.procedimento_sus_compat_p321 pc
                  WHERE pc.cd_procedimento=s.cir AND pc.cd_procedimento_compativel='<codigo_exame>'
                    AND pc.tp_compatibilidade IN ('1','5'));
```
Depois **re-CRITIQUE a conta** — a P321 é lida em tempo real (não recompila nada, não reabre MV).

## Por que o stopgap é seguro (e o que É o fix real)
- `NOT EXISTS` não duplica; `EXISTS prv` só entra cirurgia AIH válida; formato = aos pares que já
  funcionam. A **P321 é check LOCAL de pré-fechamento**; o **DATASUS valida a compatibilidade por
  conta própria** no arquivo — cadastrar o par só DESTRAVA o fechamento, não força pagamento de par
  não reconhecido. Baixa exposição de glosa.
- **Fix definitivo = CHAMADO MV / re-carga SIGTAP** do conjunto cirúrgico (registro '03') do
  exame afetado. Se houver mais de um chamado aberto por "SIGTAP/série nova incompleta" no mesmo
  período, vale consolidar — costuma ser a mesma causa raiz (carga SIGTAP desatualizada).
