# Bundled Things Cloud package

This directory contains the dependency-free `things-cloud-plugin` Python package
version 0.1.0 developed for this integration. The Go bridge embeds it verbatim,
extracts it into a private temporary directory, and launches its CLI or stdio
MCP transport with isolated Python. No second cloud protocol is implemented in Go.

The Python service synchronizes task reads and writes on demand, validates
ordinary Task7 changes, and reads accepted writes back from cloud history.
MCP calls always synchronize connected accounts, including status; CLI offline
reads are explicit. Repeating tasks remain read-only.

Keep the Python package and its tests together when updating this snapshot.
The accompanying LICENSE and THIRD_PARTY_NOTICES.md cover this embedded code.
