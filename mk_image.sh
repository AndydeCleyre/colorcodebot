#!/bin/sh -e
appname="colorcodebot"
version="0.1"
pyver="3.6"
ccb=`sudo buildah from alpine:3.7`

rm -rf app/__pycache__ app/venv

sudo buildah run $ccb -- adduser -D $appname
sudo buildah add --chown $appname:$appname $ccb app "/home/$appname/"

sudo buildah run $ccb -- apk update
sudo buildah run $ccb -- apk upgrade
sudo buildah run $ccb -- apk add fontconfig freetype jpeg python3 s6 zlib
sudo buildah run $ccb -- apk add freetype-dev gcc jpeg-dev musl-dev python3-dev zlib-dev

sudo buildah run $ccb -- pip3 install -U -r /home/$appname/requirements.txt
sudo buildah run $ccb -- sed -i 's/background-color: #f0f0f0; //g' /usr/lib/python$pyver/site-packages/pygments/formatters/html.py

sudo buildah run $ccb -- mkdir -p /usr/share/fonts/TTF
sudo buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-{regular,italic,bold}.ttf /usr/share/fonts/TTF

sudo buildah run $ccb -- apk del freetype-dev gcc jpeg-dev musl-dev python3-dev zlib-dev
sudo buildah run $ccb -- rm -r /var/cache/apk

sudo buildah config --cmd "s6-svscan /home/$appname/svcs" $ccb
sudo buildah commit --rm $ccb $appname:$version
