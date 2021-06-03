Color Code Bot
==============

- up and running on |telegram|
- container images built by GitHub Actions: |actions|
- container images pushed to |quay|

To use it, chat directly with the `@colorcodebot`_.

As a convenience, you can get to a direct chat with it from any other chat,
by typing ``@colorcodebot`` and tapping the button that pops up.

Development
-----------

Depending on your hardware, you may see faster syntax guessing (from guesslang_)
by installing ``cuda`` and ``cudnn`` packages.
This is *not* done for the currently hosted container images.


.. _@colorcodebot: https://t.me/colorcodebot
.. _guesslang: https://github.com/yoeo/guesslang

.. |actions| image:: https://img.shields.io/github/workflow/status/andydecleyre/colorcodebot/Build%20and%20push%20a%20container%20image?logo=github&style=for-the-badge
   :alt: GitHub Actions Status
   :target: https://github.com/AndydeCleyre/colorcodebot/actions

.. |quay| image:: https://img.shields.io/badge/Quay.io-andykluger%2Fcolorcodebot--prod--alpine-lightgrey?logo=redhat&style=for-the-badge
   :alt: Telegram user @colorcodebot
   :target: https://quay.io/repository/andykluger/colorcodebot-prod-alpine?tab=tags

.. |telegram| image:: https://img.shields.io/badge/Telegram-%40colorcodebot-blue?logo=telegram&style=for-the-badge
   :alt: Telegram user @colorcodebot
   :target: https://t.me/colorcodebot

