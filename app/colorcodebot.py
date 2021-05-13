#!/usr/bin/env python3
import functools
import io
import os
from pathlib import Path
from time import sleep
from typing import Any, Callable, Iterable, List, Mapping, Optional, Union

import strictyaml
import structlog
from peewee import CharField, IntegerField
from playhouse.apsw_ext import APSWDatabase
from playhouse.kv import KeyValue
from pygments import formatters, highlight, lexers
from requests.exceptions import ConnectionError
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQuery, InputMediaPhoto, Message
)
from wrapt import decorator

WraptFunc = Callable[[Callable, Any, Iterable, Mapping], Callable]


def yload(yamltxt: str) -> Union[str, List, Mapping]:
    return strictyaml.load(yamltxt).data


def ydump(data: Mapping) -> str:
    return strictyaml.as_document(data).as_yaml()


def load_configs() -> {
    'lang':             Mapping[str, str],
    'theme_image_ids':  Iterable[str],
    'kb':               Mapping[str, InlineKeyboardMarkup]
}:
    data = {}
    (
        data['lang'],
        theme_names_ids,
        syntax_names_exts
    ) = (
        yload((Path(__file__).parent / f'{yml}.yml').read_text())
        for yml in (
            'english',
            'theme_previews',
            'syntaxes'
        )
    )

    data['theme_image_ids'] = theme_names_ids.values()

    kb_theme = InlineKeyboardMarkup()
    kb_theme.add(*(InlineKeyboardButton(
        name, callback_data=ydump({'action': 'set theme', 'theme': name})
    ) for name in theme_names_ids.keys()))
    kb_syntax = InlineKeyboardMarkup()
    kb_syntax.add(*(InlineKeyboardButton(
        name, callback_data=ydump({'action': 'set ext', 'ext': ext})
    ) for name, ext in syntax_names_exts.items()))
    data['kb'] = {'theme': kb_theme, 'syntax': kb_syntax}

    return data


def mk_html(code: str, ext: str, theme: str = 'native') -> str:
    """Return generated HTML content"""
    return highlight(
        code,
        lexers.get_lexer_by_name(ext),
        formatters.HtmlFormatter(
            linenos='table',
            full=True,
            style=theme
        )
    )


def mk_png(code: str, ext: str, theme: str = 'native') -> str:
    """Return generated PNG content"""
    return highlight(
        code,
        lexers.get_lexer_by_name(ext),
        formatters.ImageFormatter(
            font_name='Iosevka Term Custom',
            font_size=35,
            line_number_chars=3,
            style=theme
        )
    )


def minikb(kb_name: str) -> InlineKeyboardMarkup:
    """
    Return an inline KB with just one button,
    which restores the specified KB by name when pressed.
    """
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        '. . .', callback_data=ydump({'action': 'restore', 'kb_name': kb_name})
    ))
    return kb


def retry(
    original: Callable = None,  # needed to make args altogether optional
    exceptions: Union[Exception, Iterable[Exception]] = ConnectionError,
    attempts: int = 6,
    seconds: float = 3
) -> WraptFunc:

    if not original:  # needed to make args altogether optional
        return functools.partial(
            retry, exceptions=exceptions, attempts=attempts, seconds=seconds
        )

    @decorator
    def wrapper(original, instance, args, kwargs):
        has_logger = (
            hasattr(instance, 'log')
            and hasattr(instance.log, 'bind')
            and hasattr(instance.log, 'msg')
        )
        last_error = None
        if has_logger:
            log = instance.log.bind(method=original.__name__)
        for attempt in range(attempts):
            try:
                resp = original(*args, **kwargs)
            except exceptions as e:
                last_error = e
                if has_logger:
                    log = log.bind(exc_info=e)
                    # exc_info will get overwritten by most recent attempt
                sleep(seconds)
            else:
                last_error = None
                break
        if has_logger:
            log.msg("called retry-able", retries=attempt, success=not last_error)
        if last_error:
            raise last_error
        return resp
    # return wrapper
    return wrapper(original)  # needed to make args altogether optional


def mk_logger(json=True):
    structlog.configure(processors=[
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(sort_keys=True) if json
        else structlog.dev.ConsoleRenderer()
    ])
    return structlog.get_logger()


