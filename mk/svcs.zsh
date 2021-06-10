#!/bin/zsh -fe

# Render template, by name, to stdout
render () {  # <template-name> <json>
  emulate -L zsh -o errreturn

  local templates=$(git -C $0:P:h rev-parse --show-toplevel)/templates

  PYTHONPATH="$templates" wheezy.template -s "$templates" $@
}

# Generate s6 svcs dir, with enabled svcs from vars.<deployment>.yml
render_svcs () {  # [-d <deployment>=dev] [<svcs-dir>=app/svcs]
  emulate -L zsh -o errreturn

  if [[ $1 =~ '^-(h|-help)$' ]] {
    print -rlu2 \
      'Generate svcs dir, with enabled svcs from vars.<deployment>.yml' \
      'Args: [-d <deployment>=dev] [<svcs-dir>=app/svcs]'
    return 1
  }

  cd "$(git -C $0:P:h rev-parse --show-toplevel)"

  # Parse args
  local deployment=dev yml svcs_dir
  if [[ $1 == -d ]] { deployment=$2; shift 2 }
  yml=vars.$deployment.yml
  svcs_dir=${1:-app/svcs}

  # Backup existing svcs dir
  if [[ -e "$svcs_dir" ]] {
    local backup_base="$svcs_dir.$(date +%Y.%j)"
    local backup=$backup_base
    local -i counter=1
    while [[ -e "$backup" ]] {
      backup="${backup_base}.${counter}"
      (( counter++ ))
    }
    print -ru2 "Moving existing destination $svcs_dir to $backup"
    mv "$svcs_dir" "$backup"
  }

  # For each defined svc...
  local name data src dest
  for name ( $(yaml-get -S -p svcs.name $yml) ) {

    # Skip if disabled
    if [[ ${$(yaml-get -S -p "svcs[name == $name].enabled" $yml):l} == false ]] continue

    print -ru2 '***' Generating $svcs_dir/$name '<-' $yml '***'

    # Collect the current svc's variables, as {"svc": {...}}
    data=$(yaml-merge -S -m svc =(<<<'{"svc": {}}') =(yaml-get -S -p "svcs[name == $name]" $yml))

    # Render the svc definition
    mkdir -p $svcs_dir/$name/log
    for src dest (
      svc.run.wz     "$svcs_dir/$name/run"
      svc.finish.wz  "$svcs_dir/$name/finish"
      svc.log.run.wz "$svcs_dir/$name/log/run"
    ) {
      render $src =(<<<$data) >"$dest"
      chmod 0700 $dest
    }

    # Install any needed encrypted yml files to the svcdir
    for dest ( ${(f)"$(yaml-get -S -p "svcs[name == $name].sops_templates.dest" $yml 2>/dev/null)"} ) {
      print -ru2 -- '***' Generating "$svcs_dir/$name/$dest" '<-' app/sops/$name.$deployment.yml '***'

      src=$(yaml-get -S -p "svcs[name == $name].sops_templates[dest == $dest].src" $yml)
      data=$(yaml-merge -S $yml =(sops -d app/sops/$name.$deployment.yml) -D json)

      render $src =(<<<$data) >"$svcs_dir/$name/$dest"

      sops -e -i "$svcs_dir/$name/$dest"
    }
  }
}


render_svcs $@
