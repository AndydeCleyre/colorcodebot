#!/bin/sh -e

root="$(git -C "$(dirname -- "$0")" rev-parse --show-toplevel)"

if [ "$1" ]; then
  printf '%s\n' 'Upgrade what we can in our *requirements.txt files' 'Args: None' 1>&2
  exit 1
fi

for folder in "$root" "$root/app"; do

  cd "$folder"

  if [ ! -d venv ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  . ./venv/bin/activate

  pip install -U pip-tools

  for reqsin in *requirements.in; do
    pip-compile -U --no-header "$reqsin"
  done

done
