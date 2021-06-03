#!/bin/sh -ex

root="$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)"

for folder in "$root" "$root/app"; do

  cd "$folder"

  if [ ! -d venv ]; then
    python3 -m venv venv
  fi
  . ./venv/bin/activate

  pip install -U pip-tools

  for reqsin in *requirements.in; do
    pip-compile -U --no-header "$reqsin"
  done

done
