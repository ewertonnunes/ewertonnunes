# A Metodologia

> Os cinco princípios de determinismo que destilamos durante o desenvolvimento
> desta biblioteca, generalizando de "agente LLM determinístico" para
> "qualquer geração de projeto determinística".

## A jornada

O ponto de partida foi uma pergunta concreta:

> *Como tornar agentes LLM determinísticos e evitar alucinações?*

A resposta evoluiu em camadas:

1. **Para agentes LLM:** confine o modelo numa caixa estreita
   (`temperature=0`, `tool_choice` forçado, schema rígido, retry com
   feedback de erro). O LLM só extrai parâmetros validados.

2. **Para o agente em si (o código):** se o agente é importante o
   suficiente para precisar ser determinístico, ele mesmo precisa ser
   determinístico. Não peça pro LLM recriar o código — guarde
   spec + gerador.

3. **Para projetos em geral:** o padrão se aplica a *qualquer*
   geração de projeto. Spec + Pydantic + Jinja + lockfile resolve
   scaffolding de microsserviços, Terraform modules, Helm charts,
   qualquer coisa.

4. **Para a biblioteca aqui:** a observação que cada gerador específico
   (Java, Go, Python) usa o mesmo motor com schemas diferentes →
   extraímos o motor.

Esta metodologia é o que ficou na destilação.

---

## Princípio 1 — Schema rígido é a primeira linha de defesa

**O que é:** todo valor que entra no gerador passa por um schema
Pydantic com `extra=forbid`, enums fechados, regex/range para tipos
livres, e validadores customizados para invariantes de negócio.

**Por quê:** o spec é a única forma de mudar o output do gerador. Se
o schema permite valores inválidos, o gerador propaga lixo.

**Exemplo:**

```python
class Java(BaseModel):
    model_config = {"extra": "forbid"}
    version: int = Field(..., ge=17, le=30)       # range fechado
    vendor: Vendor                                 # enum, não string
```

Tentar passar `java.version: 99` ou `java.vendor: "oracle-legacy"`
**falha no `model_validate` antes de qualquer arquivo ser tocado**.

**Antipadrão:** validações distribuídas no template (`{% if version > 17 %}`).
Validação tem que ser na fronteira, num só lugar, em código tipado.

---

## Princípio 2 — Template é o contrato; o LLM nunca toca código

**O que é:** todo arquivo final vem de um template literal versionado em
`files/`, renderizado pelo gerador. Nenhum LLM. Em nenhum momento.

**Por quê:** mesmo com `temperature=0`, LLMs produzem variações
estilísticas, reordenam imports, reescrevem docstrings, alteram
tratamento de edge cases. Isso é drift invisível.

**Mecânica:**

- Arquivos `.tmpl` são templates Jinja renderizados pelo gerador
- Arquivos sem `.tmpl` são copiados verbatim (bytes idênticos)
- Templates ficam em Git, versionados, com PRs revisáveis

**Convenções da biblioteca:**

- `.tmpl` (não `.j2`) — reservado para templates *do gerador*. O
  sufixo `.j2` é deixado intacto para projetos que usam Jinja em
  runtime (e.g. deploy-agent renderiza manifests Kubernetes com `.j2`).
- `.keep` — arquivo marcador para forçar criação de diretório vazio
  (`rglob` ignora dirs vazios; `.keep` resolve sem ruído).

**Antipadrão:** "agente que escreve o serviço" → você troca um problema
de scaffolding por um problema de revisão de código gerado por máquina.

---

## Princípio 3 — Render é função pura

**O que é:** dado o mesmo spec + os mesmos arquivos, o output é
identicamente o mesmo *byte* a cada execução, em qualquer máquina.

**Por quê:** determinismo é uma propriedade só verificável
empiricamente. Se você não consegue rodar duas vezes e ter `diff -r`
vazio, você não tem determinismo — você tem sorte.

**Implementação:**

```python
for src in sorted(FILES_DIR.rglob("*")):       # ordenação explícita
    ...
env = Environment(
    undefined=StrictUndefined,                  # var ausente quebra alto
    keep_trailing_newline=True,                 # sem drift de \n
    autoescape=False,                           # determinismo > segurança HTML
)
json.dump(payload, sort_keys=True, ensure_ascii=True)  # JSON estável
```

**Armadilhas conhecidas e suas soluções:**

| Armadilha | Sintoma | Solução |
|---|---|---|
| `rglob` sem `sorted()` | Hash muda entre filesystems | `sorted(rglob)` |
| `Undefined` permissivo | Erro silencioso, valor vazio | `StrictUndefined` |
| Pydantic `float` virando `0.0` | `temperature=0` vira `temperature=0.0` | filtro custom `pynum` |
| `json.dumps` sem `sort_keys` | Lockfile reorganiza randomicamente | `sort_keys=True` |
| `{% endif %}` deixa newline | Trailing `\n` extra | `{%- endif %}` |
| Diretórios vazios sumindo | `rglob` ignora dirs vazios | marker `.keep` |

