#!/bin/sh -ex

pkgname=silicon-solidity-git

artifact="${pkgname}-*-x86_64.pkg.tar.zst"

if [ "$1" ]; then
  printf '%s\n' \
    "Build $artifact" \
    'Args: None' \
    1>&2
  exit 1
fi

ctnr=siliconbuild
buildah from --name $ctnr docker.io/library/archlinux:base-devel

buildah run $ctnr useradd -m builder
buildah run $ctnr sh -c "printf '%s\n' 'builder ALL=(ALL) NOPASSWD: ALL' >/etc/sudoers.d/builder"

buildah run --user builder $ctnr mkdir /home/builder/${pkgname}
buildah copy --chown builder $ctnr "$(dirname "$0")"/PKGBUILD /home/builder/${pkgname}/

buildah run $ctnr pacman -Syu --noconfirm
buildah run --user builder --workingdir /home/builder/${pkgname} $ctnr makepkg -s --noconfirm

artifact="$(buildah run --user builder --workingdir /home/builder/${pkgname} $ctnr find . -name "$artifact")"
buildah run --user builder $ctnr cat "/home/builder/${pkgname}/${artifact}" >"$(dirname "$0")/${artifact}"

buildah rm $ctnr
