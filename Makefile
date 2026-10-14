BIN_NAME := things-cli
BINDIR ?= $(HOME)/.local/bin

.PHONY: build install uninstall test vet fmt package

build:
	go build -trimpath -o ./bin/$(BIN_NAME) ./cmd/things

install:
	mkdir -p "$(BINDIR)"
	go build -trimpath -o "$(BINDIR)/$(BIN_NAME)" ./cmd/things
	install -m 0755 "$(BINDIR)/$(BIN_NAME)" "$(BINDIR)/things"
	@echo "Installed $(BIN_NAME) to $(BINDIR)/$(BIN_NAME)"
	@echo "Run: $(BIN_NAME) --help"

uninstall:
	rm -f "$(BINDIR)/$(BIN_NAME)" "$(BINDIR)/things"
	@echo "Removed $(BINDIR)/$(BIN_NAME)"

test:
	go test ./...
	PYTHONPATH=internal/cloud/runtime python3 -m unittest discover -s internal/cloud/tests -v
	python3 -m unittest discover -s tests -v

package:
	python3 scripts/package.py

vet:
	go vet ./...

fmt:
	gofmt -w $$(rg --files -g '*.go')

