.DEFAULT_GOAL := help

.PHONY: help validate new-app networks fmt deploy backup restore

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

validate: ## Validate everything (compose, yaml, shell, secrets)
	@./scripts/validate.sh

new-app: ## Scaffold a stack: make new-app NODE=apps APP=sonarr CAT=arr
	@./scripts/new-app.sh $(NODE) $(APP) $(CAT)

networks: ## Create shared docker networks on this host
	@./scripts/create-networks.sh

config: ## Generate every stack's .env from the root .env
	@./scripts/gen-env.sh

config-check: ## Verify all stack .env files exist with no unset secrets
	@./scripts/gen-env.sh --check

deploy: ## Deploy all stacks for a node: make deploy NODE=infra [SKIP="diun caddy"]
	@./scripts/deploy-node.sh $(NODE) $(if $(SKIP),--skip "$(SKIP)")

backup: ## Back up this node to restic: make backup [STOP=1] [CHECK=1]
	@sudo ./scripts/backup.sh $(if $(STOP),--stop) $(if $(CHECK),--check)

restore: ## Restore from restic: make restore [SNAP=latest] [TARGET=/tmp/r]
	@sudo ./scripts/restore.sh $(or $(SNAP),snapshots) $(if $(TARGET),--target $(TARGET))

fmt: ## Format shell scripts (shfmt -i 4)
	@shfmt -i 4 -w $$(find scripts stacks -name '*.sh')
