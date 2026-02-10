.ONESHELL:

format:
	uv run ruff format src

install:
	uv sync --all-extras

clear:
	clear

r: clear
	uv run python -m kaito.rich

t: clear
	uv run python -m kaito.textual
