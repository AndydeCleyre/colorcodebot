#!/bin/sh -e
appname="colorcodebot"
version="0.2"
pyver="3.6"
ctnr=`buildah from alpine:3.9`
runtime_deps="fontconfig jpeg python3 s6"
buildtime_deps="freetype-dev gcc jpeg-dev musl-dev python3-dev"

alias bldr="buildah run $ctnr --"

# copy app into container:
bldr adduser -D $appname
buildah add --chown $appname:$appname $ctnr app /home/$appname

# prune junk from build-host, if found:
bldr rm -rf /home/$appname/__pycache__ /home/$appname/venv

# strip sensitive data, if directed to:
if [ $1 = "--no-vault" ]; then
  bldr rm -f /home/$appname/vault.yml
  bldr rm -f /home/$appname/log_files.yml
  bldr rm -f /home/$appname/svcs/papertrail
  bldr rm -f /home/$appname/user_themes.sqlite
fi

# upgrade packages; install runtime and build-time dependencies:
bldr apk upgrade
bldr apk add $runtime_deps $buildtime_deps

# install python modules; patch pygments:
bldr pip3 install -Ur /home/$appname/requirements.txt
bldr sed -i 's/background-color: #f0f0f0; //g' /usr/lib/python$pyver/site-packages/pygments/formatters/html.py

# install fonts:
bldr mkdir -p /usr/share/fonts/TTF
buildah add $ctnr /usr/share/fonts/TTF/iosevka-custom-{regular,italic,bold}.ttf /usr/share/fonts/TTF

# install papertrail agent:
wget "https://github.com/papertrail/remote_syslog2/releases/download/v0.20/remote_syslog_linux_amd64.tar.gz" -O - | tar xzf - -C /usr/local/bin remote_syslog

# cut the fat:
bldr apk del $buildtime_deps
bldr find /var/cache/apk -type f -delete
bldr rm -rf /root/.cache

# set default command; commit container to image; remove container:
buildah config --cmd "s6-svscan /home/$appname/svcs" $ctnr
buildah commit --rm $ctnr $appname:$version
