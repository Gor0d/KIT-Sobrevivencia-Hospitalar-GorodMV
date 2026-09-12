"""
MCP Server — Soul MV / MV ERP (Oracle, schema DBAMV)
Expõe ferramentas de consulta somente-leitura para uso com Claude Code, Codex
ou qualquer cliente MCP compatível. Implementação de referência do contrato
documentado em ../MCP.md.
"""

import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools.soul_mv import (
    buscar_paciente,
    listar_internacoes_ativas,
    resumo_ocupacao_setores,
    detalhar_unidade,
    faturamento_por_convenio,
    contas_a_receber,
    agenda_do_dia,
    cirurgias_programadas,
    listar_tabelas,
    descrever_tabela,
    executar_sql_livre,
)

app = Server("soul-mv-erp")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="buscar_paciente",
            description="Busca pacientes no Soul MV por nome, CPF ou número de prontuário.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome":       {"type": "string", "description": "Nome ou parte do nome do paciente"},
                    "cpf":        {"type": "string", "description": "CPF do paciente (com ou sem formatação)"},
                    "prontuario": {"type": "string", "description": "Número do prontuário"},
                },
            },
        ),
        Tool(
            name="listar_internacoes_ativas",
            description="Lista pacientes atualmente internados com leito, unidade, setor e convênio.",
            inputSchema={
                "type": "object",
                "properties": {"cd_unid_int": {"type": "integer", "description": "Filtra por código de unidade de internação"}},
            },
        ),
        Tool(
            name="resumo_ocupacao_setores",
            description="Mostra taxa de ocupação atual por unidade/setor hospitalar (leitos ocupados, disponíveis e total).",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="detalhar_unidade",
            description="Detalha leito a leito o status de ocupação de uma unidade de internação específica.",
            inputSchema={
                "type": "object",
                "required": ["cd_unid_int"],
                "properties": {"cd_unid_int": {"type": "integer", "description": "Código da unidade de internação (CD_UNID_INT)"}},
            },
        ),
        Tool(
            name="faturamento_por_convenio",
            description="Faturamento do mês agrupado por convênio.",
            inputSchema={
                "type": "object",
                "required": ["mes", "ano"],
                "properties": {
                    "mes": {"type": "integer", "description": "Mês (1-12)"},
                    "ano": {"type": "integer", "description": "Ano com 4 dígitos"},
                },
            },
        ),
        Tool(
            name="contas_a_receber",
            description="Lista contas a receber com vencimento nos próximos N dias.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dias_vencimento": {
                        "type": "integer",
                        "description": "Número de dias à frente para verificar vencimentos (padrão: 30)",
                    },
                },
            },
        ),
        Tool(
            name="agenda_do_dia",
            description="Consultas agendadas para um dia específico ou para o dia de hoje, opcionalmente filtradas por médico.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_str": {"type": "string", "description": "Data no formato DD/MM/YYYY (padrão: hoje)"},
                    "medico":   {"type": "string", "description": "Nome ou parte do nome do médico"},
                },
            },
        ),
        Tool(
            name="cirurgias_programadas",
            description="Lista cirurgias programadas para uma data específica ou para os próximos 7 dias.",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_str": {"type": "string", "description": "Data no formato DD/MM/YYYY (padrão: próximos 7 dias)"},
                },
            },
        ),
        Tool(
            name="listar_tabelas",
            description="Lista as tabelas disponíveis no banco do Soul MV. Útil para explorar o schema.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filtro": {"type": "string", "description": "Filtro por nome de tabela (ex: 'FATURA')"},
                },
            },
        ),
        Tool(
            name="descrever_tabela",
            description="Mostra as colunas e tipos de uma tabela do Soul MV.",
            inputSchema={
                "type": "object",
                "required": ["nome_tabela"],
                "properties": {
                    "nome_tabela": {"type": "string", "description": "Nome exato da tabela (ex: 'PACIENTE')"},
                },
            },
        ),
        Tool(
            name="executar_sql_livre",
            description=(
                "Executa um SQL SELECT personalizado no banco do Soul MV. "
                "Use para perguntas que as ferramentas específicas não cobrem. "
                "APENAS SELECT é permitido."
            ),
            inputSchema={
                "type": "object",
                "required": ["sql"],
                "properties": {
                    "sql": {"type": "string", "description": "Query SELECT a ser executada"},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=f"Erro ao executar '{name}': {e}")]


def _dispatch(name: str, args: dict):
    match name:
        case "buscar_paciente":
            return buscar_paciente(**args)
        case "listar_internacoes_ativas":
            return listar_internacoes_ativas(cd_unid_int=args.get("cd_unid_int"))
        case "resumo_ocupacao_setores":
            return resumo_ocupacao_setores()
        case "detalhar_unidade":
            return detalhar_unidade(cd_unid_int=args["cd_unid_int"])
        case "faturamento_por_convenio":
            return faturamento_por_convenio(mes=args["mes"], ano=args["ano"])
        case "contas_a_receber":
            return contas_a_receber(dias_vencimento=args.get("dias_vencimento", 30))
        case "agenda_do_dia":
            return agenda_do_dia(**args)
        case "cirurgias_programadas":
            return cirurgias_programadas(**args)
        case "listar_tabelas":
            return listar_tabelas(filtro=args.get("filtro", ""))
        case "descrever_tabela":
            return descrever_tabela(nome_tabela=args["nome_tabela"])
        case "executar_sql_livre":
            return executar_sql_livre(sql=args["sql"])
        case _:
            raise ValueError(f"Ferramenta desconhecida: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
