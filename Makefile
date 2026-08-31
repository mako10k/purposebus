.PHONY: test check

PYTHON ?= python3

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

check:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests
	$(MAKE) test
