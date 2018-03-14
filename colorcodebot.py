#!/usr/bin/env python3
import io
from string import ascii_letters
# from uuid import uuid4

import yaml
from plumbum.cmd import highlight  # , wkhtmltopdf
from telebot import TeleBot
from telebot.types import (
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup
    # InlineQueryResultDocument
)

from vault import TG_API_KEY


LANG = {
    'welcome': (
        "Hello! Send me a snippet of code as your message text, "
        "and I'll send you a colorized HTML file. "
        # "Short snippets can use this bot inline, directly, in any chat "
        # "(e.g. `@colorcodebot py def hello_world(): print('Hello, World!')` "
        # "but will send PDFs rather than HTML."
    ),
    'query ext': "Fantastic! What type of code is this?",
    # 'custom ext btn': "Something else",
    # 'query custom ext': "OK, what's the file extension?",
    # 'too long for inline': "That's too much for inline usage, let's try one-on-one.",
    'suggest pm': "Let's chat one-on-one."
}
BOT = TeleBot(TG_API_KEY)


yload = yaml.safe_load


def ydump(data):
    return yaml.safe_dump(data, default_flow_style=False)


def mk_html(code: str, ext: str):
    return (highlight[
        '--line-numbers',
        '--inline-css',
        '--style', 'solarized-dark',
        '--syntax', ext
    ] << code)()


@BOT.message_handler(commands=['start', 'help'])
def welcome(message):
    BOT.reply_to(message, LANG['welcome'])


@BOT.message_handler(func=lambda m: m.content_type == 'text')
def intake_snippet(message):
    kb = InlineKeyboardMarkup()
    kb.add(*(
        InlineKeyboardButton(
            name, callback_data=ydump({'action': 'set ext', 'ext': ext})
        ) for name, ext in (
            ('Python', 'py'),
            ('Bash', 'sh'),
            ('HTML', 'html'),
            ('CSS', 'css')
        )
    ))
    # kb.add(InlineKeyboardButton(
    #     LANG['custom ext btn'],
    #     callback_data=ydump({'action': 'get custom ext'})
    # ))
    BOT.reply_to(message, LANG['query ext'], reply_markup=kb)


# @BOT.callback_query_handler(lambda q: yload(q.data)['action'] == 'get custom ext')
# def get_custom_filetype(query):
#     snippet = query.message.reply_to_message
#     msg = BOT.send_message(
#         query.message.chat.id,
#         LANG['query custom ext'],
#         reply_to_message_id=snippet.message_id,
#         reply_markup=ForceReply()
#     )
#     BOT.register_for_reply(msg, set_snippet_custom_filetype)


# def set_snippet_custom_filetype(message):
#     ext = ''.join(filter(ascii_letters.__contains__, message.text))
    # data = yload(query.data)
    # html = mk_html(snippet.text, data['ext'])
    # with io.StringIO(html) as doc:
        # doc.name = 'code.html'
        # BOT.send_document(query.message.chat.id, doc, reply_to_message_id=snippet.message_id)


@BOT.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')
def set_snippet_filetype(query):
    snippet = query.message.reply_to_message
    data = yload(query.data)
    html = mk_html(snippet.text, data['ext'])
    with io.StringIO(html) as doc:
        doc.name = 'code.html'
        BOT.send_document(query.message.chat.id, doc, snippet.message_id)


# @BOT.inline_handler(lambda iq: iq.query.split(None, 1)[1:] and len(iq.query) <= 512)
# def suggest_inline_rendering(inline_query):
#     BOT.answer_inline_query(
#         inline_query.id,
#         [
#             InlineQueryResultDocument(
#                 uuid4(),
#                 'code.pdf',
#                 ''
#             )
#         ],
#         switch_pm_text=LANG['suggest pm']
#     )
    # mk_html()
    # wkhtmltopdf('-n', '--disable-local-file-access')


# @BOT.inline_handler(lambda iq: True)
# def suggest_private_rendering(inline_query):
#     BOT.answer_inline_query(inline_query.id, [], switch_pm_text=LANG['suggest pm'])
    # BOT.answer_inline_query(
    #     inline_query.id,
    #     [],
    #     switch_pm_text=LANG[
    #         'too long for inline' if len(inline_query.query) > 512 else 'suggest pm'
    #     ]
    # )


if __name__ == '__main__':
    BOT.polling()

# <filetype> <code to highlight>
