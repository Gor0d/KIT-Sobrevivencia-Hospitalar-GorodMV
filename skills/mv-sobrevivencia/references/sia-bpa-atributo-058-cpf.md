# SIA/BPA — Atributo 058 e conciliação de CPF

Use este procedimento quando a crítica do SIA/DATASUS rejeitar produção ambulatorial
porque `DBAMV.PACIENTE.NR_CPF` está vazio (relatório de consistência SIA, mensagem tipo
"PROCEDIMENTO COM ATRIBUTO 058 EXIGE CPF OBRIGATÓRIO"). Bloqueia BPA-I e APAC inteiros de
pacientes sem CPF cadastrado. CPF é dado pessoal e identificador de saúde: preserve
rastreabilidade, minimização, controle de acesso e retenção conforme a política LGPD da
instituição.

## Onde nasce e por que não dá pra "só preencher"

`EVE_SIASUS` (o evento que vira BPA/APAC) **não tem coluna própria de CPF** — ele herda de
`PACIENTE.NR_CPF` na geração. Corrigir é sempre **UPDATE em `PACIENTE`**, nunca no evento.

## Invariantes (regra inegociável)

- **Nunca inventar, estimar, completar ou escolher CPF por plausibilidade.** Todo valor gravado
  tem que vir de **fonte oficial** (CADSUS/CNS ou SISREG, consultado pelo CNS do próprio
  paciente) e passar por:
  1. **validação de dígito verificador (módulo 11)** antes de considerar o valor;
  2. **confirmação de identidade** (nome + data de nascimento + CNS baterem) antes de gravar — um
     CPF "quase certo" sem identidade confirmada fica **pendente**, não é forçado.
- Aceitar CPF somente com 11 dígitos e ambos os verificadores módulo 11 válidos; rejeitar
  sequências repetidas.
- CNS exato confirmado pela fonte oficial dá confiança `ALTA`.
- Nome + nascimento + nome da mãe, todos exatos após normalização, dá confiança `MEDIA`.
- Mais de um candidato é `NAO_CONFIRMADO`; nunca escolher automaticamente.
- Candidato com CPF inválido é descartado e registrado como `INVALIDO` se nenhum válido for
  confirmado em fonte posterior.
- Recém-nascido é tratado separadamente. CPF/CNS da mãe ficam em campos próprios e nunca são
  carregados automaticamente no cadastro do RN.

## Levantamento do universo (MCP, somente leitura)

```sql
SELECT
  COUNT(DISTINCT p.cd_paciente) qt_pacientes,
  COUNT(*) qt_linhas
FROM dbamv.eve_siasus e
JOIN dbamv.paciente p ON p.cd_paciente = e.cd_paciente
WHERE e.cd_multi_empresa = <empresa>
  AND TRUNC(e.dt_eve_siasus,'MM') = TO_DATE('01/<mm>/<aaaa>','dd/mm/yyyy')
  AND (p.nr_cpf IS NULL OR TRIM(p.nr_cpf) = '');
```
Sempre **quebre por grupo ADULTO × RN** (`UPPER(nm_paciente) LIKE 'RN %' OR LIKE 'RN DE%'`) e por
**tem/não tem CNS** — muda completamente a estratégia de resolução (ver abaixo) e evita que o RN
(que pode ser uma fração relevante do universo) fique escondido dentro do número de "adultos".

## Fluxo reutilizável

1. Preserve a crítica original e registre competência, estabelecimento/CNES, ambiente e
   quantidade de pacientes/linhas BPA rejeitadas.
2. Extraia uma worklist mínima, sem copiá-la para Git ou local compartilhado, contendo:
   `CD_PACIENTE`, nome, nascimento, sexo, mãe, CNS, quantidade de linhas BPA e grupo
   `RN|ADULTO`.
3. Confirme por consultas somente leitura que `NR_CPF` está vazio e que o CPF não existe em
   outra fonte interna autorizada. Não procure CPF em bases não autorizadas.
4. Priorize as fontes nesta ordem:
   - CADSUS oficial por CNS;
   - CADSUS por nome + nascimento + mãe;
   - exportação institucional autorizada do SISREG/e-SUS, usando as mesmas chaves estritas.
