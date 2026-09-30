.PHONY: test check check-mcp check-controller check-integrations verify-rc verify-plugin-v1 verify-v1

PYTHON ?= python3

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

check:
	PYTHONPATH=src $(PYTHON) -m compileall -q src tests
	$(MAKE) test

check-mcp:
	$(PYTHON) -m compileall -q integrations/purposebus_mcp/src integrations/purposebus_mcp/tests
	$(PYTHON) -m unittest discover -s integrations/purposebus_mcp/tests -v

check-controller:
	$(PYTHON) -m compileall -q integrations/purposebus_codex_controller/src integrations/purposebus_codex_controller/tests
	$(PYTHON) -m unittest discover -s integrations/purposebus_codex_controller/tests -v

check-integrations: check-mcp check-controller

verify-rc:
	$(PYTHON) scripts/verify_rc_candidate.py

verify-plugin-v1:
	$(PYTHON) scripts/verify_plugin_v1_candidate.py

verify-v1:
	$(PYTHON) scripts/verify_v1_candidate.py
