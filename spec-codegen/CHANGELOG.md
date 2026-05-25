# Changelog

## 1.0.0 (2026-05-25)

Initial release.

### Features

- Deterministic project generation from spec.yaml + Pydantic schema + Jinja templates
- Byte-stable lockfile (SHA-256 per file) for reproducibility verification
- Path templating: `{{ var }}` in directory/file names
- `.tmpl` convention separates generator templates from runtime `.j2` templates
- `.keep` markers for empty directory preservation
- `pynum` Jinja filter resolves `int`-vs-`float` byte drift
- CLI: `spec-codegen generate` / `spec-codegen verify`
- Three working examples: Go service, Java service, Python LLM agent

### Verified reproducibility

| Example | Files | Aggregate hash |
|---|---|---|
| deploy-agent | 23 | e1d1ab82d293e30f6bfd2aabd12d75d6a06302c3443d93aa7f55374af96d2290 |
| java-service | 8 | b672d88c5158fdda1dfd3b4cc027733ad04b1ebc3e20d4c7c2176a3b40fb5ee5 |
| go-service | 8 | 8da306bd021a594fb8be46d0e8dbd3a40146c7208e32b24ec618ad33dcb78729 |