class ColorCodeBot:

    def __init__(
        self,
        api_key: str,
        lang: Mapping[str, str],
        theme_image_ids: Iterable[str],
        keyboards: Mapping[str, InlineKeyboardMarkup],
        *args: Any,
        admin_chat_id: Optional[str] = None,
        db_path: str = str((Path(__file__).parent / 'user_themes.sqlite').absolute()),
        **kwargs: Any
    ):
        self.lang = lang
        self.theme_image_ids = theme_image_ids
        self.kb = keyboards
        self.admin_chat_id = admin_chat_id
        self.db_path = db_path
        self.user_themes = KeyValue(
            key_field=IntegerField(primary_key=True),
            value_field=CharField(),
            database=APSWDatabase(db_path)
        )
        self.log = mk_logger()
        self.bot = TeleBot(api_key, *args, **kwargs)
        self.register_handlers()

    def register_handlers(self):
        self.welcome              = self.bot.message_handler(commands=['start', 'help'])(self.welcome)
        self.browse_themes        = self.bot.message_handler(commands=['theme', 'themes'])(self.browse_themes)
        self.intake_snippet       = self.bot.message_handler(func=lambda m: m.content_type == 'text')(self.intake_snippet)
        self.recv_photo           = self.bot.message_handler(content_types=['photo'])(self.recv_photo)
        self.switch_from_inline   = self.bot.inline_handler(lambda q: True)(self.switch_from_inline)
        self.restore_kb           = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'restore')(self.restore_kb)
        self.set_snippet_filetype = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')(self.set_snippet_filetype)
        self.set_theme            = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set theme')(self.set_theme)

    @retry
    def switch_from_inline(self, inline_query: InlineQuery):
        self.log.msg(
            "receiving inline query",
            user_id=inline_query.from_user.id,
            user_first_name=inline_query.from_user.first_name,
            query=inline_query.query
        )
        self.bot.answer_inline_query(
            inline_query.id, [],
            switch_pm_text=self.lang['switch to direct'],
            switch_pm_parameter='x'
        )

    @retry
    def welcome(self, message: Message):
        self.log.msg(
            "introducing myself",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id
        )
        self.bot.reply_to(message, self.lang['welcome'])

    @retry
    def browse_themes(self, message: Message):
        self.log.msg(
            "browsing themes",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id
        )
        self.bot.send_media_group(
            message.chat.id,
            map(InputMediaPhoto, self.theme_image_ids),
            reply_to_message_id=message.message_id
        )
        self.bot.reply_to(
            message,
            self.lang['select theme'],
            reply_markup=self.kb['theme']
        )

    @retry
    def set_theme(self, cb_query: CallbackQuery):
        data = yload(cb_query.data)
        user = cb_query.message.reply_to_message.from_user
        self.log.msg(
            "setting theme",
            user_id=user.id,
            user_first_name=user.first_name,
            theme=data['theme'],
            chat_id=message.chat.id
        )
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=minikb('theme')
        )
        self.user_themes[user.id] = data['theme']
        self.bot.answer_callback_query(
            cb_query.id,
            text=self.lang['acknowledge theme'].format(data['theme'])
        )
        if self.admin_chat_id:
            with open(self.db_path, 'rb') as doc:
                self.bot.send_document(self.admin_chat_id, doc)

    @retry
    def intake_snippet(self, message: Message):
        self.log.msg(
            "receiving code",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id
        )
        self.bot.reply_to(
            message,
            self.lang['query ext'],
            reply_markup=self.kb['syntax'],
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    @retry
    def send_html(self, snippet: Message, ext: str, theme: str = 'native'):
        self.bot.send_chat_action(snippet.chat.id, 'upload_document')
        html = mk_html(snippet.text, ext, theme)
        with io.StringIO(html) as doc:
            doc.name = 'code.html'
            self.bot.send_document(
                snippet.chat.id,
                doc,
                reply_to_message_id=snippet.message_id
            )

    @retry
    def send_image(
        self,
        snippet: Message,
        ext: str,
        theme: str = 'native',
        max_lines_for_compressed: int = 12
    ):
        self.bot.send_chat_action(snippet.chat.id, 'upload_photo')
        png = mk_png(snippet.text, ext, theme)
        if snippet.text.count('\n') <= max_lines_for_compressed:
            try:
                with io.BytesIO(png) as doc:
                    doc.name = 'code.png'
                    self.bot.send_photo(
                        snippet.chat.id,
                        doc,
                        reply_to_message_id=snippet.message_id
                    )
            except ApiException as e:
                self.log.error(
                    "failed to send compressed image",
                    exc_info=e,
                    chat_id=snippet.chat.id
                )
                with io.BytesIO(png) as doc:
                    doc.name = 'code.png'
                    self.bot.send_document(
                        snippet.chat.id,
                        doc,
                        reply_to_message_id=snippet.message_id
                    )
        else:
            with io.BytesIO(png) as doc:
                doc.name = 'code.png'
                self.bot.send_document(
                    snippet.chat.id,
                    doc,
                    reply_to_message_id=snippet.message_id
                )

    @retry
    def restore_kb(self, cb_query: CallbackQuery):
        data = yload(cb_query.data)
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=self.kb[data['kb_name']]
        )
        self.bot.answer_callback_query(cb_query.id)

    @retry
    def set_snippet_filetype(self, cb_query: CallbackQuery):
        data = yload(cb_query.data)
        self.log.msg(
            "colorizing code",
            user_id=cb_query.message.reply_to_message.from_user.id,
            user_first_name=cb_query.message.reply_to_message.from_user.first_name,
            syntax=data['ext'],
            chat_id=cb_query.message.chat.id
        )
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=minikb('syntax')
        )
        snippet = cb_query.message.reply_to_message
        theme = self.user_themes.get(snippet.from_user.id, 'native')
        self.send_html(snippet, data['ext'], theme)
        self.send_image(snippet, data['ext'], theme)
        self.bot.answer_callback_query(cb_query.id)

    def recv_photo(self, message: Message):
        self.log.msg(
            'received photo',
            file_id=message.photo[0].file_id,
            chat_id=message.chat.id
        )


if __name__ == '__main__':
    cfg = load_configs()
    ColorCodeBot(
        api_key=os.environ['TG_API_KEY'],
        admin_chat_id=os.environ.get('ADMIN_CHAT_ID'),
        lang=cfg['lang'],
        theme_image_ids=cfg['theme_image_ids'],
        keyboards=cfg['kb'],
    ).bot.polling()