5. Comece com um único paciente com CNS em **HML**. Só processe o lote após validar requisição,
   resposta, OIDs, mapeamento dos identificadores e trilha de auditoria.
6. Gere três artefatos locais protegidos:
   - de-para `CD_PACIENTE -> CPF`, com status, origem, chave, confiança e observação;
   - SQL idempotente, somente para `OK`;
   - resumo por grupo/status, incluindo quantidade de pacientes e linhas BPA.
7. Revise o SQL linha a linha, valide novamente todos os CPFs e execute primeiro em HML.
8. Após carga piloto, confira cadastro no MV, regenere/recritique o BPA e verifique se o
   Atributo 058 desapareceu sem criar novas críticas.
9. Promova para PRD somente após homologação formal. Registre linha de base, operador, horário,
   resultado e decisão de `COMMIT`/`ROLLBACK`.

## Recém-nascido (RN): a maioria resolve pela identidade PRÓPRIA, não da mãe

Achado importante de um caso real: **a maior parte dos RN já tem CPF próprio** (emitido
automaticamente no registro civil via integração SINASC/DNV) e **CNS próprio** já no cadastro do
MV — bastou consultar o SISREG pelo **CNS do próprio bebê** (mesmo fluxo do adulto) para resolver
a maioria dos RN do caso. Só o resíduo (RN cujo próprio CNS não retornou CPF) precisa da via do
**CPF/CNS do responsável (mãe)** — que é a regra correta do SIA para faturar neonato: o `UPDATE`
grava o **CPF da mãe no `NR_CPF` do próprio `cd_paciente` do RN** (é assim que o SIA exige, não é
erro de dado).

**A via da mãe é a mais frágil e a que menos rende** — trate como último recurso, não primeira
tentativa:
- Cruzar `NM_MAE` do RN contra `PACIENTE` (mãe como paciente própria) por igualdade exata
  recupera pouco (nome com acento/abreviação diverge). Ampliar para `NLSSORT(...,
  'NLS_SORT=BINARY_AI')` (ignora acento) ajuda pouco sozinho — a maioria das mães **não existe
  como paciente** no MV.
- **Fuzzy matching por similaridade de texto é perigoso para nome de pessoa.** Um score alto
  (ex.: 0,89) pode vir de um par com mesmo sobrenome mas nome do meio **diferente** —
  provavelmente pessoas diferentes. **Nunca aceite fuzzy-match para CPF sem uma confirmação
  independente e ao vivo na fonte** (o SISREG devolvendo o **mesmo nome exato** para aquele CNS é
  essa confirmação); um match "só forte o bastante" não basta para gravar em cadastro.
- Mesmo com o CNS "achado" via fuzzy-match, a consulta ao vivo no SISREG pode devolver um **CNS
  divergente** do pesquisado — nesse caso a trava de segurança do script **tem que recusar**
  (`STATUS=NAO_CONFIRMADO`), mesmo que um CPF apareça na tela. Num caso real, **3 candidatos de
  mãe foram tentados e os 3 vieram divergentes** — ficaram pendentes, corretamente, em vez de
  forçados.
- Homônimo (2+ pacientes com o mesmo nome exato) = **nunca escolher sozinho**; marcar `AMBIGUO` e
  deixar para conferência humana.

## CADSUS PDQ / ITI-47

- O WSDL, endpoint, OIDs, identificadores de remetente/destinatário, certificado e segredo são
  sempre parametrizáveis; nunca os grave no código ou repositório.
- Priorize certificado A1 (`.pfx`/`.p12`) por TLS mútuo. A3 exige adaptador PKCS#11 ou gateway
  mTLS institucional homologado; nunca grave PIN em arquivo ou argumento.
- Use `PRPA_IN201305UV02` (PDQ_Q22) e interprete `PRPA_IN201306UV02`, validando os identificadores
  pelas raízes OID fornecidas no manual vigente.
- A presença de certificado não prova credenciamento do CNPJ no barramento.
- Confirme no manual/HML se o serviço exige WS-Addressing (`To`, `Action`, `MessageID`) e/ou
  assinatura WS-Security X.509 além de TLS mútuo. Não presuma que mTLS basta.
