BIN_NAME := things
BINDIR ?= $(HOME)/.local/bin

.PHONY: build install uninstall test vet fmt

build:
	go build -trimpath -o ./bin/$(BIN_NAME) ./cmd/things

install:
	mkdir -p "$(BINDIR)"
	go build -trimpath -o "$(BINDIR)/$(BIN_NAME)" ./cmd/things
	@echo "Installed $(BIN_NAME) to $(BINDIR)/$(BIN_NAME)"
	@echo "Run: $(BIN_NAME) --help"

uninstall:
	rm -f "$(BINDIR)/$(BIN_NAME)"
	@echo "Removed $(BINDIR)/$(BIN_NAME)"

test:
	go test ./...

vet:
	go vet ./...

fmt:
	gofmt -w $$(rg --files -g '*.go')

