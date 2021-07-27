#!/bin/sh -e
# [-d <deployment>=dev] [-t <image-tag>=develop] [-r <registry-user>=quay.io/andykluger] [--clean]

##################
### Parse Args ###
##################

deployment=dev
tag=develop
registry_user=quay.io/andykluger
unset do_clean
while [ "$1" = -d ] || [ "$1" = -t ] || [ "$1" = -r ] || [ "$1" = --clean ]; do
  if [ "$1" = -d ]; then deployment=$2;    shift 2; fi
  if [ "$1" = -t ]; then tag=$2;           shift 2; fi
  if [ "$1" = -r ]; then registry_user=$2; shift 2; fi
  if [ "$1" = --clean ]; then do_clean=1; shift; fi
done

if [ "$1" ]; then
  printf '%s\n' 'Start a colorcodebot container with podman' 'Args: [-d <deployment>=dev] [-t <image-tag>=develop] [-r <registry-user>=quay.io/andykluger] [--clean]' 1>&2
  exit 1
fi

#################
### Configure ###
#################

img="${registry_user}/colorcodebot-${deployment}-archlinux:${tag}"
ctnr=ccb
ctnr_user=colorcodebot
db_file=$PWD/user_themes.sqlite

############
### Pull ###
############

podman pull "$img" || buildah pull --policy=never "$img"

####################################
### Prepare DB File for mounting ###
####################################

if [ -f "$db_file" ]; then
  printf '%s\n' '' "Found DB on host:" "$(ls -l "$db_file")" 'Ensuring the in-container user can read and write to it . . .' 1>&2

  # Get host UID for ctnr_user
  ownme=$(mktemp)
  podman run --rm -u root -v "$ownme:/ownme" "$img" chown "$ctnr_user" /ownme
  uid=$(stat -c %u "$ownme")
  rm -rf "$ownme"

  chown "$uid" "$db_file"

  ls -l "$db_file" 1>&2
  printf '%s\n' ''

  do_mount_db=1
fi

########################
### The King is Dead ###
########################

podman stop -i $ctnr
podman rm -i $ctnr

##########################
### Long Live the King ###
##########################

if [ $do_mount_db ]; then
  podman run \
    -d \
    -v ~/.config/sops/age/keys.txt:/root/.config/sops/age/keys.txt:ro \
    -v "${db_file}:/home/${ctnr_user}/user_themes.sqlite:rw" \
    --security-opt unmask=/sys/fs/cgroup \
    --name $ctnr \
    "$img"
else
  podman run \
    -d \
    -v ~/.config/sops/age/keys.txt:/root/.config/sops/age/keys.txt:ro \
    --security-opt unmask=/sys/fs/cgroup \
    --name $ctnr \
    "$img"
fi

##############
### Report ###
##############

podman ps

###################
### Maintenance ###
###################

if [ $do_clean ]; then
  deadbeats=$(podman images -f dangling=true --format '{{.ID}}')
  if [ "$deadbeats" ]; then
    # shellcheck disable=SC2086
    podman rmi $deadbeats
  fi
fi
