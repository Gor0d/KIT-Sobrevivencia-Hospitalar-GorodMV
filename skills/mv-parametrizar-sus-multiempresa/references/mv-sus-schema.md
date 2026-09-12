# Referência MV SUS

## Ambientes de um projeto multiempresa (exemplo de formato, não valores reais)

Ao iniciar um projeto SUS multiempresa novo, registre os identificadores do contrato/gestor
nesse mesmo formato antes de tocar em qualquer tabela — eles nunca devem ser hardcoded no
código nem versionados aqui:

- HML: `CD_MULTI_EMPRESA = <n>`.
- PRD: `CD_MULTI_EMPRESA = <n>`.
- Convênio (HML): `CD_CONVENIO = <n>`.
- CNES do gestor/contrato: `<confirmar no cadastro>`.
- CNPJ do gestor/contrato: `<confirmar no cadastro>`.

## Tabelas principais

| Tabela | Finalidade |
|---|---|
| `MULTI_EMPRESAS` | Empresa corrente e parâmetros gerais |
| `CONVENIO` | Convênio e tipo hospitalar/ambulatorial |
| `CON_PLA` | Planos do convênio e regra padrão |
| `EMPRESA_CON_PLA` | Vínculo do plano/regra com a empresa |
| `REGRA` / `ITREGRA` | Regras e tabelas de cobrança |
| `PROCEDIMENTO_SUS` | Cadastro do procedimento SIGTAP |
| `PROCEDIMENTO_SUS_EMPRESA` | Habilitação do procedimento por empresa |
| `PROCEDIMENTO_SUS_VALOR` | Valores oficiais SUS |
| `PROCEDIMENTO_SUS_VALOR_CONTRAT` | Valores contratuais por empresa/UPS/vigência |
| `UNIDADE_PRESTADORA_SERVICO` | UPS e identificação estadual/municipal |

## UPS

Campos obrigatórios de `UNIDADE_PRESTADORA_SERVICO`:

- `CD_UPS`: usar `SEQ_UNIDADE_PRESTADORA_SERVICO.NEXTVAL`.
- `SN_ATIVO`: `S` ou `N`.
- `TP_UPS`: `H` para SMS/municipal; `E` para Estado.
- `TP_CONTROLE_TETO_CONTRATO`: `N`, `E`, `F` ou `B`.
- `SN_INTEGRACAO`: `S` ou `N`.

Antes de inserir, pesquisar por empresa, CNES e CNPJ. A rotina FFAS seleciona a UPS ativa com `SN_INTEGRACAO='S'` e a empresa corrente.

## Valores contratuais SUS

Chave funcional de `PROCEDIMENTO_SUS_VALOR_CONTRAT`:

- `CD_MULTI_EMPRESA`;
- `CD_UPS`;
- `CD_PROCEDIMENTO`;
- `DT_VIGENCIA`.

Essa combinação é a chave primária. A tabela não possui triggers na instalação mapeada. Existem FKs para `MULTI_EMPRESAS`, `UNIDADE_PRESTADORA_SERVICO` e `PROCEDIMENTO_SUS`.

Valores ambulatoriais disponíveis:

- `VL_SERVICO_AMBULATORIAL`;
- `VL_SERVICO_PROFISSIONAL_AMB`;
- `VL_SERVICO_ANESTESIA_AMB`;
- `VL_TOTAL_AMBULATORIAL`.

Para “100% em cima da SIGTAP”, validar formalmente se o esperado é `VL_TOTAL_AMBULATORIAL × 2` e testar um procedimento antes da carga.

Ao preparar o piloto:

1. Confirmar vínculo em `PROCEDIMENTO_SUS_EMPRESA`.
2. Selecionar a maior `DT_VIGENCIA` oficial menor ou igual à data corrente.
3. Verificar ausência da chave contratual antes do `INSERT`.
4. Multiplicar componentes e total somente quando essa regra estiver formalmente aprovada.
5. Testar cálculo de conta antes da carga em lote.
