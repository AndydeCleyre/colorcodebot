#!/bin/sh -e
ccb=`sudo buildah from colorcodebot:0.1`

# run, supervised internally (auto-recover), log to stdout:
sudo -E buildah run $ccb

# run, supervised internally (auto-recover), log to internal log files:
# sudo -E buildah run $ccb -- mv /home/colorcodebot/svcs/colorcodebot/log.down /home/colorcodebot/svcs/colorcodebot/log
# sudo -E buildah run $ccb

# run, unsupervised (no auto-recover), log to stdout:
# sudo -E buildah run $ccb -- mv /home/colorcodebot/svcs/colorcodebot/log.down /home/colorcodebot/svcs/colorcodebot/log
# sudo -E buildah run $ccb -- /home/colorcodebot/colorcodebot.py