Cada uma dessas foi descoberta empiricamente. Cada uma representa horas
debugando "por que o hash mudou?". Cada uma agora está dentro da
biblioteca.

---

## Princípio 4 — Lockfile é a prova de reprodutibilidade

**O que é:** um JSON committed no repo com SHA-256 de cada arquivo
gerado, ordenado, formatado de forma byte-estável.

**Por quê:** o lockfile responde à pergunta *"o que era o output da
última vez que esse projeto foi tratado como correto?"*. É a fonte
de verdade contra a qual toda regeneração é comparada.

**Estrutura:**

```json
{
  "file_count": 23,
  "files": {
    "Dockerfile": "5d128fc3add8…",
    "pom.xml": "e15399639059…",
    "src/main/java/.../Application.java": "279ea3def6dc…"
  },
  "version": 1
}
```

**Operação no CI:**

```yaml
- run: spec-codegen verify --spec spec.yaml --schema ... --files files
```

Se a regeneração das fontes atuais não bate com o lockfile, exit 1, PR
bloqueado. O único jeito de "mudar o output" é mudar o spec/files **e**
atualizar o lockfile no mesmo commit. Drift acidental é estrutural-
mente impossível.

**Analogia operacional:** lockfile aqui é o equivalente conceitual de
`package-lock.json`, `Cargo.lock`, `poetry.lock` — mas para
**outputs** em vez de **inputs**.

---

## Princípio 5 — Falha alta e específica vence sucesso silencioso

**O que é:** todo erro (schema inválido, template quebrado, drift
detectado) produz mensagem específica e exit code não-zero. Nada de
"warnings que viram bug em produção semanas depois".

**Por quê:** sistemas determinísticos só funcionam se *você confia
em silêncio*. Se o gerador roda sem erro, o output está certo. Se há
qualquer problema, ele aparece imediatamente, alto, com contexto.

**Exemplos de mensagens da biblioteca:**

```
✗ DRIFT DETECTED

  Hash mismatch (3):
    ~ Dockerfile
      expected 5d128fc3add8…  got 9a4f12b6c834…
    ~ pom.xml
      ...
    ~ README.md
      ...
```

```
ValidationError: 3 errors for ProjectSpec
project.version
  String should match pattern '^\d+\.\d+\.\d+$' [input_value='1.2', ...]
project.replicas
  Input should be less than or equal to 10 [input_value=20, ...]
```

**Antipadrão:** "use defaults razoáveis quando o spec é inválido". Não.
Defaults silenciosos são a fonte de 90% dos bugs de configuração.
Falhe. Force o operador a ser explícito.

---

## Os 5 princípios em ação: um diagrama

```
                    spec.yaml
                       │
            ┌──────────┴──────────┐
            ▼                      ▼
   [P1] Schema rígido       [P5] Falha alta
   (Pydantic, extra=forbid)    se inválido
            │
            ▼
       contexto válido
            │
            ▼
   [P2] Template renderer  ←── files/*.tmpl (Git)
   (Jinja, StrictUndefined)
            │
            ▼
   [P3] Render determinístico
   (sorted walk, byte-stable JSON, .tmpl/.keep convenções)
            │
            ▼
       arquivos + hashes
            │
            ▼
   [P4] Lockfile (SHA-256 por arquivo)
            │
            ▼
        commit no Git
            │
            ▼
   [P4] Verifier no CI  ──►  [P5] Bloqueia PR se drift
```

---

## Onde os princípios *não* se aplicam

Honestidade intelectual: este padrão **não** é a solução para tudo.

- **Refatoração de código existente.** Se você já tem 50k linhas e
  quer modernizar, use OpenRewrite / codemods. Esta biblioteca é para
  *geração*, não transformação.

- **Scripts ad-hoc únicos.** Se você precisa de um Bash de 20 linhas
  pra essa semana, escreva o Bash. Não precisa de spec.

- **Templates muito dinâmicos.** Se 80% do conteúdo depende de
  condicionais complexas, Jinja vira código-em-string. Considere
  gerar com código Python real e usar a biblioteca só para os outputs
  fixos.

- **Coisa que não é determinística por natureza.** Geração que
  depende de chamada de API externa, timestamp, randomness, etc.,
  pode usar este padrão para a parte determinística, mas a parte
  "viva" tem que ficar fora.

---

## A regra de ouro

> Quanto mais crítica a geração, mais determinística ela deve ser, e
> mais o LLM (se aparecer) deve ocupar apenas o papel de *extrator de
> intenção em campos schema-validados*, nunca de produtor do output.

Tudo nesta biblioteca é a operacionalização dessa frase.
