# MCP de leitura no Oracle MV

As skills funcionam sem MCP — nesse modo o agente escreve o SQL e você roda no DBeaver e cola
o resultado de volta. Mas com um MCP somente-leitura o ciclo fecha sozinho e o ganho é grande.

**Implementação pronta:** o kit já traz uma em [`mcp-server/`](mcp-server) — é só instalar e
apontar para o seu Oracle (veja o [README do mcp-server](mcp-server/README.md)). O restante
deste documento descreve o contrato que ela segue, útil se você preferir escrever a sua.

## O contrato esperado

Um servidor MCP chamado `soul-mv-erp` expondo, no mínimo:

| Ferramenta | Faz |
|---|---|
| `listar_tabelas(filtro)` | lista tabelas do schema por nome |
| `descrever_tabela(nome_tabela)` | colunas, tipos, nulidade, comentário |
| `executar_sql_livre(sql)` | executa **apenas `SELECT`** |

Restrições que as skills assumem — e que você deve manter:

- **Só `SELECT`.** Qualquer DML é recusado pelo servidor, não pelo bom senso do agente.
- **`WITH`/CTE é bloqueado** por muitos validadores simples de "começa com SELECT". As skills
  já escrevem subquery inline em vez de CTE por causa disso.
- **Limite de linhas** (~500). Consulta ampla deve ser agregada no banco, não no agente.
- **Timeout de consulta**, para não prender sessão em produção.

## Registro no Claude Code

```bash
claude mcp add soul-mv-erp --scope user -- python C:/caminho/mcp-server/server.py
```

## Registro no Codex

Adicione o servidor em `~/.codex/config.toml`, na seção de MCP servers, apontando para o
mesmo executável.

## Variáveis de ambiente

O servidor lê a conexão de um `.env` **que nunca vai para o repositório**:

```dotenv
ORACLE_HOST=
ORACLE_PORT=1521
ORACLE_SERVICE=
ORACLE_USER=
ORACLE_PASSWORD=
ORACLE_SCHEMA=DBAMV
MAX_ROWS=500
QUERY_TIMEOUT_MS=30000
```

Use um usuário Oracle com **apenas `SELECT`** nas tabelas necessárias. Não reaproveite o
usuário dono do schema: a garantia mais confiável de que nada será alterado é o banco não
permitir.

## Conferindo onde você está

Antes de qualquer análise, rode:

```sql
SELECT SYS_CONTEXT('USERENV','DB_NAME')       AS banco,
       SYS_CONTEXT('USERENV','SESSION_USER')  AS usuario,
       SYS_CONTEXT('USERENV','SERVER_HOST')   AS servidor
  FROM DUAL;
```

Se o resultado for produção, trate como produção — independente do que diga o nome da conexão.
