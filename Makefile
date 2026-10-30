.PHONY: up down reset test e2e logs

up:      ## Start everything (regtest, one command)
	docker compose up --build -d
	@echo "Boutik → http://localhost:$${BOUTIK_PORT:-8000}  (PIN 1234)"

down:
	docker compose down

reset:   ## Wipe the regtest chain, nodes and shop data
	docker compose down -v

test:    ## Unit + API tests (fake LND)
	cd app && python -m pytest -q

e2e:     ## Happy path against the running stack (real LND)
	./scripts/e2e.sh

logs:
	docker compose logs -f app bootstrap
