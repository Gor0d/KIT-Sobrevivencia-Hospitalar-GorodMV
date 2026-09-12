# AIH: package invalido, objeto ausente e implantacao parcial

Use este roteiro quando fechamento de conta AIH, calculo SUS ou impressao do espelho falhar com
`ORA-04063`, `ORA-06508`, erro Jasper ao executar SQL, ou quando um package body do FFIS estiver
`INVALID`.

## Leitura correta da cadeia de erros

- `ORA-04063` informa que o corpo possui erros de compilacao.
- `ORA-06508` e o efeito em tempo de execucao: a tela nao consegue chamar a unidade invalida.
- `ORA-06512: line 1` normalmente aponta para o wrapper da tela, nao para a linha defeituosa do
  package.
- Em `ALL_ERRORS`, encontre o primeiro erro SQL concreto. Um `ORA-00942` dentro da declaracao de
  cursor torna o cursor incompleto; `PLS-00341` e varios `PLS-00320` posteriores sao cascata, nao
  causas independentes.
- Um erro Jasper como `Error executing SQL statement` pode ser apenas outro consumidor da mesma
  cadeia. Corrija o objeto invalido e reteste o relatorio antes de investigar o SQL Jasper como
  incidente separado.

Consultas base, sempre somente leitura:

```sql
SELECT object_name, object_type, status,
       TO_CHAR(last_ddl_time,'DD/MM/YYYY HH24:MI:SS') ultima_alteracao
FROM all_objects
WHERE owner = 'DBAMV'
  AND object_name = 'PKG_FFIS_PRODUCAO_AIH'
ORDER BY object_type;
```

```sql
SELECT line, position, text
FROM all_errors
WHERE owner = 'DBAMV'
  AND name = 'PKG_FFIS_PRODUCAO_AIH'
  AND type = 'PACKAGE BODY'
ORDER BY sequence;
```

Depois de obter a linha-raiz, leia uma janela pequena do fonte:

```sql
SELECT line, text
FROM all_source
WHERE owner = 'DBAMV'
  AND name = 'PKG_FFIS_PRODUCAO_AIH'
  AND type = 'PACKAGE BODY'
  AND line BETWEEN <LINHA_INICIAL> AND <LINHA_FINAL>
ORDER BY line;
```

## Caso validado: `DADOS_LAUDO_SA04`

No caso observado, o cursor de `P_PESQUISA_DADOS_LAUDO_SA04` referenciava explicitamente
`DBAMV.DADOS_LAUDO_SA04`. O objeto nao existia na PRD, mas existia como `TABLE VALID` na HML.
Como o nome estava qualificado com `DBAMV`, grant por role ou synonym nao explicava o erro: o
pre-requisito estrutural estava ausente na PRD.

Nao crie uma tabela improvisada a partir das colunas do cursor. Primeiro:

1. Confirme ausencia na PRD e existencia/tipo/status na HML com `ALL_OBJECTS`.
2. Confirme tablespaces, constraints, indices, triggers, grants, quantidade de linhas e rotinas
   que leem/escrevem o objeto.
3. Extraia o DDL oficial da HML com o tipo literal correto:

   ```sql
   SELECT DBMS_METADATA.GET_DDL('TABLE','DADOS_LAUDO_SA04','DBAMV')
   FROM dual;
   ```

   Nao execute `<OBJECT_TYPE>` literalmente; substitua por `TABLE`, `VIEW` etc.
4. Salve CLOBs grandes diretamente em arquivo. Copiar/colar pode truncar package bodies no limite
   do cliente ou do chat; um fonte que termina no meio de uma instrucao nao e backup valido.
5. Nao copie dados da HML para PRD. Dados de homologacao nao pertencem a producao.

Assinatura estrutural observada: tabela com 27 colunas, PK `CNT_DADOS_LAUDO_SA04_PK` em
`NR_LAUDO`, dados em `MV2000_D` e indice em `MV2000_I`. Nao trate essa assinatura como universal:
extraia e compare o DDL da HML correspondente a mesma release — nomes de tablespace variam por
instalacao.

## Implantacao parcial: o que permanece gravado

Scripts Oracle com `CREATE OR REPLACE`, `CREATE TABLE`, `GRANT` ou `CREATE SYNONYM` fazem commit
implicito. Se a specification for criada, o body ficar `INVALID` e comandos posteriores forem
executados, um `ROLLBACK` comum nao restaura o estado anterior.

