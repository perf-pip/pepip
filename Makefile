PYTHON ?= python3
SOURCE_DIRS := pepip tests eval scripts

.PHONY: format format-check lint test test-cli test-installer quality

format:
	$(PYTHON) -m isort $(SOURCE_DIRS)
	$(PYTHON) -m black $(SOURCE_DIRS)

format-check:
	$(PYTHON) -m isort --check-only $(SOURCE_DIRS)
	$(PYTHON) -m black --check $(SOURCE_DIRS)

lint:
	$(PYTHON) -m ruff check $(SOURCE_DIRS)
	$(PYTHON) -m black --check $(SOURCE_DIRS)
	$(PYTHON) -m isort --check-only $(SOURCE_DIRS)
	$(PYTHON) -m mypy $(SOURCE_DIRS)
	$(PYTHON) -m flake8 --jobs=1 $(SOURCE_DIRS)
	PYLINTHOME=/tmp/pylint-cache $(PYTHON) -m pylint $(SOURCE_DIRS)

quality: format lint format-check

test:
	$(PYTHON) -m pytest
