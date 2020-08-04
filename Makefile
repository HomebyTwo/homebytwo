.DEFAULT_GOAL := help

REQUIREMENTS_DIR = requirements
ENV = staging
objects = $(REQUIREMENTS_DIR)/base.txt $(REQUIREMENTS_DIR)/dev.txt $(REQUIREMENTS_DIR)/test.txt

requirements/%.txt: $(REQUIREMENTS_DIR)/%.in $(REQUIREMENTS_DIR)/base.in
	pip-compile $<

.PHONY: requirements
requirements: $(objects) ## Compile requirements with pip-compile
	pip install -r requirements/dev.txt

.PHONY: upgrade-requirements
upgrade-requirements: ## Upgrade and compile requirements with pip-compile --upgrade
	for file in $(REQUIREMENTS_DIR)/*.in; do \
		pip-compile --upgrade $$file; \
	done

.PHONY: sync-requirements
sync-requirements:
	pip-sync $(objects)

.PHONY: translations
translations: ## Regenerate .po files with ./manage.py makemessages
	./manage.py makemessages -a -i "requirements/*" -i "virtualization/*" -i "node_modules/*"

.PHONY: compile-translations
compile-translations: ## Compile .po files with ./manage.py compilemessages
	./manage.py compilemessages

.PHONY: help
help: ## Display this help
	@grep -E '^[.a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort -k 1,1 | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
