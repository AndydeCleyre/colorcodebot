#!/bin/sh -ex
# [<deployment>=dev]

#######################
### Configure Build ###
#######################

appname='colorcodebot'
version='0.2.7'
base_img='docker.io/library/alpine:3.13'
deployment=$1

ctnr=${appname}-alpine
img=quay.io/andykluger/$ctnr
user=$appname
today=$(date +%Y.%j)

tz="America/New_York"

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

alias ctnr_mkuser="ctnr_run adduser -D"

alias ctnr_pkg="ctnr_run apk -q --no-progress"
alias ctnr_pkg_upgrade="ctnr_pkg upgrade"
alias ctnr_pkg_add="ctnr_pkg add"
alias ctnr_pkg_del="ctnr_pkg del --purge -r"

repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)

pkgs='ca-certificates execline fontconfig jpeg python3 s6'
build_pkgs='tzdata freetype-dev gcc jpeg-dev musl-dev py3-pip py3-wheel python3-dev tar zstd'
# fat='/var/cache/apk/* /tmp/* /usr/lib/python3.*/__pycache__ /home/colorcodebot/.cache'
fat='/var/cache/apk/* /tmp/* /usr/lib/python3.*/__pycache__'

#############
### Build ###
#############

# Start fresh, or from a daily "jumpstart" image if available
buildah rm $ctnr 2>/dev/null || true
if ! buildah from -q --name "$ctnr" "$img-jumpstart:$today" 2>/dev/null; then
  buildah from -q --name "$ctnr" "$base_img"
  make_jumpstart_img=1
fi

# Upgrade and install packages
ctnr_pkg_upgrade
ctnr_pkg_add $pkgs $build_pkgs

# Save this stage as a daily "jumpstart" image
if [ $make_jumpstart_img ]; then
  buildah commit -q --rm "$ctnr" "$img-jumpstart:$today"
  buildah from -q --name "$ctnr" "$img-jumpstart:$today"
fi

# Set the timezone
ctnr_run cp /usr/share/zoneinfo/$tz /etc/localtime
printf '%s\n' "$tz" | ctnr_append /etc/timezone

# Add user
ctnr_mkuser $user

# Copy app and svcs into container
tmp=$(mktemp -d)
git -C "$repo" archive "HEAD:$repo/app" >"$tmp/app.tar"
ctnr_fetch -u "$tmp/app.tar" /home/$user
"$repo/mk/svcs.zsh" -d "$deployment" "$tmp/svcs"
ctnr_fetch "$tmp/svcs" /var/svcs
rm -rf "$tmp"

# Install python modules
ctnr_run -u pip install -Ur /home/$user/requirements.txt
# Patch pygments:
# pyver='3.8'
# bldr sed -i 's/background-color: #f0f0f0; //g' /usr/lib/python$pyver/site-packages/pygments/formatters/html.py

# Install fonts
ctnr_fetch \
  'https://github.com/AndydeCleyre/archbuilder_iosevka/releases/download/https-aur/ttf-iosevka-term-custom-git-1619959084-1-any.pkg.tar.zst' \
  /tmp
ctnr_run tar xf \
  /tmp/ttf-iosevka-term-custom-git-1619959084-1-any.pkg.tar.zst \
  -C / \
  usr/share/fonts/TTF/iosevka-term-custom-{regular,italic,bold}.ttf

# Install papertrail agent
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
if [ -n "$fat" ]; then
  ctnr_run sh -c "rm -rf $fat"
fi

# Set default command
buildah config --cmd "s6-svscan /var/svcs" $ctnr

# Press container as image
buildah rmi "$img:$today" "$img:latest" "$img:$version" 2>/dev/null || true
buildah tag "$(buildah commit -q --rm "$ctnr" "$img:$today")" "$img:latest" "$img:$version"

printf '%s\n' \
  ">>> To deploy, you'll need to add or mount your age encryption keys as /root/.config/sops/keys.txt"
