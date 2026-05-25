# CLAUDE.md

Você está trabalhando no **`spec-codegen`**, uma biblioteca Python para
**geração determinística de projetos** a partir de um spec validado por
schema. Este arquivo é seu briefing — leia tudo antes da primeira ação.

## Em uma frase

O **spec** é o código que importa; o **gerador** é uma função pura;
o **lockfile** é o juiz; o **hash SHA-256** é a prova.

## A invariante central

Quando o usuário pede para criar/mudar algo nesse repo, **a regra única
acima de qualquer outra é:**

> **Toda regeneração a partir das fontes (spec.yaml + files/) deve
> produzir o mesmo projeto byte-a-byte.**

Se uma mudança quebra essa invariante, ela é um bug — não importa o
quão "útil" pareça. O CI tem um teste que verifica isto em todos os
exemplos (`tests/test_examples_reproduce.py`); rode-o cedo, rode-o
sempre.

## Arquitetura mental

```
spec.yaml          ←  fonte da verdade (humano edita)
spec_schema.py     ←  Pydantic, valida o spec
files/             ←  templates Jinja (.tmpl) + arquivos literais
       │
       ▼
   Generator       ←  função pura: (spec, files) → output
       │
       ├─►  output/         (o projeto gerado)
       └─►  lockfile.json   (SHA-256 de cada arquivo)
              │
              ▼
          Verifier          (CI: regen == lockfile?)
```

Em `examples/` há 3 instâncias completas desse padrão (deploy-agent,
java-service, go-service). Quando estiver em dúvida sobre como
estruturar algo, copie o padrão deles.

## Os 5 princípios (resumo; íntegra em `docs/METHODOLOGY.md`)

1. **Schema rígido na fronteira** — `extra=forbid`, enums, regex, ranges.
2. **Template é o contrato** — nada de LLM gerar código; templates `.tmpl` em Git.
3. **Render é função pura** — `sorted(rglob)`, `StrictUndefined`, `keep_trailing_newline`.
4. **Lockfile prova reprodutibilidade** — SHA-256 por arquivo, JSON byte-estável.
5. **Falha alta e específica** — exit não-zero com mensagem precisa.

## Convenções do repo (NÃO QUEBRE)

- `.tmpl` → template renderizado pelo gerador (uma vez, no `generate`)
- `.j2`  → template usado em **runtime** pela aplicação gerada; passa
  intacto pelo gerador. **Nunca trate `.j2` como `.tmpl`.**
- `.keep` → marcador para forçar diretório vazio; não vai pro output
- `{{ var }}` em **nomes de diretório ou arquivo** é renderizado
  (path templating). Use só `{{ namespace.field }}`, sem espaços
  internos ou condicionais.
- Lockfile: JSON com `sort_keys=True`, `ensure_ascii=True`, LF final.
  **Nunca edite à mão**; só regenere via `--write-lockfile`.

## Workflow obrigatório para mudanças

Qualquer mudança em `examples/*/files/`, `examples/*/spec.yaml`, ou
em `src/spec_codegen/`:

```bash
# 1. Faça a mudança
$EDITOR examples/go-service/spec.yaml

# 2. Regenere o lockfile do(s) exemplo(s) afetado(s)
make regenerate-examples
# ou pontualmente:
cd examples/go-service && spec-codegen generate \
  --spec spec.yaml --schema spec_schema.py:ProjectSpec \
  --files files --out /tmp/out --write-lockfile

# 3. Confirme determinismo
make verify-examples

# 4. Rode todos os testes
make check
```

**Se você modifica um template e não atualiza o lockfile, o CI quebra.**
Se você atualiza o lockfile sem mudar template/spec, isso aparece como
mudança suspeita no PR — também ruim. Os dois andam juntos.

## Comandos canônicos

| Comando | O que faz |
|---|---|
| `make install` | `pip install -e ".[dev]"` |
| `make test` | core + reprodutibilidade de todos os exemplos |
| `make check` | lint + types + test |
| `make regenerate-examples` | regera lockfile de todos os exemplos |
| `make verify-examples` | confirma reprodutibilidade dos 3 exemplos |
| `spec-codegen generate ...` | CLI canônica de geração |
| `spec-codegen verify ...` | CLI canônica de verificação |

## Skills disponíveis em `.claude/skills/`

Quando o usuário pedir algo que casa com um destes domínios, **carregue
a skill correspondente** antes de agir:

| Skill | Quando usar |
|---|---|
| `spec-author/` | criar/editar `spec.yaml` + `spec_schema.py` |
| `template-author/` | criar/editar arquivos em `files/` (`.tmpl`, paths) |
| `example-builder/` | adicionar um novo exemplo em `examples/` |
| `drift-debugger/` | `verify` falhou; investigar drift |
| `lockfile-updater/` | atualizar lockfile após mudança intencional |

## Coisas que você NÃO deve fazer (sem confirmar explicitamente)

- ❌ Editar `lockfile.json` à mão — sempre via `--write-lockfile`
- ❌ Adicionar dependência runtime sem versão pinada (`pkg>=X.Y`)
- ❌ Substituir `.tmpl` por `.j2` ou vice-versa
- ❌ Usar `model_config = {"extra": "allow"}` ou similar
- ❌ Soltar `temperature` ou `tool_choice` em qualquer exemplo de LLM
- ❌ Adicionar default mágico no schema que esconde campo faltando
- ❌ "Melhorar" um template com mudança não-pedida (vira drift invisível)
- ❌ Mover `examples/` ou renomear schema-classes sem ajustar testes

## Coisas que você DEVE fazer

- ✅ Rodar `make check` antes de dizer "pronto"
- ✅ Atualizar `lockfile.json` no MESMO commit que muda template/spec
- ✅ Se um teste de reprodutibilidade falhar, **parar e investigar**
  com `drift-debugger`. Drift quase nunca é "atualizar lockfile e seguir"
- ✅ Citar o princípio relevante (`METHODOLOGY.md` §N) quando justificar
  uma decisão estrutural

## Estado atual conhecido (na entrega 1.0.0)

```
30/30 testes passando
70% cobertura do core
Exemplos:
  deploy-agent  → 23 arquivos, hash e1d1ab82d293e30f...
  java-service  →  8 arquivos, hash b672d88c5158fdda1...
  go-service    →  8 arquivos, hash 8da306bd021a594fb...
```

Se os hashes mudarem **e** não houve mudança intencional, há um bug —
pode ser na biblioteca, no template, ou (raramente) no Python/Jinja
upstream. Investigue antes de aceitar o novo hash.

## Onde achar contexto adicional

- `README.md` — manifesto do projeto
- `docs/METHODOLOGY.md` — os 5 princípios em prosa completa
- `docs/DESIGN.md` — decisões de arquitetura e alternativas consideradas
- `examples/*/` — 3 instâncias completas que servem como referência

## Tom

O usuário deste projeto se importa com determinismo de verdade. Seja
direto, ofereça a opção mais determinística primeiro, e quando houver
trade-off, nomeie-o explicitamente. Não se desculpe por ser rigoroso —
o rigor é o produto.
