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
buildah run $ccb -- apk add python3 python3-dev gcc musl-dev highlight s6
buildah run $ccb -- pip3 install -U -r /home/$appname/requirements.txt

buildah config --cmd "s6-svscan /home/$appname/svcs" $ccb

buildah run $ccb -- apk del python3-dev gcc musl-dev
buildah run $ccb -- rm -r /var/cache

buildah commit --rm $ccb $appname:$version

# buildah push $appname-$version oci-archive:$appname-$version.oci.tar:$appname:$version
# buildah push $appname-$version docker-archive:$appname-$version.docker.tar:$appname:$version
