# Makefile for running and managing the scheduler cron job

VENV_PATH := /absolute/path/to/your/venv
SCRIPT_PATH := /absolute/path/to/well/backend/app/scripts/run_scheduler.sh
LOG_PATH := /logs/db_injections.log

.PHONY: run-scheduler add-cron remove-cron show-cron

run-scheduler:
	@echo "Running scheduler now..."
	@source $(VENV_PATH)/bin/activate && python3 app/scripts/scheduler.py

add-cron:
	@echo "Adding cron job..."
	@(crontab -l 2>/dev/null; echo "*/10 * * * * /bin/bash $(SCRIPT_PATH) >> $(LOG_PATH) 2>&1") | crontab -

remove-cron:
	@echo "Removing all matching cron jobs..."
	@crontab -l | grep -v '$(SCRIPT_PATH)' | crontab -

show-cron:
	@echo "Current cron jobs:"
	@crontab -l
