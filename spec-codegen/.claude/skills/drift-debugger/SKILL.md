---
name: drift-debugger
description: |
  Use quando `spec-codegen verify` falhar com "DRIFT DETECTED", quando
  o teste `test_examples_reproduce` quebrar, ou quando o usuário relatar
  que regenerou e o hash mudou. Cobre o playbook completo de diagnóstico:
  categorizar o drift, encontrar a causa, e decidir entre corrigir o
  template ou aceitar (e regenerar lockfile).
---

# drift-debugger

`verify` falhou. O Verifier disse que a regeneração não bate com o
lockfile. **Não regenere o lockfile cegamente** — isso esconde o
problema. Investigue primeiro.

## Decisão central

Drift sempre cai em uma de três categorias:

1. **Drift de produto** — alguém mudou template/spec e esqueceu de
   regerar o lockfile. Solução: regerar lockfile, commitar junto.
2. **Drift de ambiente** — o gerador produz output diferente em máquinas
   diferentes (Python version, Jinja version, encoding). Bug.
3. **Drift de bug no gerador** — alguma mudança em `src/spec_codegen/`
   afetou determinismo. Bug crítico.

A 1ª é "normal". A 2ª e a 3ª são bugs e precisam ser entendidas.

## Playbook

### Passo 1 — Ler o relatório

O Verifier classifica drifts em 3 baldes:

```
✗ DRIFT DETECTED

  Missing (N):         ← arquivos no lockfile, mas não gerados agora
    - tests/foo.py

  Unexpected (N):      ← arquivos gerados agora, mas não no lockfile
    + tests/bar.py

  Hash mismatch (N):   ← mesmo arquivo, conteúdo diferente
    ~ pom.xml
      expected 5d128fc3add8…  got 9a4f12b6c834…
```

Cada categoria aponta para tipos diferentes de causa:

| Categoria | Causa típica |
|---|---|
| `Missing` | Template/arquivo foi deletado de `files/` |
| `Unexpected` | Template/arquivo foi adicionado em `files/` |
| `Hash mismatch` | Template foi editado, ou spec mudou, ou contexto mudou |

### Passo 2 — Para `Hash mismatch`, ver o diff real

```bash
# Regenere em outro diretório e compare contra o esperado
cd examples/<exemplo>
spec-codegen generate \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --out /tmp/actual

# Reconstrua o "esperado" a partir de git
git checkout HEAD -- files/ spec.yaml
spec-codegen generate \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --out /tmp/expected
git checkout - -- files/ spec.yaml  # volta para o estado atual

diff -r /tmp/expected /tmp/actual
```

Agora você tem o diff exato. Categorize-o.

### Passo 3 — Diagnosticar

Para cada arquivo com hash mismatch, abra o diff e pergunte:

- **Mudou exatamente o que o usuário pediu?** → drift de produto.
  Regere lockfile, commit junto.
- **Mudou algo que não foi pedido?** → drift de bug. Continue.
- **Mudou whitespace/newline?** → checar template para falta de
  `{%- -%}` ou ausência de `keep_trailing_newline`.
- **Mudou `0` ↔ `0.0`?** → falta filtro `pynum` no template.
- **Mudou ordem de itens?** → algum dict/set não-ordenado no contexto.
  Quem produz a lista? Pydantic preserva ordem de YAML; Python `set`
  não.
- **Mudou caminho de arquivo?** → checar path templating; ver se
  variável existe no contexto.

### Passo 4 — Diagnóstico de ambiente

Se o drift acontece entre máquinas e não há mudança no repo:

```bash
# Compare versões
python --version
pip show jinja2 pydantic pyyaml spec-codegen

# Compare locale (encoding default pode mudar)
locale

# Compare ordem do walk (filesystem)
python -c "from pathlib import Path; \
  print(sorted(Path('examples/go-service/files').rglob('*')))"
```

Se a versão da Jinja diferir, é o suspeito #1 (whitespace handling
mudou em minor versions).

### Passo 5 — Diagnóstico de bug do gerador

Se você modificou `src/spec_codegen/`:

```bash
git diff HEAD src/spec_codegen/
```

Procure por:

- Remoção de `sorted(...)`
- Mudança em `keep_trailing_newline`, `StrictUndefined`, `autoescape`
- Mudança em `sort_keys` ou `ensure_ascii` no lockfile
- Adição de qualquer `set` ou `dict` não-ordenado no fluxo de dados
- Mudança no encoding (deveria ser sempre `"utf-8"`)

## Resolução

### Caso 1 — drift intencional (regerar lockfile)

```bash
cd examples/<exemplo>
spec-codegen generate \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --out /tmp/out \
  --write-lockfile --lockfile lockfile.json

# Verifique que o diff só toca o que foi pedido
git diff lockfile.json | head -20

# Commit junto com a mudança que causou o drift
git add files/ spec.yaml lockfile.json
git commit -m "feat: <descrição da mudança>"
```

### Caso 2 — drift de bug

Reverta a mudança que causou. Reabra com correção:

```bash
git restore src/spec_codegen/<arquivo>.py
# ou: git restore files/<arquivo>.tmpl
make verify-examples  # confirma baseline
# então re-aplique sua mudança com a correção
```

### Caso 3 — drift de ambiente

Pin a versão problemática em `pyproject.toml`:

```toml
dependencies = [
    "jinja2>=3.1,<3.2",   # pin estreito para garantir behavior
]
```

E adicione `jinja2==X.Y.Z` no `requirements-lock.txt` se houver.

## Antipadrões a recusar

- ❌ `--write-lockfile` sem entender o diff. Esconde drift de bug.
- ❌ "Vou só rodar de novo, deve ter sido transiente". O gerador é
  determinístico por construção — drift não é transiente.
- ❌ Editar `lockfile.json` à mão para fazer parar de quebrar. Crime.
- ❌ Aceitar drift "porque a maioria dos testes passa". Um drift
  silencioso vira dez em seis meses.

## Referências internas

- `src/spec_codegen/verify.py` — código do detector
- `docs/METHODOLOGY.md` §3 — armadilhas de byte-stability conhecidas
- `docs/DESIGN.md` — "Armadilhas conhecidas e suas soluções"
