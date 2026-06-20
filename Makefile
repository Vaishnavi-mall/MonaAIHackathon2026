.PHONY: install run test

install:
	pip install -r requirements.txt

run:
	uvicorn frontend.server:app --reload --port 8000

test:
	pytest agents/ -v
