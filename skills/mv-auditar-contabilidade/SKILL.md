---
name: mv-auditar-contabilidade
description: Investigar rotinas contábeis, classificações, documentos e divergências no Soul MV/Oracle com evidências auditáveis e, mediante autorização explícita, executar correções unitárias controladas por rotina nativa, transação reversível e conferência antes do commit. Usar em análises ou correções de produto, espécie, classe, subclasse, item de resultado, conta contábil, solicitação, ordem de compra, entrada, estoque, patrimônio, tombamento, auditoria de usuários, cadeia documental, materialidade, conciliação, fechamento contábil, NFS-e ou regras do Sentinela MV.
---

# Auditar Contabilidade no Soul MV

## Princípios obrigatórios

1. Tratar Oracle MV como somente leitura por padrão.
2. Executar escrita somente com autorização explícita para o caso e após cumprir integralmente
   a janela de mudança controlada de `references/oracle-safety.md`.
3. Preferir tela, API ou package nativo do MV. Não reproduzir manualmente efeitos financeiros
   ou contábeis que pertencem a trigger/package não dominado.
4. Confirmar ambiente e identidade da sessão antes de analisar documentos.
5. Consultar o dicionário Oracle antes de depender de tabela, coluna, chave ou índice.
6. Usar arquivos SQL nomeados, colunas explícitas, bind variables, timeout e recorte seletivo.
7. Separar fato, cálculo, inferência, recomendação e informação ausente.
8. Não atribuir culpa. Identificar somente o papel associado ao registro e o limite da evidência.

## Fluxo de investigação

1. **Delimitar o caso:** registrar ambiente, empresa quando disponível, produto, documentos,
   período, valor e pergunta contábil.
2. **Validar a sessão:** consultar `DB_NAME`, `SERVICE_NAME`, `INSTANCE_NAME`,
   `CURRENT_SCHEMA` e usuário da sessão sem expor credenciais.
3. **Descobrir capacidades:** verificar objetos e colunas em `ALL_TAB_COLUMNS`; confirmar
   constraints e índices em `ALL_CONSTRAINTS`, `ALL_CONS_COLUMNS`, `ALL_INDEXES` e
   `ALL_IND_COLUMNS`.
4. **Coletar da chave para fora:** começar pelo produto ou documento exato; reconstruir
   produto → solicitação → ordem → entrada → lote → bem → lançamento. Não varrer tabelas
   inteiras para descobrir um caso.
5. **Conferir classificação:** comparar espécie, classe, subclasse, item de resultado,
   NCM, unidade, fator, status do produto e produtos semelhantes.
6. **Conferir contexto contábil:** localizar item de resultado e conta somente nas fontes
   confirmadas para a versão do MV; não inferir conta a partir de descrição.
7. **Conferir patrimônio:** distinguir indicação de material permanente, quantidade tombada
   e bem efetivamente vinculado.
8. **Conferir autoria:** separar criador do cadastro, criador/autorizador da ordem,
   usuário do item, recebedor, usuário técnico, trigger/package e decisor contábil.
9. **Produzir conclusão neutra:** enumerar evidências, lacunas, impacto potencial,
   confiança e ação recomendada.
10. **Registrar reprodutibilidade:** salvar nomes das queries, parâmetros não sensíveis,
    duração, quantidade de linhas e data da captura.
11. **Classificar a mudança:** declarar impacto baixo, médio, alto ou indeterminado antes de
    escrever. Não executar impacto alto ou indeterminado.
12. **Executar e conferir:** abrir transação controlada, aplicar uma única chave piloto,
    conferir invariantes e efetuar `COMMIT` apenas se todas forem satisfeitas; caso contrário,
    executar `ROLLBACK` e registrar a divergência.

## Roteamento de referências

- Ler [references/oracle-safety.md](references/oracle-safety.md) antes de criar ou executar
  SQL Oracle.
- Ler [references/soulmv-schema.md](references/soulmv-schema.md) para produtos, compras,
  entradas, patrimônio e usuários já confirmados no ambiente ORASML.
- Ler [references/accounting-investigation.md](references/accounting-investigation.md)
  ao redigir uma análise, regra, parecer, evidência ou contexto para decisão contábil.

## Uso dos recursos

Executar `scripts/check_sql_readonly.py <arquivo-ou-diretório>` antes de aceitar novas
queries de investigação. Tratar qualquer reprovação como bloqueio para o fluxo somente leitura;
não usar a reprovação como autorização implícita de escrita. Mudanças autorizadas devem ficar em
arquivo separado, ser revisadas manualmente conforme `oracle-safety.md` e nunca ser misturadas
às queries de evidência.

Ao trabalhar no projeto Sentinela MV, reutilizar seu `OracleReadOnlyClient`,
`SchemaInspector` e os SQL em `backend/app/database/oracle/sql`. Manter
`USE_DEMO_DATA=true` até o ambiente e os documentos-piloto serem homologados.
