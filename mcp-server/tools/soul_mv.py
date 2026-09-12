"""
Ferramentas de consulta somente-leitura para o Soul MV / MV ERP (Oracle, schema DBAMV).
Cada função representa uma área funcional do ERP hospitalar. Nomes de tabela e coluna
seguem o dicionário padrão do produto MV — não há nada aqui específico de uma instalação.
"""

from .database import execute_query, get_schema


# ---------------------------------------------------------------------------
# PACIENTES
# ---------------------------------------------------------------------------

def buscar_paciente(nome: str = "", cpf: str = "", prontuario: str = "") -> list[dict]:
    """Busca pacientes por nome, CPF ou número de prontuário."""
    schema = get_schema()
    filters = []
    params = {}

    if nome:
        filters.append("UPPER(p.NM_PACIENTE) LIKE UPPER(:nome)")
        params["nome"] = f"%{nome}%"
    if cpf:
        filters.append("p.NR_CPF = :cpf")
        params["cpf"] = cpf.replace(".", "").replace("-", "")
    if prontuario:
        filters.append("p.CD_PACIENTE = :prontuario")
        params["prontuario"] = prontuario

    where = f"WHERE {' AND '.join(filters)}" if filters else "WHERE ROWNUM <= 50"

    sql = f"""
        SELECT p.CD_PACIENTE        AS prontuario,
               p.NM_PACIENTE        AS nome,
               p.DT_NASCIMENTO      AS nascimento,
               p.NR_CPF             AS cpf,
               p.NM_MAE             AS mae,
               p.DS_CONVENIO        AS convenio
          FROM {schema}.PACIENTE p
         {where}
         ORDER BY p.NM_PACIENTE
    """
    return execute_query(sql, params, max_rows=100)


# ---------------------------------------------------------------------------
# INTERNAÇÕES / OCUPAÇÃO
# ---------------------------------------------------------------------------

def listar_internacoes_ativas(cd_unid_int: int | None = None) -> list[dict]:
    """Lista pacientes atualmente internados, opcionalmente filtrados por unidade."""
    schema = get_schema()
    filtro_unidade = " AND u.CD_UNID_INT = :cd_unid_int" if cd_unid_int is not None else ""
    params = {"cd_unid_int": cd_unid_int} if cd_unid_int is not None else None
    sql = f"""
        SELECT i.CD_ATENDIMENTO      AS atendimento,
               p.NM_PACIENTE         AS paciente,
               p.CD_PACIENTE         AS prontuario,
               l.DS_LEITO            AS leito,
               u.CD_UNID_INT         AS cd_unid_int,
               u.DS_UNID_INT         AS unidade_internacao,
               s.NM_SETOR            AS setor,
               i.DT_ATENDIMENTO      AS dt_internacao,
               i.DT_PREVISTA_ALTA    AS dt_prevista_alta,
               c.NM_CONVENIO         AS convenio
          FROM {schema}.ATENDIME i
          JOIN {schema}.PACIENTE p    ON p.CD_PACIENTE   = i.CD_PACIENTE
          LEFT JOIN {schema}.LEITO l  ON l.CD_LEITO      = i.CD_LEITO
          LEFT JOIN {schema}.UNID_INT u ON u.CD_UNID_INT = l.CD_UNID_INT
          LEFT JOIN {schema}.SETOR s  ON s.CD_SETOR = u.CD_SETOR
          LEFT JOIN {schema}.CONVENIO c  ON c.CD_CONVENIO  = i.CD_CONVENIO
         WHERE i.SN_INTERNADO = 'S'
               {filtro_unidade}
         ORDER BY u.DS_UNID_INT, l.DS_LEITO
    """
    return execute_query(sql, params, max_rows=500)


def resumo_ocupacao_setores() -> list[dict]:
    """Retorna ocupação atual por unidade de internação (leitos ocupados x total)."""
    schema = get_schema()
    sql = f"""
        SELECT u.CD_UNID_INT          AS cd_unid_int,
               u.DS_UNID_INT          AS unidade_internacao,
               s.NM_SETOR             AS setor,
               COUNT(l.CD_LEITO)      AS total_leitos,
               SUM(CASE WHEN l.TP_OCUPACAO IN ('O', 'I') THEN 1 ELSE 0 END) AS ocupados,
               SUM(CASE WHEN l.TP_OCUPACAO = 'V' THEN 1 ELSE 0 END) AS vagos,
               SUM(CASE WHEN l.TP_OCUPACAO = 'L' THEN 1 ELSE 0 END) AS em_limpeza,
               SUM(CASE WHEN l.TP_OCUPACAO NOT IN ('O', 'I', 'V', 'L') THEN 1 ELSE 0 END) AS outros,
               ROUND(100 * SUM(CASE WHEN l.TP_OCUPACAO IN ('O', 'I') THEN 1 ELSE 0 END)
                 / NULLIF(COUNT(l.CD_LEITO), 0), 1) AS ocupacao_percentual
          FROM {schema}.UNID_INT u
          JOIN {schema}.LEITO l ON l.CD_UNID_INT = u.CD_UNID_INT
          LEFT JOIN {schema}.SETOR s ON s.CD_SETOR = u.CD_SETOR
         GROUP BY u.CD_UNID_INT, u.DS_UNID_INT, s.NM_SETOR
         ORDER BY u.DS_UNID_INT
    """
    return execute_query(sql)


