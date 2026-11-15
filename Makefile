.PHONY: build test lint format-check check hooks clean

build: ## build the sdist and wheel into dist/
	uv build

test: ## run the tests with coverage
	uv run pytest --cov --cov-report=term-missing

lint: ## ruff lint (includes the bandit security rules)
	uv run ruff check .

format-check: ## fail if code is not ruff-formatted
	uv run ruff format --check .

check: lint format-check test ## everything CI runs for code quality

hooks: ## once per clone: DCO sign-off, Conventional Commits check, secret scan on push
	git config core.hooksPath .githooks
	@echo "hooks enabled (prepare-commit-msg, commit-msg, pre-push); the pre-push scan needs gitleaks: brew install gitleaks"

clean:
	rm -rf dist build .pytest_cache .ruff_cache .coverage htmlcov
