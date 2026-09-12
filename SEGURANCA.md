# Segurança e uso responsável

As skills deste kit foram escritas para operar em **base de produção hospitalar**. Isso muda
o custo de errar: uma consulta pesada derruba a performance de quem está atendendo, e um
`UPDATE` mal calibrado afeta faturamento, prontuário ou contabilidade de gente real.

## Regras não negociáveis

1. **Somente leitura por padrão.** O MCP indicado no [MCP.md](MCP.md) aceita apenas `SELECT`.
   Trate isso como recurso, não como limitação.
2. **Escrita exige autorização explícita e nominal para o caso.** "Pode mexer" genérico não
   vale. Antes de qualquer DML: `SELECT` da linha de base, transação aberta, conferência do
   resultado e só então `COMMIT` — com `ROLLBACK` pronto.
3. **Confirme o ambiente pelo banco, não pelo apelido da conexão.**
   ```sql
   SELECT SYS_CONTEXT('USERENV','DB_NAME')   AS banco,
          SYS_CONTEXT('USERENV','SESSION_USER') AS usuario,
          SYS_CONTEXT('USERENV','HOST')      AS origem
     FROM DUAL;
   ```
4. **HML antes de PRD**, sempre que existir HML. Um piloto de um registro antes de qualquer
   carga em lote.
5. **Prefira a rotina nativa do MV** (tela, API, package). Efeito financeiro e contábil no MV
   costuma nascer em trigger; reproduzir no braço gera divergência silenciosa.

## LGPD

O MV guarda dado de saúde — a categoria mais sensível da LGPD.

- **Nunca** versione, cole em issue, mande por e-mail ou publique: nome de paciente, número
  de prontuário ou atendimento, CPF, data de nascimento, diagnóstico, matrícula de
  colaborador, IP de estação.
- Ao documentar um caso, descreva o **padrão**, não o indivíduo: "paciente marcado como VIP",
  não o nome. As skills deste repositório seguem essa regra.
- Consulta a prontuário é auditada. Se você está investigando *quem acessou*, saiba que o seu
  acesso também fica registrado — e isso é correto.

## O que este kit não faz

- Não traz credencial, host, string de conexão ou dump de dados.
- Não substitui o suporte oficial da MV para bug de produto.
- Não autoriza nada: quem responde pela alteração é quem executa e quem aprovou.

## Achou dado sensível aqui dentro?

Abra uma issue **sem repetir o dado** ("PII em `skills/x/SKILL.md`, linha N") ou fale direto
com o mantenedor. Corrigimos e reescrevemos o histórico se necessário.
