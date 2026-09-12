# Contribuindo

O kit cresce por caso resolvido. Se você gastou meio dia descobrindo por que o MV se comporta
de um jeito, esse meio dia vira parágrafo aqui e ninguém mais paga por ele.

## Antes de abrir PR — a checagem que não pode falhar

Rode e confira que **não aparece nada**:

```bash
grep -rniE "([0-9]{1,3}\.){3}[0-9]{1,3}|password|senha *[:=]|[0-9]{3}\.[0-9]{3}\.[0-9]{3}-[0-9]{2}" skills/
grep -rnoE "\b[MF][0-9]{5}\b" skills/
```

**Nunca versione:** nome de paciente, número de prontuário ou atendimento, CPF, data de
nascimento, diagnóstico, matrícula de colaborador, IP de estação, host, usuário ou senha de
banco. Ver [SEGURANCA.md](SEGURANCA.md).

Ao documentar um caso real, descreva o **padrão**: "paciente marcado como VIP", não o nome.

## Anatomia de uma skill

```
skills/minha-skill/
├── SKILL.md                 # obrigatório
├── references/*.md          # opcional: material longo, carregado sob demanda
├── scripts/*.py             # opcional: validadores, geradores
└── agents/openai.yaml       # opcional: metadados para o Codex
```

O `SKILL.md` começa com frontmatter:

```markdown
---
name: minha-skill
description: O que resolve e QUANDO usar. O agente decide pela description — cite os termos que o usuário realmente digita (nome de tela, código de relatório, nome de tabela).
---
```

Uma `description` boa é a diferença entre a skill ativar sozinha e ficar encostada. Escreva-a
pensando em como o problema chega: *"relatório de produção por convênio com valor zerado"*,
não *"utilitário de faturamento"*.

## Estilo do conteúdo

- **Português direto.** Quem lê está com o problema na mão.
- **Diga o que é fato e o que é inferência.** "Nesta instalação só aparece `ACE`" é honesto;
  "o MV nunca gera `IMP`" não é.
- **SQL testado.** Se você não rodou, marque como não verificado.
- **Registre a pegadinha, não só o caminho feliz.** O valor está no "isso parece funcionar mas
  quebra quando…".
- **Nomeie as colunas.** `SELECT *` em tabela do MV traz 80 colunas e esconde o que importa.

## Fluxo

1. Fork, branch a partir da `main`.
2. Rode a checagem de PII acima.
3. Teste a instalação: `bash scripts/instalar.sh --agente claude` e verifique que a skill ativa.
4. PR descrevendo **o caso real** que motivou a mudança.

## Skill nova ou seção em skill existente?

Skill nova quando o assunto tem gatilho próprio e vocabulário próprio. Seção quando é mais um
detalhe de um fluxo já coberto. Na dúvida, seção — skill demais atrapalha a escolha do agente.
