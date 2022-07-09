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
  if [ "$1" = --clean ]; then do_clean=1;  shift;   fi
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
db_dir=$PWD/db-files

############
### Pull ###
############

podman pull "$img" || buildah pull --policy=never "$img"

####################################
### Prepare DB File for mounting ###
####################################

mkdir -p "$db_dir"
printf '%s\n' '' "Ensuring the in-container user can read and write to $db_dir . . ." 1>&2

# Get host UID for ctnr_user
ownme=$(mktemp)
podman run --rm -u root -v "$ownme:/ownme" "$img" chown "$ctnr_user" /ownme
uid=$(stat -c %u "$ownme")

chown -R "$uid" "$db_dir" || sudo chown -R "$uid" "$db_dir"

ls -ld "$db_dir" 1>&2
ls -l "$db_dir" 1>&2
printf '%s\n' ''

########################
### The King is Dead ###
########################

podman stop -i $ctnr
podman rm -i $ctnr

##########################
### Long Live the King ###
##########################

podman run \
  -d \
  -v ~/.config/sops/age/keys.txt:/root/.config/sops/age/keys.txt:ro \
  -v "${db_dir}:/home/${ctnr_user}/db-files" \
  --security-opt unmask=/sys/fs/cgroup \
  --name $ctnr \
  "$img"

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
