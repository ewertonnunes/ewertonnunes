# spec-codegen

> **Destrua o projeto. Regenere. Bytes idênticos. Sempre.**

`spec-codegen` é uma biblioteca minimalista para geração determinística
de código a partir de um **spec.yaml** validado por schema. É o produto
destilado de uma investigação sobre determinismo em sistemas com LLM,
generalizada para qualquer geração de projeto.

[![reprodutibilidade](https://img.shields.io/badge/reprodutibilidade-byte--a--byte-success)]()
[![python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![license](https://img.shields.io/badge/license-Apache--2.0-lightgrey)]()

## A ideia em uma frase

O **spec** é o código que importa; o **gerador** é uma função pura;
o **lockfile** é o juiz; o **hash SHA-256** é a prova.

## Por que existe

LLMs são ótimos para extrair intenção, péssimos para reproduzir bytes.
Mas a maior parte do que chamamos de "scaffolding" não precisa de IA —
precisa de **um spec versionado + um gerador determinístico**.

Esta biblioteca foi construída depois de descobrir, na prática, que:

1. **Mesmo `temperature=0`, LLMs não reproduzem código byte-a-byte.**
2. **Cookiecutter resolve scaffolding, mas não verifica reprodutibilidade.**
3. **A combinação `spec validado + render Jinja + lockfile SHA-256`
   resolve, é trivial de auditar e se transfere entre linguagens.**

## Instalação

```bash
pip install spec-codegen
```

## Quick start

```bash
spec-codegen generate \
  --spec spec.yaml \
  --schema ./spec_schema.py:ProjectSpec \
  --files ./files \
  --out ./my-project \
  --write-lockfile

# Em qualquer máquina, com as mesmas sources:
spec-codegen verify \
  --spec spec.yaml \
  --schema ./spec_schema.py:ProjectSpec \
  --files ./files
# → ✓ N files reproduced byte-for-byte
```

## Como funciona em 30 segundos

```
spec.yaml ─┐
            │
spec_schema.py (Pydantic) ─►  validação rígida (enum, regex, ranges)
            │
            ▼
files/  ─►  walk ordenado
              │
              ├── *.tmpl  → render Jinja com contexto do spec
              └── outros  → copy verbatim
              │
              ▼
        SHA-256 por arquivo
              │
              ├──►  output/  (o projeto gerado)
              └──►  lockfile.json  (a prova)
```

## Exemplo: gerador de serviço Go em 4 arquivos

**`spec.yaml`:**

```yaml
project:
  name: "health-api"
  module: "github.com/example/health-api"
  version: "1.0.0"
  app_name: "Health API"
go:
  version: "1.26"
  toolchain: "go1.26.3"
server:
  port: 8080
```

**`spec_schema.py`:**

```python
from pydantic import BaseModel, Field

class Project(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(..., pattern=r"^[a-z][a-z0-9-]{1,40}$")
    module: str
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    app_name: str

class Go(BaseModel):
    model_config = {"extra": "forbid"}
    version: str
    toolchain: str

class Server(BaseModel):
    model_config = {"extra": "forbid"}
    port: int = Field(..., ge=1024, le=65535)

class ProjectSpec(BaseModel):
    model_config = {"extra": "forbid"}
    project: Project
    go: Go
    server: Server
```

**`files/go.mod.tmpl`:**

```
module {{ project.module }}

go {{ go.version }}
toolchain {{ go.toolchain }}
```

**`files/cmd/server/main.go.tmpl`:**

```go
package main

import "net/http"

func main() {
    http.ListenAndServe(":{{ server.port }}", nil)
}
```

E pronto. `spec-codegen generate` produz o projeto. `verify` confirma
reprodutibilidade.

## Mais exemplos

Veja [`examples/`](./examples/) para três geradores prontos:

| Exemplo | Stack | Arquivos gerados | Hash agregado |
|---|---|---|---|
| `deploy-agent/` | Python + LLM agent para Kubernetes | 23 | `e1d1ab82…` |
| `java-service/` | Java 25/26 + Spring Boot 4 | 8 | `b672d88c…` |
| `go-service/` | Go 1.26 + net/http | 8 | `8da306bd…` |

Cada um reprodutível indefinidamente; cada um com seu próprio `lockfile.json`.

## Recursos do gerador

- **Schema rígido** — Pydantic com `extra=forbid`, enums, regex, ranges
- **Path templating** — `{{ project.package_path }}` em nomes de diretório
- **`.tmpl` extension** — separa templates do gerador dos `.j2` de runtime
- **`.keep` markers** — força criação de diretórios vazios
- **`pynum` filter** — `0.0` → `"0"`, `0.5` → `"0.5"` (resolve drift `int`↔`float`)
- **Walk ordenado** — `sorted(rglob)` mata variação por filesystem
- **JSON estável** — `sort_keys=True`, `ensure_ascii=True`, LF final
- **CLI canônica** — `spec-codegen generate` / `spec-codegen verify`
- **Biblioteca Python** — `from spec_codegen import Generator, Verifier`

## Workflow recomendado no CI

```yaml
# .github/workflows/verify.yaml
name: verify
on: [pull_request, push]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install spec-codegen
      - run: |
          spec-codegen verify \
            --spec spec.yaml \
            --schema spec_schema.py:ProjectSpec \
            --files files
```

Qualquer commit que altere `files/` ou `spec.yaml` sem atualizar o
`lockfile.json` é bloqueado aqui.

## Documentação

- **[METHODOLOGY.md](docs/METHODOLOGY.md)** — Os 5 princípios do determinismo
- **[DESIGN.md](docs/DESIGN.md)** — Decisões de arquitetura
- **[examples/](examples/)** — Geradores prontos para Go, Java e Python

## Para quem isto serve

- **Plataformas internas** que precisam padronizar dezenas de serviços
- **GitOps** onde drift entre repo e cluster é o pior cenário
- **Auditoria/compliance** que exige rastreabilidade de toda mudança
- **DevEx** que cansou de bagunça em template-de-template repos
- **Quem ouviu "LLM gera código pra você" e quer determinismo de verdade**

## Limites honestos

Não é pra:

- Refactoring de codebase existente (use OpenRewrite, Codemod)
- Geração ad-hoc de scripts curtos (use ChatGPT, fim)
- Macros em runtime (use Jinja/template engine direto)
- Substituir Cookiecutter quando você só quer scaffolding sem CI checks

É pra:

- Sistemas onde "destruir e recriar com bytes iguais" é requisito de produção
- Sistemas onde drift silencioso entre PRs custa caro

## Licença

Apache 2.0
