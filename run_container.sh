#!/bin/sh -e
cctainer=`buildah from colorcodebot-image-0.1`
buildah run $cctainer
