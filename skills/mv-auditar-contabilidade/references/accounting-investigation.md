# Investigação e comunicação contábil

## Perguntas mínimas

1. O que foi comprado e qual código foi usado?
2. O produto estava ativo na data do documento?
3. Qual unidade e fator foram aplicados?
4. Quais espécie, classe, subclasse, item de resultado e NCM estavam vigentes?
5. Há produtos semelhantes e como estão classificados?
6. Há solicitação, ordem, entrada, lote e bem vinculados?
7. Qual quantidade, preço, valor total e materialidade?
8. Quem aparece em cada etapa e em qual papel?
9. A auditoria indica operação manual, usuário técnico, trigger ou package?
10. Há tombamento, conta ou decisão contábil histórica?
11. Quais evidências faltam e qual é a confiança da recomendação?

## Estrutura da resposta

### Fatos confirmados

Relacionar somente valores diretamente sustentados por registro ou cálculo reproduzível.

### Cálculos

Expor fórmula, entradas, unidade, fator e resultado. Exemplo:
`(quantidade comprada − solicitada) × fator = diferença em unidade-base`.

### Inferências

Usar linguagem condicional: “pode indicar”, “é compatível com”, “necessita validação”.
Não transformar similaridade textual, ausência de vínculo ou usuário técnico em fato conclusivo.

### Impacto potencial

Descrever efeitos possíveis em estoque, patrimônio, classificação, item de resultado,
conta, materialidade, competência ou fechamento.

### Recomendação

Indicar setor, validação necessária, documento a conferir e condição de encerramento.
O sistema sugere e registra; nunca corrige o MV diretamente.

## Linguagem neutra

Preferir:

- “Usuário associado à criação da ordem.”
- “Responsável registrado pelo recebimento.”
- “Operação registrada por usuário técnico.”
- “Classificação necessita validação.”
- “Não há evidência suficiente para atribuição individual.”

Evitar “culpado”, “erro do usuário”, “fraude” ou “irregularidade” sem investigação formal
e evidência apropriada.

## Evidência mínima de uma divergência

- Identificadores e período.
- Snapshot das colunas relevantes.
- Nome da query e objetos consultados.
- Linha documental e etapas ausentes.
- Classificação atual e referência comparável.
- Cálculo reproduzível, quando aplicável.
- Limitações e campos não confirmados.
- Data da captura e ambiente.

