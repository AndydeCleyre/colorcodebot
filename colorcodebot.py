#!/usr/bin/env python3
import io

import yaml
from plumbum.cmd import highlight
from telebot import TeleBot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from vault import TG_API_KEY


LANG = {
    'welcome': "Hello! Send me a snippet of code as your message text, and I'll send you a colorized HTML file.",
    'query ext': "Fantastic! What type of code is this?\n\nTo add more types, message @andykluger."
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
            ('Python', 'py'),
            ('Ruby', 'rb'),
            ('Rust', 'rs'),
            ('Swift', 'swift')
        )
    ))
    BOT.reply_to(message, LANG['query ext'], reply_markup=kb)


@BOT.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')
def set_snippet_filetype(query):
    snippet = query.message.reply_to_message
    data = yload(query.data)
    html = mk_html(snippet.text, data['ext'])
    with io.StringIO(html) as doc:
        doc.name = 'code.html'
        BOT.send_document(query.message.chat.id, doc, snippet.message_id)


if __name__ == '__main__':
    BOT.polling()
