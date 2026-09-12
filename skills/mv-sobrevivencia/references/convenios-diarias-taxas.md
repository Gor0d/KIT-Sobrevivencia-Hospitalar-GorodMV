# Convênios, diárias, taxas e vigências

Playbook validado em produção para conectar volume assistencial ao cadastro de convênio, plano,
regra, grupo, tabela, procedimento, vigência e preço. Trate códigos locais como pistas datadas e
reconfirme-os no MCP.

## Invariantes

1. Confirme banco, serviço, instância, schema, usuário, empresa e data do banco.
2. Descubra objetos e colunas no dicionário/MCP; não confie em código aproximado informado pelo
   solicitante.
3. Não extraia identificação do paciente para rankings agregados.
4. Não misture códigos de convênio distintos. Famílias como Unimed permanecem separadas nos CSVs,
   salvo pedido explícito de consolidação.
5. Não invente preço, rota ou vigência ausente. Registre a lacuna como pendência.
6. Salve SQL nomeado, resposta bruta e critérios de precedência. Paginação precisa ter ordenação
   determinística.

## Ranking por internações

Registrar empresa, período, tipo de atendimento e métrica antes da consulta. Para top 10 de
internações, após confirmar o domínio:

- `ATENDIME.TP_ATENDIMENTO = 'I'`;
- `COUNT(DISTINCT CD_ATENDIMENTO)`;
- janela semiaberta: início inclusivo e dia seguinte à data final exclusivo;
- agrupamento por `CD_MULTI_EMPRESA`, `CD_CONVENIO` e nome cadastral;
- ordenação decrescente pela quantidade e código como desempate.

Não substituir internações por faturamento, contas, diárias ou pacientes. Se a empresa não estiver
explícita, apure por empresa antes de selecionar o top 10.

Quando houver códigos aproximados ou uma família de operadoras, pesquise `CONVENIO` por código e
nome e confira razão social e situação. Rankear códigos reais separadamente. Um membro fora do top
10 pode ser anexado como complemento, claramente identificado.

## Rota de faturamento

1. `CON_PLA`: planos ativos e `CD_REGRA`.
2. `REGRA`: descrição e contexto da regra.
3. `ITREGRA`: ligação regra + grupo → `CD_TAB_FAT`.
4. `GRU_PRO`: classificação de diárias e taxas.
5. `TAB_FAT`: identificação da tabela.
6. `PRO_FAT`: código, descrição, grupo e situação do procedimento.

Inventarie os grupos pela descrição antes de fixar códigos. Na BP foram observados grupos 1
(diárias), 2 (taxas de sala), 3 (equipamentos), 4 (enfermagem), 5 (administrativas) e 75
(serviços), mas as rotas ativas podem não conter todos. Planos ativos sem item correspondente em
`ITREGRA` são pendências; não gere linhas com valor zero.

## Preço e vigência

Em `VAL_PRO`, escolher a linha ativa com maior `DT_VIGENCIA` que não ultrapasse a data-base,
particionada por tabela e procedimento. Expor `VL_TOTAL` e preservar `VL_OPERACIONAL` e
`VL_HONORARIO` para auditoria.

Em `TAB_CONVENIO`, considerar somente linhas ativas, com início até a data-base e fim contratual
nulo ou ainda válido. Entre candidatos, priorizar:

1. plano exato antes de plano nulo;
2. regra exata antes de regra nula;
3. empresa exata antes de empresa nula;
4. vigência mais recente;
5. chave sequencial como desempate.

`TAB_CONVENIO.VL_TAB_CONVENIO` prevalece sobre `VAL_PRO.VL_TOTAL` quando aplicável. Inclua também
procedimentos existentes apenas no preço específico e identifique a origem do valor.

`ITREGRA.VL_PERCETUAL_PAGO` é parâmetro da rota. Não multiplique automaticamente o preço por esse
percentual sem pedido do usuário e confirmação da semântica local.

## Paginação e evidência

O MCP pode limitar resultados. Use páginas menores que o limite, com `ROW_NUMBER()` e ordenação por
regra, plano, grupo, tabela e procedimento. Salve SQL e resposta de cada página; encerre quando uma
página vier incompleta. Use colunas explícitas e o validador de somente leitura disponível.

## CSV para de-para

Gerar um arquivo por `CD_CONVENIO`, preferencialmente UTF-8 com BOM e delimitador `;`. Granularidade:
uma linha por plano, regra, grupo, tabela e procedimento.

Campos recomendados:

`ranking_internacoes`, `qt_internacoes`, `cd_convenio`, `nm_convenio`, `cd_con_pla`,
`ds_con_pla`, `cd_regra`, `ds_regra`, `cd_gru_pro`, `ds_gru_pro`, `categoria`, `cd_tab_fat`,
`ds_tab_fat`, `cd_pro_fat`, `ds_pro_fat`, `dt_vigencia`, `dt_vigencia_final`, `valor`,
`vl_total_tabela`, `vl_operacional`, `vl_honorario`, `vl_percentual_pago`, `origem_valor`,
`sn_procedimento_ativo`, `data_extracao`.

Validar quantidade contra manifesto, único convênio por arquivo, duplicidade na chave
plano/regra/grupo/tabela/procedimento, campos obrigatórios, ausência de vigência futura, codificação
e delimitador.

## Parecer administrativo

Comece pelo resultado: empresa, período e ranking. Explique brevemente seleção da vigência e
precedência de `TAB_CONVENIO`. Destaque correções de códigos, rotas compartilhadas, preços
específicos e planos sem rota. Para listas extensas, consolide no PDF os planos com o mesmo código,
vigência, valor e origem; mantenha a granularidade completa nos CSVs.

## Esquema confirmado

| Objeto | Campos principais | Papel |
|---|---|---|
| `ATENDIME` | atendimento, tipo, data, convênio, plano, empresa | Produção e ranking. |
| `MULTI_EMPRESAS` | código e descrição | Empresa. |
| `CONVENIO` | código, nome, razão social, ativo | Convênio. |
| `CON_PLA` | convênio, plano, descrição, regra, ativo | Plano e regra. |
| `REGRA` | código e descrição | Regra. |
| `ITREGRA` | regra, grupo, tabela, percentual, base | Rota grupo → tabela. |
| `GRU_PRO` | código, descrição, tipo | Grupo. |
| `TAB_FAT` | código e descrição | Tabela. |
| `PRO_FAT` | código, descrição, grupo, ativo | Procedimento. |
| `VAL_PRO` | tabela, procedimento, vigência e componentes de valor | Preço geral. |
| `TAB_CONVENIO` | convênio, plano, regra, empresa, procedimento, vigências e valor | Preço específico. |

Confirme nomes e tipos no dicionário; versões do MV podem divergir.

## Observações locais da BP — 19/08/2026

- Empresa 1: `HOSPITAL D LUIZ I`.
- Unimed: código 8 = `UNIMED - BELEM`; 65 = `UNIMED - INTERCAMBIO`; 80 = `UNIMED - 879`.
  Na data observada, usavam regra 119 e tabela 26, com preços específicos distintos.
- GEAP: código 19; regras 95 e 146; tabela 19 para diárias e taxas.
- Particular: código 40; regra 123/tabela 25 e regra 111/tabela 38. O plano ativo 4 —
  `ACORDO APARTAMENTO`, regra 142 — `REGRA ISSA`, não apresentou rota de diárias/taxas.
- SUS - INTERNAÇÃO: código 1; havia apenas rota de diárias pela tabela 50 e dois procedimentos com
  preço vigente.

Nunca transporte automaticamente esses códigos ou achados para outra empresa, banco ou data-base.
