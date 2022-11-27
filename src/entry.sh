#!/bin/sh
. .venv/bin/activate
./kafka-client.py --help
read -p 'press enter to exit...' dummy
