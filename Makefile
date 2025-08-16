SHELL=/bin/bash
PYTHON_VERSION=3.11

.PHONY: format
format: format-python

.PHONY: lint
lint: lint-python

.PHONY: format-python
format-python:
	linters/format-python.sh

.PHONY: lint-python
lint-python:
	@MYPYPATH=social linters/lint-python.sh

.PHONY: clear-logs
clear-logs:
	@mkdir -p logs
	@: > logs/celery_error.log
	@: > logs/celery_info.log
	@: > logs/all_error.log
	@: > logs/all_info.log
	@echo "Logs cleared"
