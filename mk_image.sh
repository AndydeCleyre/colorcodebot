#!/bin/sh -e
appname="colorcodebot"
version=0.1
container=`buildah from alpine`

buildah run $container -- adduser -D $appname
buildah add --chown $appname:$appname $container app "/home/$appname/"

buildah run $container -- apk update
buildah run $container -- apk upgrade
buildah run $container -- apk add python3-dev highlight s6
buildah run $container -- pip3 install -U -r /home/$appname/requirements.txt

buildah config $container --cmd "s6-svscan /home/$appname/svcs"

buildah commit --rm $container $appname-image-$version
