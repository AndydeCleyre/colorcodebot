#!/bin/sh -e
appname="colorcodebot"
version="0.1"
pyver="3.6"
ccb=`sudo buildah from alpine:3.7`

rm -rf app/__pycache__ app/venv

sudo -E buildah run $ccb -- adduser -D $appname
sudo -E buildah add --chown $appname:$appname $ccb app "/home/$appname/"

sudo -E buildah run $ccb -- apk update
sudo -E buildah run $ccb -- apk upgrade
sudo -E buildah run $ccb -- apk add fontconfig freetype jpeg python3 s6 zlib
sudo -E buildah run $ccb -- apk add freetype-dev gcc jpeg-dev musl-dev python3-dev zlib-dev

sudo -E buildah run $ccb -- pip3 install -U -r /home/$appname/requirements.txt
sudo -E buildah run $ccb -- sed -i 's/background-color: #f0f0f0; //g' /usr/lib/python$pyver/site-packages/pygments/formatters/html.py

sudo -E buildah run $ccb -- mkdir -p /usr/share/fonts/TTF
sudo -E buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-{regular,italic,bold}.ttf /usr/share/fonts/TTF

sudo -E buildah run $ccb -- apk del freetype-dev gcc jpeg-dev musl-dev python3-dev zlib-dev
sudo -E buildah run $ccb -- rm -r /var/cache/apk

sudo -E buildah config --cmd "s6-svscan /home/$appname/svcs" $ccb
sudo -E buildah commit --rm $ccb $appname:$version
