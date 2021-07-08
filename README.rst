==============
Color Code Bot
==============

Share code snippets as beautiful syntax-highlighted images and HTML on Telegram
===============================================================================

.. list-table::
   :widths: auto
   :align: center

   * - |telegram|
     - |quay|
     - |actions-ctnr|
     - |actions-reqs|

It's a small bit of Python glue between great projects, including:

- highlight_ (lua, renders HTML)
- pyTelegramBotAPI_
- weasyprint_ (HTML `->` image)
- guesslang_ (uses tensorflow; saves you the step of specifying the snippet's language)
- Iosevka_ (the most wonderful monospaced font)

.. image:: https://user-images.githubusercontent.com/1787385/124971355-13fa0280-dff7-11eb-901c-73c5347a4e03.png
   :alt: Screenshot of the bot in action
   :align: right

Usage
-----

Send `@colorcodebot`_ the code you want highlighted,
as a forwarded or original direct message.

As a convenience, you can get to a direct chat with it from any other chat,
by typing ``@colorcodebot`` and tapping the button that pops up.
A button returning you (with a shiny new image)
to your original chat will be presented after you send the code.

Click to watch `a demo video`_!

Development & Deployment
------------------------

Depending on your hardware, you may see faster syntax guessing (from guesslang_)
by installing ``cuda`` and ``cudnn`` packages.
This is *not* done for the currently hosted container images.

Outside of the core Python "app" part of the project,
sops_ is used for secrets,
buildah_ for container building,
GitHub Actions for automated container image builds and other CI tasks,
and `wheezy.template`_ and yamlpath_ are extremely handy for
defining+rendering service definitions and other dev/ops maneuvers.

I will probably add more info here eventually,
but please do `send a message`_ or open an issue with any questions.


.. _a demo video: https://user-images.githubusercontent.com/1787385/123204250-ae9a0380-d485-11eb-981d-3302220aad58.mp4
.. _buildah: https://github.com/containers/buildah
.. _@colorcodebot: https://t.me/colorcodebot
.. _guesslang: https://github.com/yoeo/guesslang
.. _highlight: http://www.andre-simon.de/doku/highlight/highlight.html
.. _Iosevka: https://github.com/be5invis/Iosevka
.. _pyTelegramBotAPI: https://github.com/eternnoir/pyTelegramBotAPI
.. _send a message: https://t.me/andykluger
.. _sops: https://github.com/mozilla/sops
.. _weasyprint: https://weasyprint.org/
.. _wheezy.template: https://github.com/akornatskyy/wheezy.template
.. _yamlpath: https://github.com/wwkimball/yamlpath


.. |actions-ctnr| image:: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/ci.yml/badge.svg?branch=develop
   :alt: Automated Container Build Status
   :target: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/ci.yml

.. |actions-reqs| image:: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/reqs.yml/badge.svg?branch=develop
   :alt: Automated Python Requirements Bump Status
   :target: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/reqs.yml

.. |quay| image:: https://img.shields.io/badge/Quay.io-andykluger%2Fcolorcodebot--prod--archlinux-green?logo=redhat
   :alt: Container Image Repository
   :target: https://quay.io/repository/andykluger/colorcodebot-prod-archlinux?tab=tags

.. |telegram| image:: https://img.shields.io/badge/Telegram-%40colorcodebot-blue?logo=telegram
   :alt: Telegram user @colorcodebot
   :target: https://t.me/colorcodebot
