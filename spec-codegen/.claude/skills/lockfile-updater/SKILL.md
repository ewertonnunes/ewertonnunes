---
name: lockfile-updater
description: |
  Use quando o usuário fez uma mudança intencional em spec.yaml ou
  files/ e precisa atualizar o lockfile.json correspondente. Garante
  que (a) o diff do lockfile só contém o esperado, (b) lockfile e
  source são commitados juntos, (c) verify passa antes do commit.
---

# lockfile-updater

O usuário fez mudança em `spec.yaml` ou `files/` e quer atualizar o
lockfile. **Esta skill existe para garantir que a atualização seja
revisável e correta** — não é só rodar `--write-lockfile` e seguir.

## Pré-condição: confirme que a mudança é intencional

Antes de regerar, **olhe** o que mudou:

```bash
git diff examples/<exemplo>/spec.yaml examples/<exemplo>/files/
```

A pergunta a fazer: "as únicas coisas que mudaram são as que o
usuário pediu?". Se sim, prossiga. Se não, isso é drift acidental —
acione `drift-debugger`, não esta skill.

## Workflow canônico

### 1. Snapshot do baseline

```bash
cd examples/<exemplo>

# Regenere com o lockfile ATUAL como referência
git stash      # se houver mudanças não committed
spec-codegen generate \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --out /tmp/before
git stash pop  # restaura as mudanças
```

### 2. Regenerar com lockfile

```bash
spec-codegen generate \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --out /tmp/after \
  --write-lockfile --lockfile lockfile.json
```

### 3. Inspeção do diff (CRÍTICO)

```bash
# Diff do output gerado
diff -r /tmp/before /tmp/after

# Diff do lockfile committed
git diff lockfile.json
```

Para cada linha do diff do lockfile, confirme que a mudança é
explicável pela edição que o usuário fez. Se aparecer hash de
arquivo que o usuário não tocou, **pare** — isso é sinal de
contexto compartilhado mudando (variável global, computed_field,
etc.) e merece investigação.

### 4. Verify para confirmar

```bash
spec-codegen verify \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --lockfile lockfile.json
# → ✓ N files reproduced byte-for-byte
```

Se falhar aqui, alguma coisa está muito errada — provavelmente o
gerador tem não-determinismo. Acione `drift-debugger`.

### 5. Testes completos

```bash
make check
```

Isso roda lint + types + os 30 testes incluindo o do lockfile.

### 6. Commit atômico

```bash
git add examples/<exemplo>/spec.yaml \
        examples/<exemplo>/files/ \
        examples/<exemplo>/lockfile.json
git commit -m "feat(<exemplo>): <descrição da mudança>

Updates lockfile (N files affected: ...)
"
```

**Regra de ouro: source change + lockfile change SEMPRE no mesmo
commit.** Nunca em commits separados. Caso contrário a história fica
"git bisectável" mas estados intermediários não passam no `verify` —
pesadelo pra debugging.

## Mensagem de commit que ajuda

Quando o lockfile muda, deixe explícito quais arquivos foram
afetados — facilita revisão:

```
feat(go-service): bump go 1.26.3 → 1.26.4

Updates lockfile.json (3 files affected):
  ~ go.mod          (toolchain go1.26.3 → go1.26.4)
  ~ Dockerfile      (golang:1.26.3-alpine → golang:1.26.4-alpine)
  ~ README.md       (string da versão atualizada)
```

Quem revisa o PR consegue verificar em segundos que o diff bate.

## Quando o diff do lockfile surpreende

Se o lockfile mudou em mais arquivos do que você esperava:

- **Mudou em arquivo que importa de outro:** algum template usa um
  `computed_field` que mudou. Ex: editar `project.module` no Go cascateia
  pra todos os `.tmpl` que importam pacote.
- **Mudou em arquivo que tem o nome no path:** se a variável é parte do
  path (e.g. `{{project.package_path}}`), mudar a variável renomeia
  o arquivo — aparece como `Missing` + `Unexpected` no diff.
- **Mudou em campo que parecia decorativo:** título do README, descrição.
  Tudo o que aparece em string nos templates conta como produto.

Nenhum desses é bug, mas todos merecem aparecer na mensagem de commit
para a revisão ser rápida.

## Quando NÃO atualizar o lockfile

- Se a mudança foi acidental (você não pretendia mudar nada).
  → reverta antes.
- Se você não entende por que o hash mudou.
  → acione `drift-debugger` primeiro.
- Se o CI está vermelho por outro motivo (lint, types, testes).
  → arrume antes; lockfile correto + outras coisas quebradas é pior
    que tudo quebrado.

## Antipadrões a recusar

- ❌ `git add lockfile.json; git commit -m "fix lockfile"` em commit
  separado da mudança que causou. Quebra `git bisect`.
- ❌ Editar `lockfile.json` à mão para corrigir hash. Lockfile é gerado.
- ❌ Atualizar lockfile sem rodar `make check`. CI vai pegar; melhor
  pegar localmente.
- ❌ Atualizar lockfile de um exemplo quando a mudança foi noutro.
  Lockfiles são por-exemplo.

## Referências internas

- `src/spec_codegen/lockfile.py` — formato e regras de byte-stability
- `src/spec_codegen/cli.py` — flags `--write-lockfile`, `--lockfile`
- `docs/METHODOLOGY.md` §4 — "Lockfile é a prova de reprodutibilidade"
