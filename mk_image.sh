#!/bin/sh -e
appname="colorcodebot"
version="0.1"
pyver="3.6"
ccb=`sudo buildah from alpine:3.7`

# copy app into container:
sudo -E buildah run $ccb -- adduser -D $appname
sudo -E buildah add --chown $appname:$appname $ccb app /home/$appname/

# prune junk from build-host, if found:
sudo -E buildah run $ccb -- rm -rf /home/$appname/__pycache__ /home/$appname/venv

# strip sensitive data, if directed to:
if [ $1 = "--no-vault" ]; then
  sudo -E buildah run $ccb -- rm /home/$appname/vault.yml
fi

# update packages; install runtime and build-time dependencies:
sudo -E buildah run $ccb -- apk update
sudo -E buildah run $ccb -- apk upgrade
sudo -E buildah run $ccb -- apk add fontconfig freetype jpeg python3 s6 zlib
sudo -E buildah run $ccb -- apk add freetype-dev gcc jpeg-dev musl-dev python3-dev zlib-dev

# install python modules; patch pygments:
sudo -E buildah run $ccb -- pip3 install -U -r /home/$appname/requirements.txt
sudo -E buildah run $ccb -- sed -i 's/background-color: #f0f0f0; //g' /usr/lib/python$pyver/site-packages/pygments/formatters/html.py

# install fonts:
sudo -E buildah run $ccb -- mkdir -p /usr/share/fonts/TTF
sudo -E buildah add $ccb /usr/share/fonts/TTF/iosevka-custom-{regular,italic,bold}.ttf /usr/share/fonts/TTF

# cut the fat:
sudo -E buildah run $ccb -- apk del freetype-dev gcc jpeg-dev musl-dev python3-dev zlib-dev
sudo -E buildah run $ccb -- find /var/cache/apk -type f -delete
sudo -E buildah run $ccb -- rm -rf /root/.cache

# set default command; commit container to image; remove container:
sudo -E buildah config --cmd "s6-svscan /home/$appname/svcs" $ccb
sudo -E buildah commit --rm $ccb $appname:$version
