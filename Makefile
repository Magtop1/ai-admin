.PHONY: run test seed lint
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
test:
	pytest -q
seed:
	python3 scripts/seed.py
