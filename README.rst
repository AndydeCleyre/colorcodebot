Color Code Bot
==============

- |telegram|
- |actions|
- |quay|

To use it, chat directly with `@colorcodebot`_.

As a convenience, you can get to a direct chat with it from any other chat,
by typing ``@colorcodebot`` and tapping the button that pops up.

Check out `a demo video`_!

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


.. _a demo video: https://user-images.githubusercontent.com/1787385/123162011-19275100-d43e-11eb-9788-7defa4bdf1d5.mp4
.. _@colorcodebot: https://t.me/colorcodebot
.. _highlight: http://www.andre-simon.de/doku/highlight/highlight.html
.. _guesslang: https://github.com/yoeo/guesslang
.. _pyTelegramBotAPI: https://github.com/eternnoir/pyTelegramBotAPI
.. _send a message: https://t.me/andykluger
.. _weasyprint: https://weasyprint.org/


.. |actions| image:: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/ci.yml/badge.svg?branch=develop
   :alt: Automated Container Build Status
   :target: https://github.com/AndydeCleyre/colorcodebot/actions/workflows/ci.yml

.. |quay| image:: https://img.shields.io/badge/Quay.io-andykluger%2Fcolorcodebot--prod--archlinux-green?logo=redhat
   :alt: Container Image Repository
   :target: https://quay.io/repository/andykluger/colorcodebot-prod-archlinux?tab=tags

.. |telegram| image:: https://img.shields.io/badge/Telegram-%40colorcodebot-blue?logo=telegram
   :alt: Telegram user @colorcodebot
   :target: https://t.me/colorcodebot
