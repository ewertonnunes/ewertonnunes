---
name: example-builder
description: |
  Use quando o usuário pedir para adicionar um exemplo novo em
  examples/ — um gerador completo para uma stack diferente (Rust,
  Node, Terraform module, Helm chart, etc.). Cobre a estrutura
  obrigatória, a ordem certa de construção, e o teste final
  end-to-end que prova reprodutibilidade.
---

# example-builder

Você está adicionando um exemplo novo em `examples/<nome>/`. O exemplo
precisa funcionar 100% sob o motor `spec_codegen` existente — sem
modificá-lo. Se você se vê precisando alterar `src/spec_codegen/`,
**pare e pergunte**: provavelmente é um caso que pode ser resolvido
no schema/template.

## Estrutura obrigatória

```
examples/<nome>/
├── spec.yaml           ← fonte da verdade (humano edita)
├── spec_schema.py      ← Pydantic com ProjectSpec
├── files/              ← templates + arquivos literais
│   └── ... (estrutura do projeto a gerar)
└── lockfile.json       ← gerado, NUNCA editado a mão
```

A classe Pydantic principal **deve se chamar `ProjectSpec`** —
o teste `tests/test_examples_reproduce.py` importa por esse nome.

## Ordem de construção (sequência importa)

1. **Entender a stack-alvo.** Que arquivos um projeto típico desta
   tecnologia tem? Quais variam entre instâncias?

2. **Esboçar o `spec.yaml`** com os campos mínimos. Use a skill
   `spec-author` aqui.

3. **Escrever o `spec_schema.py`.** Classe `ProjectSpec` com `extra=forbid`.

4. **Validar o schema antes dos templates:**
   ```bash
   cd examples/<nome> && python -c "import yaml; from spec_schema import ProjectSpec; \
     print(ProjectSpec.model_validate(yaml.safe_load(open('spec.yaml'))))"
   ```

5. **Construir `files/` incrementalmente.** Comece com 1-2 arquivos.
   Renderize. Inspecione. Adicione mais. Use a skill `template-author`.

6. **Geração inicial + lockfile:**
   ```bash
   cd examples/<nome>
   spec-codegen generate \
     --spec spec.yaml --schema spec_schema.py:ProjectSpec \
     --files files --out /tmp/<nome>-out \
     --write-lockfile --lockfile lockfile.json
   ```

7. **Bateria de reprodutibilidade** (a mesma que rodamos nos outros):
   ```bash
   cd examples/<nome>
   # Run 1
   spec-codegen generate --spec ... --out /tmp/run1 > /dev/null
   H1=$(cd /tmp/run1 && find . -type f | sort | xargs sha256sum | sha256sum | awk '{print $1}')
   # Destroy + Run 2
   rm -rf /tmp/run1
   spec-codegen generate --spec ... --out /tmp/run1 > /dev/null
   H2=$(cd /tmp/run1 && find . -type f | sort | xargs sha256sum | sha256sum | awk '{print $1}')
   # Destroy + Run 3
   rm -rf /tmp/run1
   spec-codegen generate --spec ... --out /tmp/run1 > /dev/null
   H3=$(cd /tmp/run1 && find . -type f | sort | xargs sha256sum | sha256sum | awk '{print $1}')

   [ "$H1" = "$H2" ] && [ "$H2" = "$H3" ] && echo "✓ 3/3 idêntico"
   ```

8. **Verify do lockfile:**
   ```bash
   spec-codegen verify --spec ... --files files --lockfile lockfile.json
   # → ✓ N files reproduced byte-for-byte
   ```

9. **Rodar o teste do repo inteiro:**
   ```bash
   make test
   # Tem que pegar o exemplo novo automaticamente (parametrizado)
   ```

10. **Se a stack tem compilador disponível, compile o output:**
    ```bash
    cd /tmp/<nome>-out && <build command>
    ```
    Não é obrigatório, mas pega bugs lógicos rapidamente.

## Anatomia mínima por stack (templates de referência)

### Linguagem compilada (Go, Rust, Java)
- `<build manifest>.tmpl` — go.mod, Cargo.toml, pom.xml
- `Dockerfile.tmpl` — multi-stage, usuário não-root
- `Makefile.tmpl` — build, test, lint, clean
- `README.md.tmpl` — descrição, comandos, estrutura
- `.gitignore` — literal, não-templated
- Código-fonte mínimo (1 entry point + 1 handler + 1 test)

### Linguagem interpretada (Python, Node)
- `<manifest>.tmpl` — pyproject.toml, package.json
- Outros iguais à compilada
- `__init__.py` ou equivalente

### Infrastructure-as-code (Terraform, Helm)
- `<manifest>.tmpl` — Chart.yaml, versions.tf
- Recursos templados
- `values.yaml.tmpl` ou variáveis tf
- `README.md.tmpl`

## Checklist pré-PR

- [ ] `spec.yaml` valida sob `spec_schema.py`
- [ ] Geração produz output esperado (inspeção visual)
- [ ] `lockfile.json` está committed
- [ ] `spec-codegen verify` retorna `✓`
- [ ] 3x destroy/recreate produz hash idêntico
- [ ] `make test` verde (incluindo `test_examples_reproduce`)
- [ ] Output compila/roda se o ambiente de CI suportar
- [ ] README do exemplo (se aplicável) documenta o que ele faz
- [ ] CHANGELOG da raiz atualizado (linha curta)

## Referências internas

- `examples/go-service/` — exemplo mais limpo, comece copiando
- `examples/java-service/` — exemplo com path templating
- `examples/deploy-agent/` — exemplo mais complexo (LLM dentro)
- `tests/test_examples_reproduce.py` — como o CI vai te testar
