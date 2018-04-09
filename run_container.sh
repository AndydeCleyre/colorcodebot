#!/bin/sh -e
cctainer=`buildah from colorcodebot:0.1`
buildah run $cctainer
