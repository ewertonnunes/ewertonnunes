---
name: spec-author
description: |
  Use quando o usuário pedir para criar, editar, ou estender um
  spec.yaml ou spec_schema.py. Cobre desenho de campos, escolha de
  tipos (Enum vs str+regex vs int+range), validadores customizados,
  computed_field, e a regra-mãe `extra=forbid`. Acione antes de
  qualquer alteração em spec.yaml ou spec_schema.py em qualquer
  exemplo, ou ao criar um exemplo novo do zero.
---

# spec-author

Você está autorando um spec (`spec.yaml` + `spec_schema.py`). Estes
arquivos são a **fronteira de confiança** do gerador — tudo o que passar
deles entra no sistema sem outra validação. Erre forte aqui e o
projeto inteiro fica permeável.

## Checklist obrigatório antes de propor o spec

- [ ] Toda classe tem `model_config = {"extra": "forbid"}`
- [ ] Toda string livre tem `pattern=r"..."` ou virou `Enum`
- [ ] Todo inteiro tem `ge=...` e `le=...` apropriados
- [ ] Toda lista tem `min_length=1` (a menos que vazio seja semanticamente válido)
- [ ] Versões seguem regex: `r"^\d+\.\d+\.\d+$"` (ou `r"^\d+\.\d+$"`)
- [ ] Identificadores kebab-case: `r"^[a-z][a-z0-9-]{N,M}$"`
- [ ] Nomes Python: `r"^[a-z_][a-z0-9_]*$"`
- [ ] Valores derivados ficam em `@computed_field`, não no template
- [ ] Invariantes cross-field viram `@field_validator` ou `@model_validator`

## Regras práticas

### Quando usar Enum vs regex

- **Enum** quando o conjunto é fechado e nomeável: ambientes
  (`dev|staging|prod`), times, sizes (`xs|s|m|l|xl`), vendors.
- **Regex** quando o conjunto é infinito mas tem forma: versões,
  identificadores, paths, URLs.
- **Nunca** `str` puro sem regex/enum, a menos que seja prosa
  (description, app_name).

### Quando usar computed_field

Use sempre que um valor seja **derivado** de outros campos. Exemplos
do repo:

```python
@computed_field
@property
def package_path(self) -> str:
    # com.example.foo → com/example/foo
    return self.package.replace(".", "/")

@computed_field
@property
def main_class(self) -> str:
    # health-api → HealthApiApplication
    camel = "".join(p.title() for p in self.artifact_id.split("-"))
    return f"{camel}Application"
```

**Por quê:** sem computed_field, a derivação aparece no template
(`{{ project.module | replace('.', '/') }}`) — três templates depois,
você tem três regras de derivação ligeiramente diferentes. Centralize.

### Quando usar @field_validator

Invariantes que envolvem mais de um campo, ou validações que regex
não expressa:

```python
@field_validator("replicas")
@classmethod
def prod_min_replicas(cls, v: int, info) -> int:
    if info.data.get("environment") == Environment.PROD and v < 2:
        raise ValueError("prod requires >=2 replicas (HA)")
    return v

@field_validator("runtime_dependencies")
@classmethod
def deps_pinned(cls, v: list[str]) -> list[str]:
    import re
    pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*\s*[><=!~]+\s*[\d.]+")
    for dep in v:
        if not pattern.match(dep) and "types-" not in dep:
            raise ValueError(f"dependency must be pinned: {dep!r}")
    return v
```

## Antipadrões a recusar

| Antipadrão | Por que evitar | Alternativa |
|---|---|---|
| `extra="allow"` | Campo com typo passa silenciosamente | `extra="forbid"` |
| `Optional[str] = None` sem motivo | Vira código condicional no template | Default explícito ou obrigatório |
| `str` puro | Aceita qualquer coisa | regex ou Enum |
| Default mágico (`port: int = 8080`) | Spec parece completo mas não é | Campo obrigatório; default por convenção docs |
| Lista sem `min_length=1` | Aceita lista vazia que quebra template | `min_length=1` se a vazio for inválido |

## Fluxo para criar/editar spec

1. Entender o domínio: o que muda entre instâncias do template?
2. Esboçar o YAML mínimo (campos sem os quais o template não funciona)
3. Para cada campo: tipo? enum? regex? range? derivado?
4. Escrever o `spec_schema.py` com Pydantic
5. Validar manualmente:
   ```bash
   python -c "import yaml; from spec_schema import ProjectSpec; \
              print(ProjectSpec.model_validate(yaml.safe_load(open('spec.yaml'))))"
   ```
6. Tentar **propositalmente** valores inválidos e ver se falha alto
7. Se passar campo errado e não falhar, o schema não está rígido o bastante

## Referências internas

- `docs/METHODOLOGY.md` §1 — "Schema rígido é a primeira linha de defesa"
- `examples/deploy-agent/spec_schema.py` — exemplo mais complexo (LLM agent)
- `examples/java-service/spec_schema.py` — computed_field intenso
- `examples/go-service/spec_schema.py` — exemplo mais simples
