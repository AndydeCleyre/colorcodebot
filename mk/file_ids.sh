#!/bin/sh -e
# [-d <deployment>=dev] [<dest>=app/theme_previews.yml]

repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)

deployment=dev
if [ "$1" = -d ]; then
  deployment=$2
  shift 2
fi

dest="$repo/app/theme_previews.yml"
if [ "$1" ]; then
  if [ "$1" = -h ] || [ "$1" = --help ]; then
    printf '%s\n' \
      'Generate theme_previews.yml, with data from vars.<deployment>.yml' \
      'Args: [-d <deployment>=dev] [<dest>=app/theme_previews.yml]' >&2
    exit 1
  fi
  dest="$(realpath "$1")"
  shift
fi

cd "$repo"
if [ ! "$VIRTUAL_ENV" ]; then
  if [ ! -d venv ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  . ./venv/bin/activate
fi
pip install -r dev-requirements.txt

yaml-get -S -p theme_previews "vars.$deployment.yml" >/dev/null 2>&1

wheezy.template -s templates app.theme_previews.yml.wz \
  "$(yaml-get -S -p . "vars.$deployment.yml")" \
  >"$dest"
