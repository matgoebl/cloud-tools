#!/bin/bash
java -jar "$(dirname "${BASH_SOURCE[0]}")/.venv/avro-tools-1.11.3.jar" "$@"
