.PHONY: data sample-data dev

data:
	python3 scripts/build_real_scenarios.py
	python3 scripts/sync_public_data.py

sample-data:
	python3 scripts/build_sample_scenarios.py
	python3 scripts/sync_public_data.py

dev:
	python3 backend/server.py
