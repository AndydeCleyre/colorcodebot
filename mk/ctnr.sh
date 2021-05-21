#!/bin/sh -ex
# [-d <deployment>=dev]

#######################
### Configure Build ###
#######################

deployment=dev
if [ "$1" = -d ]; then
  deployment=$2
  shift 2
fi

if [ "$1" ] && [ "$1" != --push ]; then
  printf '%s\n' 'Args: [-d <deployment>=dev]'
  exit 1
fi

repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
version=$(git -C "$repo" describe)
branch=$(git -C "$repo" branch --show-current)

appname=colorcodebot
img=quay.io/andykluger/${appname}-${deployment}-alpine
ctnr=${img}-building

user=$appname
svcs_dir=/home/$user/svcs

sops_ver=3.7.1
today=$(date +%Y.%j)
tz="America/New_York"

base_img='docker.io/library/alpine:3.13'
pkgs='ca-certificates execline fontconfig jpeg python3 s6'
build_pkgs='tzdata freetype-dev gcc jpeg-dev musl-dev python3-dev tar zstd'
fat="/tmp/* /usr/lib/python3.*/__pycache__ /home/$user/.cache /root/.cache /home/$user/.local/bin /root/.local/bin /var/cache/apk/*"

#################
### Functions ###
#################

ctnr_run () {  # [-u] <cmd> [<cmd-arg>...]
  _u=root
  if [ "$1" = -u ]; then _u=$user; shift; fi
  buildah run --user $_u "$ctnr" "$@"
}

ctnr_fetch () {  # [-u] <src-url-or-path> <dest-path>
  _u=root
  if [ "$1" = -u ]; then _u=$user; shift; fi
  buildah add --chown $_u "$ctnr" "$@"
}

ctnr_append () {  # [-u] <dest-path>
  unset _u
  if [ "$1" = -u ]; then _u=-u; shift; fi
  ctnr_run $_u sh -c "cat >>$1"
}

alias ctnr_pkg="ctnr_run apk -q --no-progress"
alias ctnr_pkg_upgrade="ctnr_pkg upgrade"
alias ctnr_pkg_add="ctnr_pkg add"
alias ctnr_pkg_del="ctnr_pkg del --purge -r"
alias ctnr_mkuser="ctnr_run adduser -D"

#############
### Build ###
#############

# Start fresh, or from a daily "jumpstart" image if available
buildah rm "$ctnr" 2>/dev/null || true
if ! buildah from -q --name "$ctnr" "$img-jumpstart:$today" 2>/dev/null; then
  buildah from -q --name "$ctnr" "$base_img"
  make_jumpstart_img=1
fi

# Upgrade and install packages
ctnr_pkg_upgrade
ctnr_pkg_add $pkgs $build_pkgs

# Set the timezone
ctnr_run cp /usr/share/zoneinfo/$tz /etc/localtime
printf '%s\n' "$tz" | ctnr_append /etc/timezone

# Add user
ctnr_mkuser $user || true

# Copy app and svcs into container
ctnr_run rm -rf "$svcs_dir"
ctnr_run sh -c "rm -rf /home/$user/*"
tmp=$(mktemp -d)
git -C "$repo" archive HEAD:app >"$tmp/app.tar"
ctnr_fetch -u "$tmp/app.tar" /home/$user
zsh -fe "$repo/mk/svcs.zsh" -d "$deployment" "$tmp/svcs"
ctnr_fetch "$tmp/svcs" "$svcs_dir"
rm -rf "$tmp"

# Install python modules
ctnr_run -u python3 -m venv /home/$user/venv
ctnr_run /home/$user/venv/bin/pip install -U wheel
ctnr_run /home/$user/venv/bin/pip install -Ur /home/$user/requirements.txt
ctnr_run /home/$user/venv/bin/pip uninstall -y wheel

# Save this stage as a daily "jumpstart" image
if [ $make_jumpstart_img ]; then
  ctnr_pkg_del $build_pkgs
  ctnr_run sh -c "rm -rf $fat"
  buildah commit -q --rm "$ctnr" "$img-jumpstart:$today"
  buildah from -q --name "$ctnr" "$img-jumpstart:$today"
  ctnr_pkg_upgrade
  ctnr_pkg_add $pkgs $build_pkgs
fi

# Install fonts
ctnr_fetch \
  'https://github.com/AndydeCleyre/archbuilder_iosevka/releases/download/https-aur/ttf-iosevka-term-custom-git-1619959084-1-any.pkg.tar.zst' \
  /tmp
ctnr_run tar xf \
  /tmp/ttf-iosevka-term-custom-git-1619959084-1-any.pkg.tar.zst \
  -C / --wildcards --wildcards-match-slash \
  '*-regular.ttf' '*-italic.ttf' '*-bold.ttf' '*-bolditalic.ttf'

# Install sops
ctnr_fetch \
  "https://github.com/mozilla/sops/releases/download/v${sops_ver}/sops-v${sops_ver}.linux" \
  /usr/local/bin/sops
ctnr_run chmod 0555 /usr/local/bin/sops
ctnr_run mkdir -p /root/.config/sops

# Install papertrail agent, if enabled
if [ "$(yaml-get -p 'svcs[name == papertrail].enabled' "$repo/vars.$deployment.yml")" = True ]; then
  ctnr_fetch \
    'https://github.com/papertrail/remote_syslog2/releases/download/v0.20/remote_syslog_linux_amd64.tar.gz' \
    /tmp
  ctnr_run tar xf \
    /tmp/remote_syslog_linux_amd64.tar.gz \
    -C /usr/local/bin \
    remote_syslog/remote_syslog \
    --strip-components 1
fi

###############
### Package ###
###############

# Cut the fat:
ctnr_pkg_del $build_pkgs
ctnr_run sh -c "rm -rf $fat"

# Set default command
buildah config --cmd "s6-svscan $svcs_dir" "$ctnr"

# Press container as image
buildah rmi "$img:$today" "$img:latest" "$img:$version" 2>/dev/null || true
buildah tag "$(buildah commit -q --rm "$ctnr" "$img:latest")" "$img:$today" "$img:$version" "$img:$branch"

printf '%s\n' '' \
  '###################' \
  "### BUILT IMAGE ###" \
  '###################' '' \
  ">>> To decrypt credentials, you'll need to add or mount your age encryption keys as /root/.config/sops/age/keys.txt" \
  ">>> For the internal process supervision to work, you'll need to unmask /sys/fs/cgroup" \
  ">>> e.g.:" '' \
  "  podman run -v ~/.config/sops/age/keys.txt:/root/.config/sops/age/keys.txt:ro --security-opt unmask=/sys/fs/cgroup $img" ''

if [ "$1" = --push ]; then
  podman push "$img:latest"
  podman push "$img:$today"
  podman push "$img:$version"
  podman push "$img:$branch"
fi
