# Cadastro estrutural — Origem de atendimento → Setor/CC → Unidade de Internação → Leitos

Padrão para criar/segregar uma área assistencial nova (ex.: um convênio/contrato novo que
precisa de **centro de custo, censo e leitos próprios**). Validado num caso real: setor e unidade
de internação novos criados numa empresa existente, com um lote de leitos e as origens de
atendimento repontadas para eles.

## A cadeia (de cima pra baixo)

| Nível | Tabela | Liga em | Papel |
|---|---|---|---|
| Origem de atendimento | **`ORI_ATE`** | `CD_SETOR` → SETOR | de onde o paciente entra; carrega o setor pro atendimento |
| Centro de custo = Setor | **`SETOR`** | `CD_CEN_CUS` (código contábil) | `SN_CENTRO_DE_CUSTO='S'` = É um CC. `CD_MULTI_EMPRESA` NOT NULL (1 setor = 1 empresa) |
| Unidade de internação | **`UNID_INT`** | `CD_SETOR` → SETOR | agrupa leitos; `TP_UNID_INT` ('I'=internação, 'U'=urgência); `SN_SEMI_UTI` p/ diária semi-intensiva SUS |
| Leito | **`LEITO`** | `CD_UNID_INT` → UNID_INT | `CD_TIP_ACOM` (3=ENFERMARIA, 1=APART, 8=UTI…); `TP_OCUPACAO` ('V'=vago); `TP_SITUACAO` ('A'=ativo) |

**"Atrelar a origem ao setor/CC" = `UPDATE ORI_ATE SET CD_SETOR=<novo>`** — muitas vezes as
origens já existem apontando pro setor genérico (ex.: um setor guarda-chuva de convênio/SUS).

## Técnica: clonar um molde que já funciona (não montar do zero)

`SETOR` tem dezenas de colunas (muitos `SN_*` NOT NULL de config) e `UNID_INT`/`LEITO` idem. **Não
enumere valores no chute** — faça `INSERT ... SELECT` de um registro-molde equivalente,
sobrescrevendo só o essencial. No caso real:
- Setor: um setor guarda-chuva de convênio/SUS já existente como molde (`tp_setor='P'`,
  `tp_grupo_setor='A'`, `sn_centro_de_custo='S'`). Sobrescrever: `cd_setor` novo, `nm_setor`,
  `cd_cen_cus` novo, `cd_setor_custo`=ele mesmo, `cd_setor_integra`=NULL (de-para contábil),
  `dt_inclusao`=SYSDATE.
- Unidade: uma ala real de internação já existente, do mesmo `tp_unid_int='I'`, como molde.
- Leitos: gerar N via `CONNECT BY LEVEL <= N`, `cd_leito = (SELECT MAX(cd_leito) FROM leito)+LEVEL`.

Sequenciais: pegar `MAX(cd_setor)`/`MAX(cd_unid_int)`/`MAX(cd_leito)`/`MAX(cd_ori_ate)` antes
(não há sequence exposta confiável; base viva, reconferir na hora).

## Armadilhas confirmadas

- **`CD_CEN_CUS` NÃO é único** — pode repetir entre empresas (setores em pares espelhados entre
  empresas, com um offset fixo entre os códigos). Antes de "usar o próximo código", cheque
  `SELECT ... FROM setor WHERE cd_cen_cus='<código>'` — um código que parece livre pode já
  pertencer a outro setor (ex.: uma capela, um ambulatório) escondido na mesma faixa. Descubra o
  próximo código realmente livre da faixa, não assuma sequencial.
- **Espelho entre empresas**: se o rateio contábil exigir, criar o setor análogo na empresa
  espelhada também. Muitas vezes só a empresa principal já basta (decidir com a Controladoria).
- **`sn_extra` do leito**: `'S'` = leito EXTRA (overflow), não é "leito adicional". Enfermaria
  normal de N leitos = `sn_extra='N'`.
- **Escrita estrutural em PRD**: setor/unidade idealmente pela **TELA** (Cadastro de Setor /
  Cadastro de Unidade) — o MV monta config dependente (grupo de faturamento, censo, mapa de
  leitos). Se fizer por SQL (clone), **abra as telas depois** e confirme que aparecem/salvam, e
  cheque o **Mapa de Leitos** da unidade. Leitos (repetitivo) e o `UPDATE` das origens são OK por SQL.
- **Não confundir com o roteamento multiempresa de faturamento.** Criar setor/unidade/leito
  numa empresa resolve **censo/custo**, NÃO faz a AIH sair no CNES de outra empresa. Cross-empresa
  de internação (LEITO→UNID_INT→SETOR travado por `CD_MULTI_EMPRESA` nas rotinas de internação) é
  caso de suporte MV.
