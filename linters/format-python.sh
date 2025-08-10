#!/usr/bin/env sh

set -e

linters/find-python.sh black -t py311 --line-length 88
linters/find-python.sh isort
