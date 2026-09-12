# Acesso ao PEP (MVPEP) — "Você não tem acesso a página"

Caso validado (identificação da prestadora e do atendimento omitidas). Sintoma clássico:
profissional **com os perfis certos** abre o prontuário e recebe **"Você não tem acesso a
página"** — some vez em um tipo de atendimento (ex.: urgência) mas funciona em outro (ex.:
ambulatório).

## A tabela que decide: `PERFIL_AMBULATORIAL`

É a camada que define **qual perfil o PEP entrega quando o prontuário é aberto**. Tela:
**`M_CONFIG_PERFIL_USUARIO`** ("Perfil do Usuário (Std)", aba **Área de Prontuário**).
O PEP escolhe um perfil cujos **filtros batem com o contexto do atendimento aberto**. Se
**nenhum perfil ativo casa** → "Você não tem acesso a página". Colunas de filtro do perfil:

| Coluna | Casa com… |
|---|---|
| `TP_ATENDIMENTO` | tipo do atendimento: `I`/`U`/`A`/`E` (nulo = qualquer) |
| `CD_TIP_PRESTA` | **tipo de prestador** do profissional (`PRESTADOR.CD_TIP_PRESTA`) |
| **`CD_ESPECIALIDADE`** | **a especialidade DO ATENDIMENTO** (`ATENDIME.CD_ESPECIALID`), **não** a do prestador |
| `CD_SETOR` | setor do atendimento (nulo = qualquer) |
| `CD_MULTI_EMPRESA` | empresa (nulo = qualquer) |
| `TP_PORTA_ENTRADA` | de onde entrou: `LISTA_PACIENTES`, `LISTA_TODOS_PACIENTES`, `PARECER_MEDICO`, `LOGIN`, `PW_AGE_*`… |
| `TP_ALTA` | `ALTA`/`ALTA_MEDICA`/`ALTA_HOSPITALAR`/`SEM_ALTA` (nulo = qualquer) |
| `SN_ATIVO` | só perfis `S` são considerados |

## As duas armadilhas que geram o bloqueio

1. **`CD_ESPECIALIDADE` do perfil compara com a especialidade do ATENDIMENTO, não a do prestador.**
   A especialidade do profissional tem coluna própria (`CD_ESPECIALIDADE_MEDICA`). Confirmado ao
   vivo: a profissional do caso tinha uma especialidade X **como Principal** e mesmo assim travava
   — porque o atendimento de urgência entrou com uma especialidade Y diferente, e o único perfil de
   urgência do tipo dela filtrava pela especialidade X. Nenhum perfil casou.
2. **`CD_TIP_PRESTA` separa "médico" de subtipos.** Um tipo de prestador especializado (no caso,
   um subtipo de oncologista) é diferente do tipo "médico" genérico usado pelos perfis padrão de
   urgência — o perfil genérico exige o tipo genérico e não casa com o subtipo. Sempre confira o
   `CD_TIP_PRESTA` real do prestador antes de assumir "é médico".

## Correção aplicada (a que resolveu)

Na tela `M_CONFIG_PERFIL_USUARIO`, no perfil de urgência do tipo do prestador,
**apagar o valor do campo Especialidade** (deixar `CD_ESPECIALIDADE` nulo) → salvar → o
profissional **sai e entra** (cache de sessão do PEP). Passa a casar com urgência de qualquer
especialidade. Validação (somente leitura):
```sql
SELECT cd_perfil_ambulatorial, ds_perfil_ambulatorial, sn_ativo, tp_atendimento,
       cd_tip_presta, cd_especialidade, tp_porta_entrada, cd_multi_empresa
FROM dbamv.perfil_ambulatorial WHERE cd_perfil_ambulatorial = <perfil>;
-- cd_especialidade deve ficar NULL
```
**Alcance é global**: o filtro vale para **todos** os prestadores daquele `CD_TIP_PRESTA`, não só
para o usuário do chamado. Antes de alterar, conte quantos prestadores caem no tipo — se forem
poucos, o impacto é controlado.

## Metodologia de diagnóstico (o que separou causa de coincidência)

- **Compare o usuário-problema com vários que acessam OK.** Foi assim que se descartou, um a um:
  cadastro do prestador (tipo/situação/atuante idênticos), papel e módulos autorizados iguais.
  Sobrou a única diferença real: o `CD_TIP_PRESTA` do prestador e, por consequência, o perfil
  ambulatorial que casa.
- **Prove regressão com dados históricos.** Cruzar documentos clínicos × atendimentos por
  tipo/especialidade pode mostrar quando um filtro de especialidade foi introduzido e quebrou um
  fluxo que antes funcionava com várias especialidades. Vira o melhor argumento: **é reversão de
  restrição, não liberação nova.**
```sql
SELECT pr.cd_tip_presta, a.tp_atendimento, a.cd_especialid, COUNT(*) qtd,
       TO_CHAR(MAX(d.dh_criacao),'dd/mm/yyyy') ultimo
FROM dbamv.pw_documento_clinico d
JOIN dbamv.atendime a  ON a.cd_atendimento = d.cd_atendimento
JOIN dbamv.prestador pr ON pr.cd_prestador = d.cd_prestador
WHERE pr.cd_tip_presta = <tipo> AND a.tp_atendimento = 'U'
GROUP BY pr.cd_tip_presta, a.tp_atendimento, a.cd_especialid ORDER BY qtd DESC;
```

## O que NÃO resolve (becos verificados)

- **Descriptografar / "descobrir" a senha** do profissional: recusar. Não é o problema (a senha
  está certa) e quebra a rastreabilidade individual do prontuário. A função de checagem de senha do
  MV é **verificadora de tentativa** (compara um palpite), não extratora; usar como "descobrir
  senha" vira força bruta. Senha esquecida → **reset** pela admin de usuários.
- **Clonar papéis/módulos de um usuário-modelo**: é outra camada, não mexe no perfil do PEP.
  E cuidado com **login com/sem zero à esquerda** — um `NOT IN` comparando strings com formato
  diferente (`M123` vs `M00123`) pode não achar nenhuma linha e "dar sucesso" sem fazer nada;
  sempre confirme o formato exato do login antes de montar a comparação.
- Aba **Especialidades do cadastro de Prestador** (marcar "Principal"): não afeta o filtro do
  perfil (que olha a especialidade do atendimento). Não mexer — altera agenda/faturamento/laudos.

## Clonar perfil (opção A, quando NÃO se quer alcance global)

Se a política exigir manter granularidade (ex.: um perfil por especialidade em vez de campo nulo),
**use o botão "Copiar Perfil" da própria tela** — clona com a hierarquia certa. Clonar por SQL
é arriscado: os módulos ficam em tabelas próprias com hierarquia por PK/PAI. Um `INSERT..SELECT`
só funciona com **offset fixo aplicado em PK e em PAI** (para a hierarquia se preservar) e ajuste
da sequence; caso contrário o perfil novo aponta para os módulos do original e abre com abas
erradas/faltando.
