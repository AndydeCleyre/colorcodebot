#!/bin/sh -e
# [-d <deployment>=dev] [--fast]

deployment=dev
if [ "$1" = -d ]; then deployment=$2; shift 2; fi

fast=''
if [ "$1" = --fast ]; then fast=1; shift; fi

if [ "$1" ]; then
  printf '%s\n' 'Start the bot locally, without process supervision or other svcs' 'Args: [-d <deployment>=dev]'
  exit 1
fi

cd "$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)"

if [ ! $fast ]; then
  ./mk/reqs.sh
  ./mk/file_ids.sh -d "$deployment" || true
fi

if [ ! -d app/venv ]; then
  python3 -m venv app/venv
fi
# shellcheck disable=SC1091
. app/venv/bin/activate

if [ ! $fast ]; then
  pip install -U pip wheel

  pip install -r app/requirements.txt
  if [ -r "app/${deployment}-requirements.txt" ]; then
    pip install -r "app/${deployment}-requirements.txt"
  fi
fi

exec sops exec-env "app/sops/colorcodebot.${deployment}.yml" \
app/colorcodebot.py