- Aplique throttling, timeout, retry somente para falhas transitórias e backoff exponencial.
  Registre `correlationId`, resultado técnico e fonte, sem escrever nome, CNS ou CPF no log.
- SOAP Fault de autenticação, assinatura, endereçamento, contrato ou schema não deve ser
  mascarado como paciente não encontrado. Interrompa o piloto e ajuste a integração em HML.

## SISREG — quando é o caminho que efetivamente resolve

Quando CADSUS/PDQ ainda não está operacional na instituição (falta certificado/credenciamento), o
SISREG (`sisregiii.saude.gov.br`) pode ser o caminho que resolve na prática, via automação de
navegador (ex.: Playwright) com **login manual do operador a cada execução** — a ferramenta nunca
deve guardar usuário/senha; o script deve recusar rodar sem digitação interativa. Busca por
**CNS** é a chave forte; busca por **nome** exige também nome da mãe **ou** CPF/CNS (regra do
próprio portal) — então busca só-por-nome não serve para achar a mãe como paciente (precisaria do
nome da avó, que não se tem).

Armadilhas técnicas de automação de navegador para esse fluxo:
- **Precisa rodar em sessão interativa de verdade** (terminal onde o usuário digita usuário/senha
  ao vivo) — um agente com shell **não-interativo** (stdin fechado) não consegue responder a
  `input()`/`getpass()`; nem tentar.
- **Perfil do navegador pode ficar travado** (erro de sessão já existente) se um processo anterior
  morreu sem fechar o navegador — sintoma de processos órfãos apontando pro mesmo
  `--user-data-dir`. Fix: matar a árvore de processos daquele perfil antes de rodar de novo; **não**
  é necessário apagar o perfil inteiro.

## SQL seguro

Formato esperado para cada adulto confirmado:

```sql
UPDATE dbamv.paciente SET nr_cpf='<11 digitos>'
WHERE cd_paciente=<codigo> AND (nr_cpf IS NULL OR TRIM(nr_cpf)='');
```

- Emita `UPDATE` apenas para `OK`.
- Comente integralmente todas as linhas RN para revisão humana.
- Termine com `-- COMMIT;`, nunca com commit automático.
- Antes da escrita, capture a linha de base por `SELECT` e valide que o alvo continua vazio.
- A escrita não passa pelo MCP somente leitura; o usuário autorizado executa no DBeaver ou pelo
  fluxo institucional aprovado.

## Resultado de um caso real (ordem de grandeza, para calibrar expectativa)

| | Antes | Depois |
|---|---|---|
| Pacientes sem CPF | centenas | dezenas |
| Linhas de BPA bloqueadas | milhares | uma fração pequena |

A maioria dos CPFs gravados veio do caminho adulto direto e do RN via CNS próprio, 100%
confirmados por identidade em fonte oficial, 0 inválidos no dígito verificador, 0 duplicados. O
resíduo (não localizado + não confirmado, incluindo RN via mãe não confirmada) é pendência
genuína — caminho daqui pra frente é contato direto com paciente/família no próximo atendimento,
não mais automação (a fonte oficial já foi consultada e não confirmou identidade suficiente).

## Armadilhas técnicas gerais (reaproveitar da próxima vez)

- **MCP (`soul-mv-erp`) continua com as mesmas travas de sempre**: sem CTE/`WITH`, sem
  `LISTAGG(DISTINCT ...)` (`ORA-30482` — Oracle 12.1 SE não suporta), ~500 linhas por consulta.
  Ao montar a worklist de uma tabela nova (ex.: APAC), rode `descrever_tabela` antes de assumir
  nome de coluna (`cd_procedimento` não existe em toda tabela de procedimento — confira sempre).

## Se você mantém uma ferramenta própria de resolução de CPF/CNS

Reaproveite código e testes já validados (validação de dígito verificador, pipeline de decisão,
gerador SQL) em vez de reescrever do zero a cada caso. Antes de uma execução real, confira a
mensagem SOAP contra o manual/WSDL vigente e faça o piloto em HML.
