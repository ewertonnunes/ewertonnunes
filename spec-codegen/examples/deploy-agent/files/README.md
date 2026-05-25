# deploy-agent

Agente determinístico para deploy de aplicações em Kubernetes via GitOps.
O LLM aparece em **um único ponto** do pipeline (extração de parâmetros);
todo o resto é código puro, idempotente e auditável.

## A ideia em uma frase

> O template é a fonte da verdade. O LLM só preenche variáveis tipadas,
> validadas por schema, gateadas por policy, aplicadas via PR. Qualquer
> desvio do template é falha de pipeline, não surpresa em produção.

## Arquitetura

```
request (linguagem natural)
        │
        ▼
  ┌──────────────┐
  │  EXTRACTOR   │  ← ÚNICO ponto com LLM
  │  (Claude)    │     • temperature=0
  └──────┬───────┘     • tool_choice obrigatório
         │             • schema Pydantic rígido
         ▼             • retry com feedback de erro
   ServiceSpec
         │
         ▼
  ┌──────────────┐
  │   RENDERER   │  ← Jinja2, byte-for-byte determinístico
  │   (Jinja2)   │     mesmo spec → mesmo manifest (SHA-256)
  └──────┬───────┘
         ▼
     manifest.yaml
         │
         ▼
  ┌──────────────────────────────────┐
  │      VALIDATOR (3 estágios)      │
  │  1. YAML structural              │
  │  2. OPA / conftest policy        │
  │  3. kubectl diff allow-list      │
  └──────┬───────────────────────────┘
         ▼
  ┌──────────────┐
  │   GIT OPS    │  ← agente NUNCA toca o cluster
  │  (open PR)   │     ArgoCD/Flux faz o sync depois
  └──────┬───────┘
         ▼
    audit.jsonl  (append-only, immutable)
```

## Por que cada peça existe

| Componente   | Risco que mitiga                                | Mecanismo                                  |
|--------------|-------------------------------------------------|--------------------------------------------|
| Schema       | LLM inventar valores                            | enum, regex, range, `extra: forbid`        |
| temperature=0| Variação entre execuções                        | sampling determinístico                    |
| tool_choice  | LLM escrever prosa em vez do JSON               | API força a chamada da ferramenta          |
| Retry loop   | Falhas transitórias de schema                   | feedback de erro re-injetado no contexto   |
| Jinja2       | LLM gerar YAML torto                            | template é arquivo fixo, no Git            |
| OPA policy   | Desvio de padrões obrigatórios (security ctx…)  | conftest no CI                             |
| kubectl diff | Drift no que vai pro cluster                    | allow-list de campos permitidos no diff    |
| GitOps PR    | Mudança direta sem revisão                      | toda mudança vira commit revisável         |
| Audit log    | Falta de rastreabilidade                        | JSONL append-only com fingerprint SHA-256  |
| Eval suite   | Regressão silenciosa após mudar prompt/modelo   | golden cases checados a cada PR            |

## Setup

```bash
make install              # instala dependências dev
export ANTHROPIC_API_KEY=sk-...
make check                # lint + typecheck + testes + policy
```

## Uso

```bash
# Dry-run: renderiza e valida, mas não abre PR
make dry-run

# Run completo: extrai → renderiza → valida → abre PR
deploy-agent \
  "Deploy payment-api v1.2.3 to prod, team payments, \
   image payments/payment-api, 3 replicas, 1Gi memory, 500m CPU" \
  --repo /path/to/manifests-repo
```

Saída esperada:

```
Extracted spec (confidence=high): payment-api v1.2.3 -> prod
branch pushed: deploy/prod/payment-api-v1.2.3
title: deploy(prod): payment-api -> v1.2.3
fingerprint: 9c8a1e6b4f7d…  ← reproduzível
```

## Destroy / recreate idempotente

Como o spec vive no Git e o render é determinístico, recriar é:

```bash
# 1. Apaga
kubectl delete -f apps/prod/payment-api.yaml

# 2. Re-aplica o mesmo arquivo
kubectl apply -f apps/prod/payment-api.yaml

# 3. Verifica que o fingerprint bate
sha256sum apps/prod/payment-api.yaml
# deve ser idêntico ao registrado no commit que o gerou
```

Se você usa ArgoCD/Flux, o passo 2 é automático — basta deletar os
recursos no cluster e o controller reconcilia a partir do Git.

## Quando o agente DEVE falhar

Falha alta e ruidosa é melhor que sucesso silencioso e errado. O agente
falha (exit code ≠ 0) quando:

- LLM produz JSON fora do schema 3× seguidas → `exit 2`
- Manifest renderizado quebra YAML, policy ou drift check → `exit 3`
- Git push falha → exceção propaga

Nunca há fallback "criativo". Falha → humano olha.

## Estrutura

```
.
├── src/deploy_agent/
│   ├── schemas.py       # Pydantic + JSON schema p/ tool use
│   ├── extractor.py     # LLM com retry + validação
│   ├── renderer.py      # Jinja2 + fingerprint
│   ├── validator.py     # YAML + OPA + drift
│   ├── git_ops.py       # PR no repo de manifests
│   ├── audit.py         # Log append-only
│   └── __main__.py      # CLI
├── templates/kubernetes/
│   ├── deployment.yaml.j2
│   └── service.yaml.j2
├── policies/
│   └── deployment.rego  # Regras OPA não-negociáveis
├── evals/
│   ├── golden_cases.yaml
│   └── run_evals.py
├── tests/
│   ├── test_schemas.py
│   ├── test_renderer.py
│   └── test_validator.py
└── .github/workflows/
    └── ci.yaml          # test + policy + eval em todo PR
```

## Próximos passos sugeridos

- Trocar `gh pr create` por chamada direta à API do GitHub p/ abrir o PR
- Adicionar `cosign` para assinar o manifest antes do commit
- Integrar com Backstage / Port para o request virar uma UI
- Adicionar drift detection contínua (cronjob comparando cluster ↔ Git)
- Estender com mais templates: CronJob, StatefulSet, HPA
