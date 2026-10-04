UV ?= uv
PYTHON_VERSION ?= $(shell cat .python-version)

.PHONY: install-dev frontend-install frontend-check web-dist-check lint format typecheck clean lock-check hygiene-check architecture-check build-check release-check ci

install-dev:
	$(UV) sync --all-extras
	cd frontend && npm ci

frontend-install:
	cd frontend && npm ci

frontend-check:
	cd frontend && npm run build

# The packaged bundle is committed; fail when src/folionym/web_dist differs from a fresh build.
web-dist-check:
	cd frontend && npm run build
	@test -z "$$(git status --porcelain -- src/folionym/web_dist)" || { \
		git status --short -- src/folionym/web_dist; \
		echo "src/folionym/web_dist is stale: rebuild with 'cd frontend && npm run build' and commit it."; \
		exit 1; }

lint:
	$(UV) run ruff format --check .
	$(UV) run ruff check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy src/folionym/ scripts/

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache .cache
	rm -rf .coverage .coverage.* coverage.xml coverage htmlcov
	rm -rf build dist
	rm -rf frontend/node_modules
	rm -rf src/folionym.egg-info *.egg-info
	find src scripts -type d -name '__pycache__' -prune -exec rm -rf {} +
	find src scripts -type d -name '.pytest_cache' -prune -exec rm -rf {} +
	find . -name '.DS_Store' -delete

hygiene-check:
	git ls-files -z | $(UV) run python scripts/repository_hygiene.py --null-stdin

architecture-check:
	$(UV) run python scripts/check_architecture.py

lock-check:
	$(UV) lock --check

build-check:
	rm -rf dist
	$(UV) build --out-dir dist
	@set -eu; \
	ENV_DIR=$$(mktemp -d); \
	trap 'rm -rf "$$ENV_DIR"' EXIT; \
	set -- dist/*.whl; \
	[ "$$#" -eq 1 ]; \
	WHEEL=$$1; \
	PYTHON=$$($(UV) python find $(PYTHON_VERSION)); \
	$(UV) venv --no-project --python "$$PYTHON" "$$ENV_DIR"; \
	$(UV) pip install --python "$$ENV_DIR/bin/python" "$${WHEEL}[pdf,tokens,ocr,tui,web]"; \
	"$$ENV_DIR/bin/python" scripts/verify_distributions.py dist --installed-wheel

release-check: lock-check frontend-check hygiene-check architecture-check lint typecheck build-check

# Everything the CI release job runs.
ci: release-check web-dist-check
