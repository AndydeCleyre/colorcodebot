#!/bin/sh -e
ccb=`buildah from colorcodebot:0.1`

# run, supervised internally (auto-recover), log to stdout:
buildah run $ccb

# run, supervised internally (auto-recover), log to internal log files:
# buildah run $ccb -- mv /home/colorcodebot/svcs/colorcodebot/log.down /home/colorcodebot/svcs/colorcodebot/log
# buildah run $ccb

# run, unsupervised (no auto-recover), log to stdout:
# buildah run $ccb -- mv /home/colorcodebot/svcs/colorcodebot/log.down /home/colorcodebot/svcs/colorcodebot/log
# buildah run $ccb -- /home/colorcodebot/colorcodebot.py
