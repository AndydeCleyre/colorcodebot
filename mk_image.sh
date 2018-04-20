#!/bin/sh -e
appname="colorcodebot"
version="0.1"
pyver="3.6"
ccb=`buildah from alpine:3.7`

rm -rf app/__pycache__
rm -rf app/venv

buildah run $ccb -- adduser -D $appname
buildah add --chown $appname:$appname $ccb app "/home/$appname/"

buildah run $ccb -- apk update
buildah run $ccb -- apk upgrade
buildah run $ccb -- apk add \
  fontconfig \
  freetype \
  freetype-dev \
  gcc \
  jpeg \
  jpeg-dev \
  musl-dev \
  python3 \
  python3-dev \
  s6 \
  zlib \
  zlib-dev

buildah run $ccb -- pip3 install -U -r /home/$appname/requirements.txt
buildah run $ccb -- sed -i 's/background-color: #f0f0f0; //g' /usr/lib/python$pyver/site-packages/pygments/formatters/html.py

buildah run $ccb -- mkdir -p /usr/share/fonts/TTF
buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-{regular,italic,bold}.ttf /usr/share/fonts/TTF

buildah run $ccb -- apk del \
  freetype-dev \
  gcc \
  jpeg-dev \
  musl-dev \
  python3-dev \
  zlib-dev
buildah run $ccb -- rm -r /var/cache/apk

buildah config --cmd "s6-svscan /home/$appname/svcs" $ccb
buildah commit --rm $ccb $appname:$version
