.PHONY: test lint

test:
	python3 -m pytest --cov=ecli --cov-report=term-missing

lint:
	ruff check ecli tests
	mypy ecli tests
