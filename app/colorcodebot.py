#!/usr/bin/env python3
import io

import pygments
import strictyaml
import structlog

from peewee import IntegerField, CharField
from playhouse.kv import KeyValue
from playhouse.apsw_ext import APSWDatabase
from pygments import formatters, lexers
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, InputMediaPhoto

from vault import TG_API_KEY, ADMIN_CHAT_ID


LANG = {
    'welcome': (
        "Hello! Send me a snippet of code as your message text, "
        "and I'll send you a colorized HTML file."
    ),
    'query ext': (
        "Fantastic! What type of code is this?\n\n"
        "To add more types, message @andykluger."
    ),
    'switch to direct': "Let's color some code!",
    'select theme': "Which theme should we use?",
    'acknowledge theme': "Right on, your theme is now {}!"
}


THEME_PREVIEWS = {
    'fruity': 'AgADAQAD16cxG6740EbLRtkzb4IjE2N9DDAABP12cwlgnA3FbUIBAAEC',
    'monokai': 'AgADAQAD2KcxG6740EbUclJ3FAZihZzuCjAABPFe3tdMfu9Aih4AAgI',
    'native': 'AgADAQAD2acxG6740EZXZlZ6Mcu9jJFrDDAABPUd8ym4FCHpbjkBAAEC',
    'paraiso-dark': 'AgADAQADBKgxG2L70UZ9oGAV3e3mEK8sAzAABEXw70NhrDkAAVwQAgABAg',
    'paraiso-light': 'AgADAQADBagxG2L70UbCrGikx5AIk1NmAzAABG_AdzOOepiiLR8AAgI',
    'perldoc': 'AgADAQAD2qcxG6740EZfoPhbCzL-flJ1DDAABJM5f6Za8wOdsD8BAAEC',
    'tango': 'AgADAQADBqgxG2L70UbZ31ds6VjfJuqxCjAABId5KwXH50Q_IWgAAgI',
    'vim': 'AgADAQADB6gxG2L70UbXgz-9lLxTHKorAzAABKwFyXeR7JAdZggCAAEC',
    'vs': 'AgADAQADCKgxG2L70UZZOnXzVkGNxfca9y8ABHP076VPTwNdI9gCAAEC',
    'xcode': 'AgADAQADCagxG2L70Ub_89UsAAGWzL1m7AowAARha7vVB_I1zHUfAAIC'
}


SYNTAXES = (
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
    ('Python', 'py3'),
    ('Ruby', 'rb'),
    ('Rust', 'rust'),
    ('Swift', 'swift')
)


USER_THEMES = KeyValue(
    key_field=IntegerField(primary_key=True),
    value_field=CharField(),
    database=APSWDatabase('user_themes.sqlite')
)


LOG = structlog.get_logger()


BOT = TeleBot(TG_API_KEY)


def yload(yamltxt: str) -> dict:
    return strictyaml.load(yamltxt).data


def ydump(data: dict) -> str:
    return strictyaml.as_document(data).as_yaml()


def mk_html(code: str, ext: str, theme: str='native') -> str:
    """Return HTML content"""
    return pygments.highlight(
        code,
        lexers.get_lexer_by_name(ext),
        formatters.HtmlFormatter(
            linenos='table',
            full=True,
            style=theme
        )
    )


def mk_png(code: str, ext: str, theme: str='native') -> str:
    """Return path of generated png"""
    return pygments.highlight(
        code,
        lexers.get_lexer_by_name(ext),
        formatters.ImageFormatter(
            font_name='Iosevka Custom',
            font_size=35,
            line_number_chars=3,
            style=theme
        )
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


@BOT.message_handler(commands=['theme', 'themes'])
def browse_themes(message):
    LOG.msg(
        "browsing themes",
        user_id=message.from_user.id,
        user_first_name=message.from_user.first_name
    )
    BOT.send_media_group(
        message.chat.id,
        map(InputMediaPhoto, THEME_PREVIEWS.values()),
        reply_to_message_id=message.message_id
    )
    kb = InlineKeyboardMarkup()
    kb.add(*(
        InlineKeyboardButton(
            name, callback_data=ydump({'action': 'set theme', 'theme': name})
        ) for name in THEME_PREVIEWS.keys()
    ))
    BOT.reply_to(message, LANG['select theme'], reply_markup=kb)


@BOT.callback_query_handler(lambda q: yload(q.data)['action'] == 'set theme')
def set_theme(cb_query):
    data = yload(cb_query.data)
    LOG.msg(
        "setting theme",
        user_id=cb_query.message.reply_to_message.from_user.id,
        user_first_name=cb_query.message.reply_to_message.from_user.first_name,
        theme=data['theme']
    )
    USER_THEMES[cb_query.message.reply_to_message.from_user.id] = data['theme']
    BOT.reply_to(cb_query.message, LANG['acknowledge theme'].format(data['theme']))
    if ADMIN_CHAT_ID:
        with open('user_themes.sqlite', 'rb') as doc:
            BOT.send_document(ADMIN_CHAT_ID, doc)


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
        ) for name, ext in SYNTAXES
    ))
    BOT.reply_to(message, LANG['query ext'], reply_markup=kb)


def send_html(snippet: Message, ext: str, theme: str='native'):
    BOT.send_chat_action(snippet.chat.id, 'upload_document')
    html = mk_html(snippet.text, ext, theme)
    with io.StringIO(html) as doc:
        doc.name = 'code.html'
        BOT.send_document(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)


def send_image(snippet: Message, ext: str, theme: str='native', max_lines_for_compressed: int=80):
    BOT.send_chat_action(snippet.chat.id, 'upload_photo')
    png = mk_png(snippet.text, ext, theme)
    with io.BytesIO(png) as doc:
        doc.name = 'code.png'
        if snippet.text.count('\n') <= max_lines_for_compressed:
            try:
                BOT.send_photo(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)
            except ApiException as e:
                LOG.error("failed to send compressed image", exc_info=e)
                BOT.send_document(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)
        else:
            BOT.send_document(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)


@BOT.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')
def set_snippet_filetype(cb_query):
    data = yload(cb_query.data)
    LOG.msg(
        "colorizing code",
        user_id=cb_query.message.reply_to_message.from_user.id,
        user_first_name=cb_query.message.reply_to_message.from_user.first_name,
        syntax=data['ext']
    )
    snippet = cb_query.message.reply_to_message
    theme = USER_THEMES.get(cb_query.message.reply_to_message.from_user.id, 'native')
    send_html(snippet, data['ext'], theme)
    send_image(snippet, data['ext'], theme)


@BOT.message_handler(content_types=['photo'])
def recv_photo(message):
    LOG.msg('received photo', file_id=message.photo[0].file_id)


if __name__ == '__main__':
    BOT.polling()
