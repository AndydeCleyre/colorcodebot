#!/bin/sh -e
# [-d <deployment>=dev] [--push] [-r <registry-user>=quay.io/andykluger]

if [ "$1" = -h ] || [ "$1" = --help ]; then
  printf '%s\n' \
    'Build a container image' \
    'Args: [-d <deployment>=dev] [--push] [-r <registry-user>=quay.io/andykluger]' \
    1>&2
  exit 1
fi

#######################
### Configure Build ###
#######################

deployment=dev
registry_user=quay.io/andykluger
unset do_push
while [ "$1" = -d ] || [ "$1" = --push ] || [ "$1" = -r ]; do
  if [ "$1" = -d ];     then deployment=$2;    shift 2; fi
  if [ "$1" = -r ];     then registry_user=$2; shift 2; fi
  if [ "$1" = --push ]; then do_push=1;        shift;   fi
done

repo=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
set -x
version=$(git -C "$repo" describe)
branch=$(git -C "$repo" branch --show-current | sed 's/[^[:alnum:]\.\_\-]/_/g')
set +x

appname=colorcodebot
img=${registry_user}/${appname}-${deployment}-archlinux
ctnr=${img}-building

user=$appname
svcs_dir=/home/$user/svcs

iosevka_pkg='https://github.com/AndydeCleyre/archbuilder_iosevka/releases/download/ccb-straight-quote/ttf-iosevka-term-custom-git-1627380286-1-any.pkg.tar.zst'
today=$(date +%Y.%j)
tz="America/New_York"

base_img='docker.io/library/archlinux:base'
pkgs='cairo fontconfig graphicsmagick highlight pango python sops ttf-joypixels ttf-nerd-fonts-symbols-mono'
aur_pkgs='s6 ttf-code2000 ttf-nanumgothic_coding ttf-unifont'
build_pkgs='git'
build_groups='base-devel'
gpg_keys='1A09227B1F435A33'

fat="/tmp/* /usr/lib/python3.*/__pycache__ /home/$user/.cache/* /root/.cache/* /home/$user/.local/bin /root/.local/bin /var/cache/pacman/pkg/*"

#################
### Functions ###
#################

