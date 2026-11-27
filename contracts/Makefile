PYTHON ?= python
AGAINST ?=

.PHONY: check test

check:
	$(PYTHON) contract_check.py .$(if $(AGAINST),--against$(AGAINST),)

test:
	$(PYTHON) -m pytest tests/test_contract_check.py -v