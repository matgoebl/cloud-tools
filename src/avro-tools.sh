#!/bin/bash
java -jar "$(dirname "${BASH_SOURCE[0]}")/.venv/avro-tools-1.12.1.jar" "$@"
