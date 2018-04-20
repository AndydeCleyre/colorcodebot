#!/bin/sh -e
appname="colorcodebot"
version=0.1

rm -rf app/__pycache__
rm -rf app/venv

ccb=`buildah from alpine`
buildah run $ccb -- adduser -D $appname
buildah add --chown $appname:$appname $ccb app "/home/$appname/"

buildah run $ccb -- apk update
buildah run $ccb -- apk upgrade
buildah run $ccb -- apk add \
  fontconfig \
  freetype \
  freetype-dev \
  gcc \
  highlight \
  jpeg \
  jpeg-dev \
  musl-dev \
  python3 \
  python3-dev \
  s6 \
  zlib \
  zlib-dev
buildah run $ccb -- pip3 install -U -r /home/$appname/requirements.txt
buildah run $ccb -- apk del \
  freetype-dev \
  gcc \
  jpeg-dev \
  musl-dev \
  python3-dev \
  zlib-dev
buildah run $ccb -- rm -r /var/cache/apk

buildah run $ccb -- mkdir -p /usr/share/fonts/TTF
buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-regular.ttf /usr/share/fonts/TTF
buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-italic.ttf /usr/share/fonts/TTF
buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-bold.ttf /usr/share/fonts/TTF

buildah config --cmd "s6-svscan /home/$appname/svcs" $ccb
buildah commit --rm $ccb $appname:$version

# buildah push $appname-$version oci-archive:$appname-$version.oci.tar:$appname:$version
# buildah push $appname-$version docker-archive:$appname-$version.docker.tar:$appname:$version