Tambem pode ocorrer de uma tabela de controle de versao SUS registrar a evolucao antes da falha;
DDL posterior na mesma sessao pode efetivar esse registro. Preserve o registro como evidencia ate
decidir entre completar a implantacao ou restaurar a versao anterior. Nao repita cegamente o
pacote inteiro.

Inventarie o que realmente foi aplicado:

- status e `LAST_DDL_TIME` de specifications e bodies;
- colunas/tabelas alteradas;
- grants e synonyms executados depois do erro;
- linha na tabela de controle de versao SUS, se existir;
- arquivos efetivamente entregues e sua ordem nominal.

## Comparacao HML x PRD

- Datas diferentes em `LAST_DDL_TIME` nao provam sozinhas que o codigo difere; compare fontes.
- Hashes iguais de extracoes truncadas provam apenas que o prefixo recebido e igual.
- Se o package novo e igual, mas compila somente na HML, procure objetos/pre-requisitos presentes
  na HML e ausentes na PRD.
- Pesquise quem alimenta a nova tabela:

  ```sql
  SELECT name, type, line, TRIM(text) texto
  FROM all_source
  WHERE owner = 'DBAMV'
    AND UPPER(text) LIKE '%DADOS_LAUDO_SA04%'
  ORDER BY name, type, line;
  ```

No caso validado, a HML possuia `INSERT`/`UPDATE` no body de `PKG_FFIS_LAUDO_INTEGRACAO` e leitura
em `PRC_FFIS_VALIDA_FINAL`, enquanto a PRD nao possuia essas referencias. Isso indica divergencia
de baseline. Nao copie packages inteiros da HML para PRD sem o pacote oficial e comparacao de
versao; corrigir a compilacao nao autoriza ampliar a mudanca para a integracao.

Uma tabela vazia na HML nao significa que seja descartavel: ela pode ser uma estrutura de apoio
alimentada apenas durante eventos de integracao. Identifique escritores antes de concluir que o
DDL isolado completa toda a funcionalidade.

## Correcao controlada em PRD

Qualquer DDL exige autorizacao explicita do DBA/responsavel. Antes da mudanca:

1. Confirme banco, servico, usuario e schema com `SYS_CONTEXT`.
2. Confirme que o objeto-alvo nao existe e que os tablespaces exigidos estao `ONLINE`.
3. Preserve o DDL oficial e os resultados do diagnostico.
4. Execute uma etapa por vez. Pare diante de qualquer erro inesperado.

Quando o unico pre-requisito comprovadamente ausente era a tabela, a sequencia validada foi:

1. criar a tabela com o DDL exato extraido da HML;
2. confirmar `TABLE VALID`;
3. consultar todos os dependentes e recompilar somente o objeto `INVALID`;
4. no caso observado, apenas:

   ```sql
   ALTER PACKAGE DBAMV.PKG_FFIS_PRODUCAO_AIH COMPILE BODY;
   ```

Nao recompile packages ja `VALID` sem necessidade. Nao substitua novamente a specification se o
erro estiver apenas no body e a causa for um objeto ausente.

## Validacao pos-correcao

Confirme:

- tabela e PK `VALID`/`ENABLED`;
- quantidade e tipos de colunas iguais a HML;
- specification e body de `PKG_FFIS_PRODUCAO_AIH` como `VALID`;
- `ALL_ERRORS` vazio;
- outros dependentes permanecem `VALID`;
- zero linhas na tabela e aceitavel imediatamente apos a criacao quando a HML tambem esta vazia.

Depois faca teste funcional pela tela, nesta ordem:

1. impressao do espelho da conta;
2. fechamento de uma conta autorizada;
3. captura de qualquer novo erro completo.

Nao chame diretamente rotinas de producao AIH por SQL para testar: packages desse fluxo podem
calcular, fechar, gerar job e executar `COMMIT` internamente. Use a tela e uma conta autorizada.

O caso foi considerado operacionalmente resolvido somente depois de: objeto criado, body
`VALID`, `ALL_ERRORS` vazio e validacao funcional por usuario. Ainda assim, quando HML e PRD
divergirem nas rotinas que alimentam a tabela, mantenha chamado com a MV para identificar o
pre-requisito oficial e alinhar os ambientes; nao amplie a correcao local sem essa orientacao.
