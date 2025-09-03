#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

run: black ./custom_components/
