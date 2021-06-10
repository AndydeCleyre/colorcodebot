#!/bin/sh -e
# [-d <deployment>=dev]

deployment=dev
if [ "$1" = -d ]; then deployment=$2; shift 2; fi

if [ "$1" ]; then
  printf '%s\n' 'Start the bot locally, without process supervision' 'Args: [-d <deployment>=dev]'
  exit 1
fi

cd "$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)"

if [ ! "$VIRTUAL_ENV" ]; then
  if [ ! -d app/venv ]; then
    python3 -m venv app/venv
  fi
  # shellcheck disable=SC1091
  . app/venv/bin/activate
  pip install -r app/requirements.txt
fi

exec sops exec-env "app/sops/colorcodebot.${deployment}.yml" \
app/colorcodebot.py
