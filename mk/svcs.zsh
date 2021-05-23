#!/bin/zsh -fex

render () {  # <template-name> <json>
  emulate -L zsh -o errreturn
  local templates=$(git -C $0:P:h rev-parse --show-toplevel)/templates
  PYTHONPATH="$templates" wheezy.template -s "$templates" $@
}

render_svcs () {  # [-d dev|prod|<any>=dev] [SVCS_DIR=app/svcs]
  emulate -L zsh -o errreturn

  cd "$(git -C $0:P:h rev-parse --show-toplevel)"

  local yml svcs_dir deployment=dev
  if [[ $1 == -d ]] { deployment=$2; shift 2 }
  yml=vars.$deployment.yml
  svcs_dir=${1:-app/svcs}

  local name data src dest
  for name ( $(yaml-get -S -p svcs.name $yml) ) {
    if [[ ${$(yaml-get -S -p "svcs[name == $name].enabled" $yml):l} == false ]] continue
    print -ru2 -- '***' Generating $svcs_dir/$name '<-' $yml '***'

    mkdir -p $svcs_dir/$name/log

    data=$(yaml-merge -S -m svc =(<<<'{"svc": {}}') =(yaml-get -S -p "svcs[name == $name]" $yml))

    for src dest (
      svc.run.wz     "$svcs_dir/$name/run"
      svc.finish.wz  "$svcs_dir/$name/finish"
      svc.log.run.wz "$svcs_dir/$name/log/run"
    ) {
      render $src =(<<<$data) >"$dest"
      chmod 0700 $dest
    }

    for dest ( ${(f)"$(yaml-get -S -p "svcs[name == $name].sops_templates.dest" $yml 2>/dev/null)"} ) {
      print -ru2 -- '***' Generating $dest '<-' app/sops/$name.$deployment.yml '***'

      src=$(yaml-get -S -p "svcs[name == $name].sops_templates[dest == $dest].src" $yml)
      data=$(yaml-merge -S $yml =(sops -d app/sops/$name.$deployment.yml) -D json)

      render $src =(<<<$data) >"$dest"

      if [[ $dest:a:h:t == sops ]] sops -e -i $dest
    }
  }
}


render_svcs $@
