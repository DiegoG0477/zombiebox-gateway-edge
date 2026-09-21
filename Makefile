
.PHONY: format format-check
format:
	python3 scripts/format.py
format-check:
	python3 scripts/format.py --check

.PHONY: deps deps-check check install
deps:
	python3 scripts/dependencies.py fetch gateway-core
deps-check:
	python3 scripts/dependencies.py check gateway-core
check:
	for script in install.sh install-termux.sh install-services.sh install-youtube-receiver.sh install-airplay-experimental.sh edge.sh runtime/*.sh; do bash -n "$$script"; done
	python3 -m unittest discover -s tests
install: deps-check
	bash install-termux.sh
