#!/usr/bin/env python3
import io

from plumbum.cmd import highlight
from pygments import lexers, formatters
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import pygments
import strictyaml
import structlog

from vault import TG_API_KEY


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


LOG = structlog.get_logger()
BOT = TeleBot(TG_API_KEY)


def yload(yamltxt: str) -> dict:
    return strictyaml.load(yamltxt).data


def ydump(data: dict) -> str:
    return strictyaml.as_document(data).as_yaml()


def mk_html(code: str, ext: str) -> str:
    """Return HTML content"""
    return (highlight[
        '--inline-css',
        '--style', 'molokai',
        '--syntax', ext
    ] << code)()


def mk_png(code: str, ext: str) -> str:
    """Return path of generated png"""
    return pygments.highlight(
        code,
        lexers.get_lexer_by_name({'rs': 'rust', 'py': 'py3'}.get(ext, ext)),
        formatters.ImageFormatter(font_name='Iosevka Custom', font_size=35, style='monokai')
    )


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
            ('C#', 'csharp'),
            ('C', 'c'),
            ('CSS', 'css'),
            ('Go', 'go'),
            ('HTML', 'html'),
            ('Java', 'java'),
            ('JavaScript', 'js'),
            ('JSON', 'json'),
            ('Kotlin', 'kotlin'),
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
    BOT.send_chat_action(cb_query.message.chat.id, 'upload_document')
    html = mk_html(snippet.text, data['ext'])
    with io.StringIO(html) as doc:
        doc.name = 'code.html'
        BOT.send_document(cb_query.message.chat.id, doc, snippet.message_id)
    BOT.send_chat_action(cb_query.message.chat.id, 'upload_photo')
    png = mk_png(snippet.text, data['ext'])
    with io.BytesIO(png) as doc:
        doc.name = 'code.png'
        try:
            BOT.send_photo(cb_query.message.chat.id, doc, snippet.message_id)
        except ApiException as e:
            LOG.error("failed to send compressed image", exc_info=e)
            BOT.send_document(cb_query.message.chat.id, doc, snippet.message_id)


if __name__ == '__main__':
    BOT.polling()
