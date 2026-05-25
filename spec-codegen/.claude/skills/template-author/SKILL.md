---
name: template-author
description: |
  Use quando o usuário pedir para criar/editar arquivos em
  examples/*/files/ — templates Jinja (.tmpl), arquivos literais,
  ou estrutura de diretórios. Cobre as armadilhas de byte-stability
  (whitespace control, pynum filter), a regra .tmpl vs .j2, e
  path templating. Acione antes de qualquer mudança em files/.
---

# template-author

Você está editando arquivos sob `examples/*/files/`. Tudo aqui termina
em bytes do projeto gerado, então a regra é simples: **byte-stable ou
não vai**.

## Convenções de extensão (NÃO INVENTE OUTRAS)

| Extensão | Significado | O gerador faz |
|---|---|---|
| `.tmpl` | Template Jinja DO GERADOR | Renderiza, escreve sem o `.tmpl` |
| `.j2`   | Template Jinja DO RUNTIME da app | Copia bytes verbatim |
| outras  | Arquivo literal | Copia bytes verbatim |
| `.keep` | Marcador de diretório vazio | Cria dir, não escreve arquivo |

**A confusão mais comum:** ver um `.j2` num exemplo e querer
substituir por `.tmpl` "pra ficar consistente". Não. O `deploy-agent`
usa Jinja em runtime para renderizar Kubernetes manifests; aqueles
`.j2` PRECISAM chegar intactos no output.

## Path templating

`{{ var }}` em nomes de pastas e arquivos é renderizado:

```
files/src/main/java/{{project.package_path}}/{{project.main_class}}.java.tmpl
                                                                   ↓
output/src/main/java/com/example/healthapi/HealthApiApplication.java
```

**Limites:**

- Use `{{ namespace.field }}` simples, sem espaços extras
- Não funciona com `{% if %}`, `{% for %}`, filtros, etc.
- Se precisar de lógica, faça via `@computed_field` no schema

## Byte-stability — armadilhas conhecidas

Cada item abaixo já causou drift em algum momento da história do repo.
Trate como leis físicas.

### 1. Whitespace control no Jinja

`{% endif %}` deixa newline. `{%- endif %}` não. **Sempre prefira a
versão `{%- -%}` quando o trailing newline importa.**

```jinja
{% if cond %}
  texto
{%- endif %}        ← sem newline extra
```

### 2. Floats que parecem ints

Pydantic serializa `temperature: 0` (no YAML) como `0.0` (float). Se
o template tem `temperature={{ model.temperature }}`, vai sair
`temperature=0.0` — diferente do código original com `temperature=0`.

**Solução:** use o filtro `pynum`:

```jinja
temperature={{ model.temperature | pynum }}
```

`pynum` rende `0` para floats inteiros e `0.5` para fracionários.

### 3. Acessar variáveis nested vs flat

A biblioteca dá contexto **nested** por padrão (`{{ project.name }}`,
não `{{ name }}`). Se um exemplo precisa de aliases flat para
conveniência, eles aparecem no `_build_context` — mas dentro da
biblioteca padrão, sempre nested.

### 4. Diretórios vazios

`rglob` não enxerga diretório vazio. Se você precisa de
`tests/fixtures/` vazio no output (porque o framework de testes
espera), ponha um arquivo `.keep` lá:

```
files/tests/fixtures/.keep
```

O `.keep` cria o diretório no output e some.

### 5. Strings que parecem comandos shell

Templates que escrevem comandos shell precisam escapar strings com
caracteres especiais. Use o filtro `shellesc`:

```jinja
RUN echo {{ project.name | shellesc }} > /etc/app.name
```

## Workflow para mudança em template

1. **Antes de editar:** rode `make verify-examples` para garantir baseline limpo
2. Edite o `.tmpl` (ou crie novo arquivo)
3. Renderize manualmente pra olhar o output:
   ```bash
   cd examples/go-service && spec-codegen generate \
     --spec spec.yaml --schema spec_schema.py:ProjectSpec \
     --files files --out /tmp/preview
   ```
4. Inspecione `/tmp/preview/` — está como você esperava?
5. Atualize o lockfile:
   ```bash
   spec-codegen generate --spec ... --files ... --out /tmp/preview \
                          --write-lockfile --lockfile lockfile.json
   ```
6. Confirme: `spec-codegen verify ...` → `✓`
7. Rode `make check` antes de commitar

## Antipadrões a recusar

- ❌ Editar diretamente um arquivo no output (`/tmp/preview/...`) em vez
  do template em `files/`. O output é descartável; só o template
  importa.
- ❌ "Melhorar" um template adicionando lógica/condicional que o
  usuário não pediu. Drift invisível.
- ❌ Hardcodar valor que deveria vir do spec. Se você se pegou
  digitando "8080" em vez de `{{ server.port }}`, pare.
- ❌ Adicionar template novo sem rodar `--write-lockfile` no mesmo
  commit. CI quebra.

## Referências internas

- `docs/METHODOLOGY.md` §2 — "Template é o contrato"
- `docs/METHODOLOGY.md` §3 — "Render é função pura"
- `docs/DESIGN.md` — "Por que `.tmpl` e não `.j2`"
- `src/spec_codegen/filters.py` — filtros disponíveis (`pynum`, `shellesc`)
