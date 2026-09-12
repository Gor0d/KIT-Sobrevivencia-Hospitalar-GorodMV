# mcp-server — soul-mv-erp

Implementação de referência do MCP somente-leitura descrito em [../MCP.md](../MCP.md).
É o servidor que faz as skills do kit renderem de verdade: sem ele, o agente escreve SQL
e você cola o resultado na mão; com ele, o ciclo fecha sozinho.

Roda 100% local, contra o Oracle do seu hospital — nenhum dado sai da sua rede.

## O que ele expõe

| Ferramenta | Faz |
|---|---|
| `buscar_paciente` | busca por nome, CPF ou prontuário |
| `listar_internacoes_ativas` | pacientes internados, com leito/unidade/setor/convênio |
| `resumo_ocupacao_setores` | ocupação por unidade (ocupados/vagos/limpeza/outros) |
| `detalhar_unidade` | leito a leito de uma unidade específica |
| `faturamento_por_convenio` | faturamento do mês agrupado por convênio |
| `contas_a_receber` | títulos a vencer nos próximos N dias |
| `agenda_do_dia` | agenda ambulatorial por data e/ou médico |
| `cirurgias_programadas` | mapa cirúrgico por data |
| `listar_tabelas` / `descrever_tabela` | exploração de schema (`ALL_TABLES`, `ALL_TAB_COLUMNS`) |
| `executar_sql_livre` | qualquer `SELECT` ad-hoc, para o que as ferramentas acima não cobrem |

Garantias que o servidor aplica (não dependem do bom senso do agente):

- **Só `SELECT`.** `executar_sql_livre` recusa qualquer coisa que não comece com `SELECT`.
- **Limite de linhas** por consulta (`MAX_ROWS`, padrão 500).
- **Timeout de round-trip** (`QUERY_TIMEOUT_MS`, padrão 30s) — não prende sessão em produção.

## Instalação

**Windows (PowerShell)**
```powershell
cd mcp-server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # preencha com as credenciais do SEU banco
```

**Linux / macOS / Git Bash**
```bash
cd mcp-server
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha com as credenciais do SEU banco
```

Use um usuário Oracle **com apenas `SELECT`** nas tabelas necessárias — não reaproveite o
usuário dono do schema. A garantia mais confiável de que nada será alterado é o banco não
permitir, não o código.

## Registro

**Claude Code**
```bash
claude mcp add soul-mv-erp --scope user -- python /caminho/mcp-server/server.py
```

**Codex** — adicione o executável na seção de MCP servers de `~/.codex/config.toml`.

## Limitações conhecidas

- Nomes de tabela/coluna seguem o dicionário padrão MV. Instalações com customização de
  schema (view própria, coluna renomeada) podem exigir ajuste pontual — normalmente
  1-2 linhas por ferramenta afetada.
- `executar_sql_livre` valida sintaxe (`starts with SELECT`), não substitui permissão de
  banco. O controle real é o usuário Oracle somente-leitura.

## Precisa que alguém instale, valide contra o seu schema e treine sua equipe?

O código é MIT — pode instalar e adaptar sozinho. Para quem prefere não gastar o próprio
tempo de TI nisso, oferecemos instalação, validação de schema, ferramentas customizadas e
suporte com contrato. Veja a seção "Suporte pago" no [README principal](../README.md).
