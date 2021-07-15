#!/bin/sh -e

cd "$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)"

if [ "$1" ]; then
  printf '%s\n' 'Format all Python with black and isort, and check mk scripts with shellcheck' 'Args: None' 1>&2
  exit 1
fi

if [ ! -d venv ]; then
  python3 -m venv venv
fi
# shellcheck disable=SC1091
. ./venv/bin/activate

pip install -U wheel
pip install -Ur dev-requirements.txt

black .
isort .

shellcheck mk/*.sh