def detalhar_unidade(cd_unid_int: int) -> list[dict]:
    """Detalha leito a leito de uma unidade de internação específica (status de ocupação)."""
    schema = get_schema()
    sql = f"""
        SELECT u.CD_UNID_INT          AS cd_unid_int,
               u.DS_UNID_INT          AS unidade_internacao,
               s.NM_SETOR             AS setor,
               l.CD_LEITO             AS cd_leito,
               l.DS_LEITO             AS leito,
               l.TP_OCUPACAO          AS status_ocupacao
          FROM {schema}.UNID_INT u
          JOIN {schema}.LEITO l ON l.CD_UNID_INT = u.CD_UNID_INT
          LEFT JOIN {schema}.SETOR s ON s.CD_SETOR = u.CD_SETOR
         WHERE u.CD_UNID_INT = :cd_unid_int
         ORDER BY l.DS_LEITO
    """
    return execute_query(sql, {"cd_unid_int": cd_unid_int}, max_rows=100)


# ---------------------------------------------------------------------------
# FATURAMENTO / FINANCEIRO
# ---------------------------------------------------------------------------

def faturamento_por_convenio(mes: int, ano: int) -> list[dict]:
    """Faturamento agrupado por convênio em determinado mês/ano."""
    schema = get_schema()
    sql = f"""
        SELECT c.DS_CONVENIO          AS convenio,
               COUNT(f.CD_FATURA)     AS qtd_faturas,
               SUM(f.VL_TOTAL)        AS valor_total,
               SUM(f.VL_PAGO)         AS valor_pago,
               SUM(f.VL_TOTAL - NVL(f.VL_PAGO, 0)) AS valor_pendente
          FROM {schema}.FATURA f
          JOIN {schema}.CONVENIO c ON c.CD_CONVENIO = f.CD_CONVENIO
         WHERE EXTRACT(MONTH FROM f.DT_EMISSAO) = :mes
           AND EXTRACT(YEAR  FROM f.DT_EMISSAO) = :ano
         GROUP BY c.CD_CONVENIO, c.DS_CONVENIO
         ORDER BY valor_total DESC
    """
    return execute_query(sql, {"mes": mes, "ano": ano})


def contas_a_receber(dias_vencimento: int = 30) -> list[dict]:
    """Lista contas a receber com vencimento nos próximos N dias."""
    schema = get_schema()
    sql = f"""
        SELECT c.DS_CONVENIO          AS convenio,
               f.NR_FATURA            AS nr_fatura,
               p.NM_PACIENTE          AS paciente,
               f.DT_EMISSAO           AS emissao,
               f.DT_VENCIMENTO        AS vencimento,
               f.VL_TOTAL             AS valor_total,
               f.VL_PAGO              AS valor_pago,
               f.VL_TOTAL - NVL(f.VL_PAGO, 0) AS saldo
          FROM {schema}.FATURA f
          JOIN {schema}.CONVENIO c ON c.CD_CONVENIO = f.CD_CONVENIO
          JOIN {schema}.PACIENTE p  ON p.CD_PACIENTE  = f.CD_PACIENTE
         WHERE f.DT_VENCIMENTO BETWEEN TRUNC(SYSDATE) AND TRUNC(SYSDATE) + :dias
           AND (f.VL_TOTAL - NVL(f.VL_PAGO, 0)) > 0
         ORDER BY f.DT_VENCIMENTO
    """
    return execute_query(sql, {"dias": dias_vencimento})


# ---------------------------------------------------------------------------
# AGENDA / AMBULATÓRIO
# ---------------------------------------------------------------------------

def agenda_do_dia(data_str: str = "", medico: str = "") -> list[dict]:
    """Consultas agendadas para uma data (formato DD/MM/YYYY) ou médico."""
    schema = get_schema()
    params = {}
    extra = ""

    if data_str:
        extra += " AND TRUNC(a.DT_AGENDA) = TO_DATE(:data, 'DD/MM/YYYY')"
        params["data"] = data_str
    else:
        extra += " AND TRUNC(a.DT_AGENDA) = TRUNC(SYSDATE)"

    if medico:
        extra += " AND UPPER(m.NM_PRESTADOR) LIKE UPPER(:medico)"
        params["medico"] = f"%{medico}%"

    sql = f"""
        SELECT a.DT_AGENDA             AS data_hora,
               p.NM_PACIENTE           AS paciente,
               m.NM_PRESTADOR          AS medico,
               esp.DS_ESPECIALIDADE    AS especialidade,
               a.DS_SITUACAO           AS situacao,
               c.DS_CONVENIO           AS convenio
          FROM {schema}.AGENDA a
          JOIN {schema}.PACIENTE p       ON p.CD_PACIENTE    = a.CD_PACIENTE
          JOIN {schema}.PRESTADOR m      ON m.CD_PRESTADOR   = a.CD_PRESTADOR
          LEFT JOIN {schema}.ESPECIALIDADE esp ON esp.CD_ESPECIALIDADE = a.CD_ESPECIALIDADE
          LEFT JOIN {schema}.CONVENIO c  ON c.CD_CONVENIO    = a.CD_CONVENIO
         WHERE 1=1 {extra}
         ORDER BY a.DT_AGENDA
    """
    return execute_query(sql, params, max_rows=200)


