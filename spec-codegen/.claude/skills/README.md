# Claude Code — skills do projeto

Estas skills são lidas pelo Claude Code quando o usuário trabalha no
`spec-codegen`. Cada uma é um briefing focado num tipo de tarefa.

O `CLAUDE.md` na raiz do projeto cita quais skills usar para cada
tipo de pedido — leia ele primeiro.

## Mapa rápido

| Skill | Para quê | Quando carregar |
|---|---|---|
| [`spec-author/`](./spec-author/SKILL.md) | Schema design (Pydantic + spec.yaml) | Editar `spec.yaml` ou `spec_schema.py` |
| [`template-author/`](./template-author/SKILL.md) | Templates Jinja, path templating, byte-stability | Editar `files/` em qualquer exemplo |
| [`example-builder/`](./example-builder/SKILL.md) | Adicionar gerador novo end-to-end | Criar `examples/<novo>/` |
| [`drift-debugger/`](./drift-debugger/SKILL.md) | `verify` falhou; investigar drift | `DRIFT DETECTED` ou teste de repro quebrado |
| [`lockfile-updater/`](./lockfile-updater/SKILL.md) | Atualizar lockfile após mudança intencional | Após editar template/spec com intenção |

## Como usar

No Claude Code, mencione o que você quer fazer naturalmente — o
agente decide qual skill puxar. Se quiser forçar uma, peça
explicitamente:

> "Use a skill `example-builder` para adicionar um exemplo de Rust."

## Como evoluir as skills

Cada skill é um arquivo `SKILL.md` com:

- **Front matter** YAML: `name`, `description`
- **Corpo** Markdown: checklists, antipadrões, workflow, referências

Mantenha-as curtas (≤300 linhas). Skills longas viram noise — quebre
em duas se passar disso.
