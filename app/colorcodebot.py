#!/usr/bin/env python3
import io

import strictyaml
import structlog
from plumbum.cmd import highlight
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from vault import TG_API_KEY


LOG = structlog.get_logger()


LANG = {
    'welcome': (
        "Hello! Send me a snippet of code as your message text, "
        "and I'll send you a colorized HTML file."
    ),
    'query ext': (
        "Fantastic! What type of code is this?\n\n"
        "To add more types, message @andykluger."
    ),
    'switch to direct': "Let's color some code!"
}


BOT = TeleBot(TG_API_KEY)


def yload(yamlstr):
    return strictyaml.load(yamlstr).data


def ydump(data):
    return strictyaml.as_document(data).as_yaml()


def mk_html(code: str, ext: str):
    return (highlight[
        '--line-numbers',
        '--inline-css',
        '--style', 'solarized-dark',
        '--syntax', ext
    ] << code)()


@BOT.inline_handler(lambda q: True)
def switch_from_inline(inline_query):
    LOG.msg(
        "receiving inline query",
        user_id=inline_query.from_user.id,
        user_first_name=inline_query.from_user.first_name,
        query=inline_query.query
    )
    BOT.answer_inline_query(
        inline_query.id, [],
        switch_pm_text=LANG['switch to direct'], switch_pm_parameter='x'
    )


@BOT.message_handler(commands=['start', 'help'])
def welcome(message):
    LOG.msg(
        "introducing myself",
        user_id=message.from_user.id,
        user_first_name=message.from_user.first_name
    )
    BOT.reply_to(message, LANG['welcome'])


@BOT.message_handler(func=lambda m: m.content_type == 'text')
def intake_snippet(message):
    LOG.msg(
        "receiving code",
        user_id=message.from_user.id,
        user_first_name=message.from_user.first_name
    )
    kb = InlineKeyboardMarkup()
    kb.add(*(
        InlineKeyboardButton(
            name, callback_data=ydump({'action': 'set ext', 'ext': ext})
        ) for name, ext in (
            ('Bash', 'sh'),
            ('C#', 'cs'),
            ('C', 'c'),
            ('CSS', 'css'),
            ('Go', 'go'),
            ('HTML', 'html'),
            ('Java', 'java'),
            ('JavaScript', 'js'),
            ('JSON', 'json'),
            ('Kotlin', 'kt'),
            ('NGINX', 'nginx'),
            ('Objective C', 'objc'),
            ('PHP', 'php'),
            ('Python', 'py'),
            ('Ruby', 'rb'),
            ('Rust', 'rs'),
            ('Swift', 'swift')
        )
    ))
    BOT.reply_to(message, LANG['query ext'], reply_markup=kb)


@BOT.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')
def set_snippet_filetype(cb_query):
    snippet = cb_query.message.reply_to_message
    data = yload(cb_query.data)
    LOG.msg(
        "colorizing code",
        user_id=cb_query.message.reply_to_message.from_user.id,
        user_first_name=cb_query.message.reply_to_message.from_user.first_name,
        syntax=data['ext']
    )
    html = mk_html(snippet.text, data['ext'])
    with io.StringIO(html) as doc:
        doc.name = 'code.html'
        BOT.send_document(cb_query.message.chat.id, doc, snippet.message_id)


if __name__ == '__main__':
    BOT.polling()
