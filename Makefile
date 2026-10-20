.PHONY: setup data test lint run

setup:
	pip install -r requirements.txt && pip install -e .

data:
	python scripts/make_presets.py

test:
	pytest --cov=src/schoolsim --cov-report=term-missing

lint:
	ruff check .

run:
	streamlit run app/streamlit_app.py