# Design Notes

Decisões de arquitetura, com justificativas e alternativas consideradas.

## Por que Pydantic e não JSON Schema puro

Pydantic dá:
- Tipagem Python real (`int`, `Enum`, `Literal`, etc.)
- Validadores customizados (`@field_validator`, `@model_validator`)
- `computed_field` para derivar valores no contexto (e.g. `package_path`
  a partir de `module`)
- Mensagens de erro úteis sem código adicional
- Geração de JSON Schema *quando necessário* (e.g. para tool use em LLM)

JSON Schema puro forçaria reinventar tudo isso.

## Por que Jinja2

- Padrão de facto em Python (Ansible, Salt, Flask, Django, Sphinx)
- `StrictUndefined` resolve 90% dos bugs silenciosos
- Whitespace control (`{%- ... -%}`) crítico para byte-estabilidade
- Custom filters fáceis de plugar (e.g. `pynum`)

Alternativas consideradas:
- **f-strings + dict** — funciona pra casos simples, vira sopa em casos reais
- **Mako/Cheetah** — menos popular, sem ganho funcional sobre Jinja
- **Handlebars/Mustache** — semantica fraca demais para condicionais reais

## Por que `.tmpl` e não `.j2`

Esta foi uma descoberta concreta durante o desenvolvimento.

**O problema:** o gerador percorre `files/` e renderiza qualquer
`.j2` que encontra. Mas o agente de deploy (um dos exemplos) usa
Jinja em *runtime* para renderizar manifests Kubernetes, e seus
templates de runtime *também* terminam em `.j2`.

**A confusão:** o gerador tentava renderizar os templates de runtime
do agente como se fossem do próprio gerador, com contexto errado,
quebrando.

**A solução:** `.tmpl` para templates do gerador, `.j2` reservado
para a aplicação gerada. O gerador trata `.j2` como bytes literais.

Isso é um caso clássico de "convenção pequena, dor enorme se ignorada".

## Por que walk ordenado (`sorted(rglob)`)

Filesystems não garantem ordem ao listar diretórios. ext4 retorna
em ordem de inode, btrfs em ordem alfabética, NTFS em ordem de
criação. Sem `sorted()`, o mesmo gerador em máquinas diferentes
produz lockfiles diferentes — não em conteúdo, mas em ordem de
processamento que vaza para a aggregate hash.

`sorted()` no caminho relativo dá ordem consistente independente
do filesystem.

## Por que JSON e não TOML/YAML para o lockfile

- JSON tem `sort_keys=True` trivial. TOML não tem (vários parsers
  ordenam diferente).
- YAML é ambíguo demais (citação automática, escape regional, etc.).
- JSON é parseável por qualquer linguagem sem dependências.
- O lockfile não é editado a mão; estética não importa.

## Por que `extra=forbid` por padrão

A pior categoria de bug é "campo no spec sendo ignorado silenciosa-
mente porque tem typo". Com `extra=forbid`, qualquer campo
desconhecido na entrada quebra. Operador precisa ser explícito.

Custo: spec migrations (adicionar campo opcional) precisam de
defaults na schema. Vale a pena.

## Por que computed_field

Templates frequentemente precisam de valores *derivados* do spec:

- `package_path` = `module` com `.` → `/`
- `main_class` = `artifact_id` em PascalCase + "Application"
- `binary_name` = `name` mais sufixo

Três opções:
1. Hardcoded no template (`{{ project.module | replace('.', '/') }}`)
2. Calculado num context_builder customizado por gerador
3. Pydantic `@computed_field`

Opção 3 é a melhor:
- Centraliza a lógica de derivação no schema (perto da definição)
- Aparece automaticamente em `model_dump(mode="json")`
- Testável independente do gerador

Opção 1 vira inconsistência (cada template re-implementa a regra).
Opção 2 espalha lógica de domínio em arquivos do gerador.

## Por que path templating (e onde para)

Java exige `src/main/java/com/example/app/` casado com o nome do
pacote. Sem path templating, ou você hardcoda o pacote no gerador,
ou força o usuário a renomear diretórios manualmente.

A solução: Jinja na string do path também, não só no conteúdo.
`files/src/main/java/{{project.package_path}}/Application.java.tmpl`
funciona.

**Limites:** path templating só substitui `{{ var }}`, não roda
condicionais complexas. Filenames `{% if x %}foo{% else %}bar{% endif %}`
não vão funcionar — e tudo bem, é uma simplicidade intencional.

## Por que CLI + biblioteca

Casos de uso diferentes:

- **CLI** — para CI scripts, Makefiles, integração externa.
  `spec-codegen generate --spec ... --files ...` é trivial.
- **Biblioteca** — para casos que precisam de context_builder
  customizado, filters extras, ou integração programática (e.g.
  um portal interno que chama `Generator(...)` direto).

Manter os dois é barato; um simplesmente embrulha o outro.

## Por que NÃO incluímos `git` ou `gh`

Tentadora ideia: o gerador podia commitar e abrir PR direto.
Decidimos não fazer por:

- O escopo da biblioteca é geração determinística, não orquestração
- Cada org tem seu fluxo (`gh`, GitLab, Bitbucket, branch protection
  diferente)
- Adicionar `git` cria dependência de processo externo, mata
  portabilidade
- O caller pode fazer `git add lockfile.json files/ && git commit` em
  3 linhas — sem precisar de biblioteca

Princípio Unix: faça uma coisa bem.

## Quando esta biblioteca *NÃO* é a resposta

Já dito no `METHODOLOGY.md`, mas vale repetir aqui:

- Quando o requisito é "scaffolding e basta" → use Cookiecutter
- Quando precisa transformar código existente → use OpenRewrite
- Quando o output muda em runtime → use Jinja diretamente
- Quando o spec não tem schema possível (ex: prosa criativa) →
  esse caso simplesmente não é geração determinística

## Versionamento e compatibilidade

`spec-codegen` segue SemVer. Mudanças breaking:

- Mudança na assinatura de `Generator.__init__` ou `generate()`
- Mudança no formato do `lockfile.json` (versionado por `version: N`)
- Remoção de filtros built-in (`pynum`, `shellesc`)

Mudanças NÃO breaking (não bumpam major):
- Novos filtros adicionados ao Jinja env
- Novas chaves opcionais nos error reports
- Performance / mensagens de log

O `lockfile.json` tem campo `version`, hoje `1`. Se um dia mudarmos
o formato, o `Verifier` ainda saberá ler v1 com aviso.
