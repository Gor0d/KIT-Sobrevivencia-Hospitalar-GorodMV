# Segurança e método Oracle

## Modo padrão: somente leitura

Somente `SELECT`, inclusive consultas ao dicionário. Abrir a transação com
`SET TRANSACTION READ ONLY` quando o driver e a sessão permitirem.

## Janela de mudança controlada

Permitir DML ou chamada de rotina nativa somente quando todas as condições forem verdadeiras:

1. O usuário autorizou explicitamente a escrita para a chave e ambiente atuais.
2. Banco, serviço, instância, schema, empresa e usuário técnico foram confirmados.
3. O alvo é unitário e identificado por PK/chave de negócio; não há lote nem filtro aberto.
4. Existe snapshot anterior suficiente para provar valores, vínculos e estados afetados.
5. A operação é idempotente ou possui guarda que impeça duplicidade.
6. Preferir package, API ou tela oficial do MV cuja assinatura e efeitos tenham sido inspecionados.
7. Confirmar que package/trigger chamado não possui `COMMIT`, `ROLLBACK` ou transação autônoma.
8. Definir invariantes pós-operação e uma condição objetiva de rollback antes de executar.
9. Executar sem autocommit, com timeout, `SAVEPOINT` e uma única chave piloto.
10. Conferir as invariantes na mesma sessão antes do `COMMIT`.

Em PRD, exigir adicionalmente rotina nativa já ensaiada em HML ou evidência funcional equivalente.
Se HML não reproduzir o caso, classificar o impacto como indeterminado e não executar.

### Exceção controlada de persistência fiscal em HML

Uma criação fiscal unitária em HML pode ser persistida mesmo envolvendo numeração fiscal
somente quando todas as condições abaixo forem satisfeitas:

1. O mesmo contrato, chave equivalente e conjunto de triggers passou antes por ensaio com
   `SAVEPOINT`, invariantes completas e rollback confirmado em nova conexão.
2. O usuário forneceu uma segunda autorização explícita para persistir a chave HML exata.
3. Nenhuma conta, parcela, recebimento ou lançamento contábil novo será criado.
4. O DML usa PK, guarda idempotente, bloqueio do contador e confere valores antes do `COMMIT`.
5. A persistência é confirmada em nova conexão e registrada como evidência de homologação.

Essa exceção não se aplica a PRD, lote, DDL, alteração de package/trigger/sequence, desligamento
de constraints ou operação com transação autônoma efetivamente acionada.

### Classificação de impacto

- **Baixo:** atualização unitária, reversível, sem efeito financeiro/contábil e com invariantes completas.
- **Médio:** rotina nativa unitária com triggers conhecidas, sem recriar documentos financeiros e
  com ensaio anterior. Pode executar com autorização específica.
- **Alto:** cria ou altera conta, parcela, recebimento, estoque, patrimônio, lançamento contábil,
  numeração fiscal ou múltiplas tabelas sem rotina nativa comprovada. Não executar diretamente.
- **Indeterminado:** fonte incompleta, `COMMIT` interno, transação autônoma, trigger dinâmica ou
  impossibilidade de ensaio/rollback. Não executar.

## Comandos permanentemente proibidos

Bloquear `CREATE`, `ALTER`, `DROP`, `TRUNCATE`, `GRANT`, `REVOKE`, alteração de trigger,
sequence ou package, desligamento de constraints e DML sem `WHERE` seletivo. Nunca usar HML como
autorização implícita: ela reduz risco, mas ainda exige autorização e validação.

Não executar `COMMIT` quando a conferência indicar alteração inesperada em valores, conta,
parcelas, recebimentos, contabilização, numeração fiscal, empresa ou quantidade de registros.

## Padrão de query

- Arquivo `.sql` separado com nome, descrição, parâmetros, objetos e observação de performance.
- Lista explícita de colunas; nunca `SELECT *`.
- Bind variables para todo valor externo.
- Filtro por chave ou período curto.
- Sem concatenação de schema, coluna, ordenação ou valores vindos do usuário.
- Timeout configurado no driver.
- Logar nome da query, duração, quantidade de linhas e erro; nunca senha, token ou DSN completo
  quando o relatório for compartilhado.

## Ordem de validação

1. Confirmar banco, serviço, instância e schema.
2. Confirmar a existência do objeto.
3. Confirmar colunas, tipos e nulabilidade.
4. Confirmar PK, FKs e índices.
5. Executar a consulta para uma chave piloto.
6. Conferir o resultado com a interface MV ou fonte funcional.
7. Só então ampliar período ou lote.

## Ordem de execução de uma mudança autorizada

1. Salvar snapshot anterior e contagens das tabelas relacionadas.
2. Inspecionar fonte e dependências da rotina nativa, inclusive commits internos.
3. Preparar arquivo de mudança separado, com binds e guarda idempotente.
4. Iniciar transação, criar `SAVEPOINT` e executar para uma chave.
5. Repetir as queries de evidência na mesma sessão.
6. Comparar invariantes e quantidade de linhas alteradas.
7. Efetuar `COMMIT` somente se tudo conferir; caso contrário, `ROLLBACK`.
8. Abrir nova conexão somente leitura e confirmar o estado persistido.

Após três falhas consecutivas, interromper novas consultas e tratar a integração como degradada.
Continuar a análise apenas com snapshots já persistidos, indicando possível desatualização.
