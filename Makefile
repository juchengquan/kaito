.ONESHELL:

format:
	uv run ruff format src

install:
	uv sync --all-extras

run:
	uv run python -m kaito.main
