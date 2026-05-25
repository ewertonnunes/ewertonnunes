.PHONY: install test test-core test-examples lint typecheck check clean regenerate-examples verify-examples

install:
	pip install -e ".[dev]"

test: test-core test-examples

test-core:
	pytest tests/test_core.py -v

test-examples:
	pytest tests/test_examples_reproduce.py -v

lint:
	ruff check src tests

typecheck:
	mypy src

check: lint typecheck test

regenerate-examples:
	@for ex in examples/*/; do \
		echo "▶ $$ex"; \
		( cd $$ex && spec-codegen generate \
			--spec spec.yaml \
			--schema spec_schema.py:ProjectSpec \
			--files files \
			--out /tmp/$$(basename $$ex)-out \
			--write-lockfile \
			--lockfile lockfile.json ); \
	done

verify-examples:
	@for ex in examples/*/; do \
		echo "▶ $$ex"; \
		( cd $$ex && spec-codegen verify \
			--spec spec.yaml \
			--schema spec_schema.py:ProjectSpec \
			--files files \
			--lockfile lockfile.json ); \
	done

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache *.egg-info build dist