# ---------------------------------------------------------------------------
# CIRURGIAS / CENTRO CIRÚRGICO
# ---------------------------------------------------------------------------

def cirurgias_programadas(data_str: str = "") -> list[dict]:
    """Lista cirurgias programadas (padrão: próximos 7 dias)."""
    schema = get_schema()
    params = {}

    if data_str:
        data_filter = "TRUNC(c.DT_CIRURGIA) = TO_DATE(:data, 'DD/MM/YYYY')"
        params["data"] = data_str
    else:
        data_filter = "TRUNC(c.DT_CIRURGIA) BETWEEN TRUNC(SYSDATE) AND TRUNC(SYSDATE) + 7"

    sql = f"""
        SELECT c.DT_CIRURGIA           AS data_hora,
               p.NM_PACIENTE           AS paciente,
               c.DS_PROCEDIMENTO       AS procedimento,
               m.NM_PRESTADOR          AS cirurgiao,
               s.DS_SALA               AS sala,
               c.DS_SITUACAO           AS situacao,
               c.DS_ANESTESIA          AS anestesia
          FROM {schema}.CIRURGIA c
          JOIN {schema}.PACIENTE  p ON p.CD_PACIENTE  = c.CD_PACIENTE
          JOIN {schema}.PRESTADOR m ON m.CD_PRESTADOR = c.CD_CIRURGIAO
          LEFT JOIN {schema}.SALA  s ON s.CD_SALA      = c.CD_SALA
         WHERE {data_filter}
         ORDER BY c.DT_CIRURGIA
    """
    return execute_query(sql, params, max_rows=200)


# ---------------------------------------------------------------------------
# EXPLORAÇÃO DE SCHEMA (útil para perguntas ad-hoc)
# ---------------------------------------------------------------------------

def listar_tabelas(filtro: str = "") -> list[dict]:
    """Lista tabelas disponíveis no schema do Soul MV."""
    schema = get_schema()
    params = {"schema": schema}
    extra = ""
    if filtro:
        extra = " AND UPPER(t.TABLE_NAME) LIKE UPPER(:filtro)"
        params["filtro"] = f"%{filtro}%"

    sql = f"""
        SELECT t.TABLE_NAME   AS tabela,
               c.COMMENTS     AS descricao
          FROM ALL_TABLES t
          LEFT JOIN ALL_TAB_COMMENTS c
                 ON c.OWNER = t.OWNER AND c.TABLE_NAME = t.TABLE_NAME
         WHERE t.OWNER = :schema {extra}
         ORDER BY t.TABLE_NAME
    """
    return execute_query(sql, params, max_rows=300)


def descrever_tabela(nome_tabela: str) -> list[dict]:
    """Descreve colunas de uma tabela do Soul MV."""
    schema = get_schema()
    sql = """
        SELECT col.COLUMN_NAME  AS coluna,
               col.DATA_TYPE    AS tipo,
               col.NULLABLE     AS nulo,
               com.COMMENTS     AS descricao
          FROM ALL_TAB_COLUMNS col
          LEFT JOIN ALL_COL_COMMENTS com
                 ON com.OWNER       = col.OWNER
                AND com.TABLE_NAME  = col.TABLE_NAME
                AND com.COLUMN_NAME = col.COLUMN_NAME
         WHERE col.OWNER      = :schema
           AND col.TABLE_NAME = UPPER(:tabela)
         ORDER BY col.COLUMN_ID
    """
    return execute_query(sql, {"schema": schema, "tabela": nome_tabela})


def executar_sql_livre(sql: str) -> list[dict]:
    """
    Executa um SQL SELECT personalizado. APENAS leitura.
    Use para perguntas que nenhuma outra ferramenta atende.

    A checagem aqui é sintática (começa com SELECT), não substitui um usuário
    Oracle com permissão apenas de leitura — veja README.md.
    """
    sql_clean = sql.strip()
    if not sql_clean.upper().startswith("SELECT"):
        raise ValueError("Apenas queries SELECT são permitidas por segurança.")
    return execute_query(sql_clean, max_rows=200)
