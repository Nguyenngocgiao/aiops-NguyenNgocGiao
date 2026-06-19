.PHONY: install run test clean

install:
	uv pip install -r requirements.txt

run:
	uvicorn serve:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 4 --no-access-log

test:
	pytest -v tests/

clean:
	find . -name "__pycache__" -exec rm -rf {} +
	rm -f rca_llm_trace.log
