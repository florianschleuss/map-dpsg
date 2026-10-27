#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
docker compose --profile tools run --rm -T test
