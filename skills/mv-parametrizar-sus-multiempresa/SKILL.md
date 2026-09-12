---
name: mv-parametrizar-sus-multiempresa
description: Mapear, parametrizar, testar e promover configurações SUS multiempresa no Soul MV/Oracle, incluindo UPS, SIGTAP, valores contratuais, convênios, planos, regras, centros de custo e migração de contas. Usar quando o trabalho envolver HML antes de PRD, CD_MULTI_EMPRESA, FFAS, BPA, APAC, PAT, OCI, POA, PMAE ou contratos com percentuais sobre SIGTAP.
---

# Parametrizar SUS Multiempresa no MV

## Fluxo obrigatório

1. Confirmar ambiente, empresa, convênio, CNES e CNPJ.
2. Começar por consultas `SELECT` e registrar a linha de base.
3. Separar valores oficiais SIGTAP de valores contratuais.
4. Executar cada alteração na HML com pré-validação, transação, pós-validação e rollback automático em erro.
5. Aplicar um procedimento piloto antes de cargas em lote.
6. Validar na interface MV, no faturamento, no financeiro e na contabilidade.
7. Documentar SQL, parâmetros, resultado, código gerado e pendências.
8. Preparar PRD somente após homologação formal; nunca trocar códigos de empresa por substituição cega.

## Proteções

- Tratar HML e PRD como ambientes distintos.
- Nunca executar escrita em PRD por um MCP configurado para HML.
- Não alterar tabelas ou regras compartilhadas sem análise de impacto.
- Não usar `MAX(id)+1` quando existir sequência oficial.
- Não cadastrar valor sem código, vigência e origem contratual aprovados.
- Não migrar contas por simples atualização de `CD_MULTI_EMPRESA`.
- Confirmar dependências antes de qualquer rollback destrutivo.
- Redigir scripts idempotentes: abortar quando empresa, CNES, CNPJ ou chave funcional já existir.

## Escolher a estrutura correta

- Usar `PROCEDIMENTO_SUS_VALOR` como fonte dos valores oficiais SUS/SIGTAP.
- Avaliar `PROCEDIMENTO_SUS_VALOR_CONTRAT` para valores contratuais por empresa, UPS, procedimento e vigência.
- Usar `UNIDADE_PRESTADORA_SERVICO` para identificar a UPS.
- Interpretar `TP_UPS`: `H = SMS/municipal`; `E = Estado`. Não usar esse campo para modalidade assistencial.
- Separar hospitalar e ambulatorial em convênios, planos e regras.
- Usar `SN_INTEGRACAO = 'S'` somente para a UPS padrão da empresa, após confirmar que não existe outra.

## Evidências mínimas

Registrar para cada etapa:

- data e ambiente;
- comando ou script executado;
- parâmetros funcionais;
- resultado da pré-validação;
- identificador gerado;
- resultado da pós-validação;
- `COMMIT` ou `ROLLBACK`;
- validação manual pendente;
- adaptação necessária para PRD.

## Referências

Ler [references/mv-sus-schema.md](references/mv-sus-schema.md) ao trabalhar com UPS, SIGTAP ou valores contratuais.

Se você mantém documentação própria de um projeto multiempresa em andamento (ambientes,
convênio, CNES/CNPJ do gestor, decisões já tomadas), trate-a como fonte viva e releia antes de
cada etapa — não é conteúdo para versionar neste kit público.
