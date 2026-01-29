all: format run

run:
	python -m main

format:
	python -m black *.py