ctnr_run () {  # [-u|-b] <cmd> [<cmd-arg>...]
  _u=root
  if [ "$1" = -u ]; then
    _u=$user
    shift
  elif [ "$1" = -b ]; then
    _u=builder
    shift
  fi
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

alias ctnr_pkg="ctnr_run pacman --noconfirm"
alias ctnr_pkg_upgrade="ctnr_pkg -Syu"
alias ctnr_pkg_add="ctnr_pkg -S --needed"
alias ctnr_pkg_del="ctnr_pkg -Rsn"

ctnr_mkuser () {  # <username>
  if ! ctnr_run id "$1" >/dev/null 2 >&1; then
    ctnr_run useradd -m "$1"
  fi
}

ctnr_trim () {
  # shellcheck disable=SC2046
  ctnr_pkg_del $build_pkgs $(ctnr_run pacman -Qqgtt $build_groups)
  ctnr_run sh -c "rm -rf $fat"
}

#############
### Build ###
#############

# Start fresh, or from a daily "jumpstart" image if available
buildah rm "$ctnr" 2>/dev/null || true
if ! buildah from -q --name "$ctnr" "$img-jumpstart:$today" 2>/dev/null; then
  buildah from -q --name "$ctnr" "$base_img"
  make_jumpstart_img=1
fi

# Set the timezone
ctnr_run ln -sf /usr/share/zoneinfo/$tz /etc/localtime

# Upgrade and install official packages
printf '%s\n' '' '>>> Upgrading and installing distro packages . . .' '' >&2
ctnr_pkg_upgrade
# shellcheck disable=SC2086
ctnr_pkg_add $pkgs $build_pkgs $build_groups

# Add user
ctnr_mkuser $user

# Install AUR packages
printf '%s\n' '' '>>> Installing AUR packages . . .' '' >&2
ctnr_mkuser builder
ctnr_run rm -f /etc/sudoers.d/builder
printf '%s\n' 'builder ALL=(ALL) NOPASSWD: ALL' \
| ctnr_append '/etc/sudoers.d/builder'
ctnr_run -b git clone 'https://aur.archlinux.org/paru-bin' /tmp/paru-bin
buildah config --workingdir /tmp/paru-bin "$ctnr"
ctnr_run -b makepkg --noconfirm -si
buildah config --workingdir "/home/$user" "$ctnr"
for key in $gpg_keys; do
  ctnr_run -b gpg --keyserver keyserver.ubuntu.com --recv-keys "$key"
done
# shellcheck disable=SC2086
ctnr_run -b paru -S --noconfirm --needed $aur_pkgs
ctnr_pkg_del paru-bin

# Copy app and svcs into container
tmp=$(mktemp -d)
# First, ready payloads:
git -C "$repo" archive HEAD:app >"$tmp/app.tar"
"$repo/mk/file_ids.sh" -d "$deployment" "$tmp/theme_previews.yml"
"$repo/mk/svcs.zsh" -d "$deployment" "$tmp/svcs"
ctnr_run sh -c "[ -d /home/$user/venv ]" && ctnr_run mv "/home/$user/venv" "/tmp/jumpstart_venv"
# Second, burn down home:
ctnr_run rm -rf "$svcs_dir"
ctnr_run rm -rf "/home/$user"
# Third, deliver:
ctnr_fetch -u "$tmp/app.tar" /home/$user
ctnr_run -u chmod 0700 /home/$user
ctnr_fetch -u "$tmp/theme_previews.yml" /home/$user/
ctnr_fetch "$tmp/svcs" "$svcs_dir"
ctnr_run sh -c '[ -d /tmp/jumpstart_venv ]' && ctnr_run mv "/tmp/jumpstart_venv" /home/$user/venv
# Tidy up:
rm -rf "$tmp"

# Install python modules
printf '%s\n' '' '>>> Installing PyPI packages . . .' '' >&2
ctnr_run -u python3 -m venv /home/$user/venv
ctnr_run /home/$user/venv/bin/pip install -qU pip wheel
ctnr_run /home/$user/venv/bin/pip install -Ur /home/$user/requirements.txt
ctnr_run /home/$user/venv/bin/pip uninstall -qy pip wheel

# Save this stage as a daily "jumpstart" image
if [ $make_jumpstart_img ]; then
  printf '%s\n' '' '>>> Making jumpstart image . . .' '' >&2
  ctnr_trim
  buildah commit -q --rm "$ctnr" "$img-jumpstart:$today"
  buildah from -q --name "$ctnr" "$img-jumpstart:$today"
  ctnr_pkg_upgrade
  ctnr_pkg_add $build_pkgs $build_groups
fi

# Install iosevka font
ctnr_fetch "$iosevka_pkg" /tmp
ctnr_run sh -c "tar xf /tmp/ttf-iosevka-*.pkg.tar.zst -C / --wildcards --wildcards-match-slash '*-regular.ttf' '*-italic.ttf' '*-bold.ttf' '*-bolditalic.ttf'"

# Install papertrail agent, if enabled
if [ "$(yaml-get -S -p 'svcs[name == papertrail].enabled' "$repo/vars.$deployment.yml")" = True ]; then
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
ctnr_trim

# Set default command
buildah config --cmd "s6-svscan $svcs_dir" "$ctnr"

# Press container as image
buildah rmi "$img:$today" "$img:latest" "$img:$version" 2>/dev/null || true
buildah tag "$(buildah commit -q --rm "$ctnr" "$img:latest")" "$img:$today" "$img:$version"
if [ "$branch" ]; then
  buildah tag "$img:latest" "$img:$branch"
fi

printf '%s\n' '' \
  '###################' \
  "### BUILT IMAGE ###" \
  '###################' '' \
  ">>> To decrypt credentials, you'll need to add or mount your age encryption keys as /root/.config/sops/age/keys.txt" \
  ">>> For the internal process supervision to work, you'll need to unmask /sys/fs/cgroup" \
  ">>> See start/podman.sh, which uses the host user's encryption keys and mounts a DB if present" ''

if [ "$do_push" ]; then
  podman push "$img-jumpstart:$today"
  podman push "$img:latest"
  podman push "$img:$today"
  podman push "$img:$version"
  if [ "$branch" ]; then
    podman push "$img:$branch"
  fi
fi
