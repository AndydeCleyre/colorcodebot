Color Code Bot
==============

- |telegram|
- |quay|
- |actions-ctnr|
- |actions-reqs|

To use it, chat directly with `@colorcodebot`_.

As a convenience, you can get to a direct chat with it from any other chat,
by typing ``@colorcodebot`` and tapping the button that pops up.

Click to watch `a demo video`_!

|demo|

This project uses some excellent existing tools, including:

- pyTelegramBotAPI_
- highlight_
- weasyprint_
- guesslang_

Development & Deployment
------------------------

Depending on your hardware, you may see faster syntax guessing (from guesslang_)
by installing ``cuda`` and ``cudnn`` packages.
This is *not* done for the currently hosted container images.

I will probably add more info here eventually,
but please do `send a message`_ or open an issue with any questions.


.. _a demo video: https://user-images.githubusercontent.com/1787385/123204250-ae9a0380-d485-11eb-981d-3302220aad58.mp4
.. _@colorcodebot: https://t.me/colorcodebot
.. _highlight: http://www.andre-simon.de/doku/highlight/highlight.html
.. _guesslang: https://github.com/yoeo/guesslang
.. _pyTelegramBotAPI: https://github.com/eternnoir/pyTelegramBotAPI
.. _send a message: https://t.me/andykluger
.. _weasyprint: https://weasyprint.org/


.. |actions-ctnr| image:: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/ci.yml/badge.svg?branch=develop
   :alt: Automated Container Build Status
   :target: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/ci.yml

.. |actions-reqs| image:: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/reqs.yml/badge.svg?branch=develop
   :alt: Automated Python Requirements Bump Status
   :target: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/reqs.yml

.. |demo| image:: https://user-images.githubusercontent.com/1787385/123205425-dee2a180-d487-11eb-9430-a7f79aecac0c.jpg
   :alt: Demo of the bot in use
   :target: https://user-images.githubusercontent.com/1787385/123204250-ae9a0380-d485-11eb-981d-3302220aad58.mp4
   :height: 720px

.. |quay| image:: https://img.shields.io/badge/Quay.io-andykluger%2Fcolorcodebot--prod--archlinux-green?logo=redhat
   :alt: Container Image Repository
   :target: https://quay.io/repository/andykluger/colorcodebot-prod-archlinux?tab=tags

.. |telegram| image:: https://img.shields.io/badge/Telegram-%40colorcodebot-blue?logo=telegram
   :alt: Telegram user @colorcodebot
   :target: https://t.me/colorcodebot
