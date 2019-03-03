#!/bin/sh -e
ccb=`buildah from colorcodebot:0.2`

# run, supervised internally (auto-recover), log to internal log files:
buildah run $ccb

# run, unsupervised (no auto-recover), log to stdout:
# buildah run $ccb -- /home/colorcodebot/colorcodebot.py
