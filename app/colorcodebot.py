#!/usr/bin/env python3
import functools
import io
import os
from itertools import chain
from textwrap import dedent
from time import sleep
from typing import Any, Callable, Iterable, List, Mapping, Optional, TypedDict, Union
from uuid import uuid4

import strictyaml
import structlog
from guesslang import Guess
from peewee import CharField, IntegerField
from playhouse.apsw_ext import APSWDatabase
from playhouse.kv import KeyValue
from plumbum import CommandNotFound, local
from plumbum.cmd import highlight
from requests.exceptions import ConnectionError
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import (
    CallbackQuery, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQuery, InlineQueryResultCachedPhoto, InputMediaPhoto, Message
)
from weasyprint import HTML
from wrapt import decorator

try:
    convert = local['gm']['convert']
except CommandNotFound:
    convert = local['convert']

WraptFunc = Callable[[Callable, Any, Iterable, Mapping], Callable]


class Config(TypedDict):
    lang: Mapping[str, str]
    theme_image_ids: tuple[str]
    kb: Mapping[str, InlineKeyboardMarkup]
    guesslang: Mapping[str, str]


def yload(yamltxt: str) -> Union[str, List, Mapping]:
    return strictyaml.load(yamltxt).data


def ydump(data: Mapping) -> str:
    return strictyaml.as_document(data).as_yaml()


def load_configs() -> Config:
    data = {}
    (data['lang'], theme_names_ids, syntax_names_exts, data['guesslang']) = (
        yload((local.path(__file__).up() / f'{yml}.yml').read())
        if (local.path(__file__).up() / f'{yml}.yml').exists()
        else {}
        for yml in ('english', 'theme_previews', 'syntaxes', 'guesslang')
    )

    data['theme_image_ids'] = tuple(theme_names_ids.values())

    kb_theme = InlineKeyboardMarkup()

    kb_theme.add(
        *[
            InlineKeyboardButton(
                name, callback_data=ydump({'action': 'set theme', 'theme': name})
            )
            for name in theme_names_ids.keys()
        ]
    )

    kb_syntax = InlineKeyboardMarkup()

    kb_syntax.add(
        *[
            InlineKeyboardButton(
                name, callback_data=ydump({'action': 'set ext', 'ext': ext})
            )
            for name, ext in syntax_names_exts.items()
        ]
    )

    data['kb'] = {'theme': kb_theme, 'syntax': kb_syntax}

    return data


def mk_html(code: str, ext: str, theme: str = 'base16/gruvbox-dark-hard') -> str:
    """Return generated HTML content"""
    return (
        highlight[
            f"--syntax={ext}",
            f"--style={theme}",
            '--line-numbers',
            '--out-format=html',
            '--include-style',
            '--encoding=UTF-8',
            (
                '--font=ui-monospace,monospace,mono'
                ',monaco'
                ',Consolas'
                ',Andale Mono,AndaleMono'
                ',Lucida Console'
                ',Lucida Sans Typewriter'
                ',Lucida Typewriter'
                ',Courier New'
                ',Courier'
                ',Bitstream Vera Sans Mono'
            ),
        ]
        << code
    )()


def mk_png(html: str, folder=None) -> str:
    """Return generated PNG file path"""
    folder = (local.path(folder) if folder else local.path('/tmp/ccb_png')) / uuid4()
    folder.mkdir()
    png = folder / 'code.png'
    (
        convert['-trim', '-trim', '-', png]
        << HTML(string=html, media_type='screen').write_png(resolution=384)
    )()
    return png


def minikb(kb_name: str, mini_text: str = '. . .') -> InlineKeyboardMarkup:
    """
    Return an inline KB with just one button,
    which restores the specified KB by name when pressed.
    """
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            mini_text, callback_data=ydump({'action': 'restore', 'kb_name': kb_name})
        )
    )
    return kb


def retry(
    original: Callable = None,  # needed to make args altogether optional
    exceptions: Union[Exception, Iterable[Exception]] = ConnectionError,
    attempts: int = 6,
    seconds: float = 3,
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
        if has_logger and attempt > 0:
            log.msg("called retry-able", retries=attempt, success=not last_error)
        if last_error:
            raise last_error
        return resp

    # return wrapper
    return wrapper(original)  # needed to make args altogether optional


def mk_logger(json=True):
    structlog.configure(
        processors=[
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(sort_keys=True)
            if json
            else structlog.dev.ConsoleRenderer(),
        ]
    )
    return structlog.get_logger()


@retry
def send_html(bot, chat_id, html: str, reply_msg_id=None) -> Message:
    bot.send_chat_action(chat_id, 'upload_document')
    with io.StringIO(html) as doc:
        doc.name = 'code.html'
        return bot.send_document(chat_id, doc, reply_to_message_id=reply_msg_id)


@retry
def send_image(bot, chat_id, png_path: str, reply_msg_id=None, compress=True) -> Message:
    bot.send_chat_action(chat_id, 'upload_photo')
    with open(png_path, 'rb') as doc:
        if compress:
            return bot.send_photo(chat_id, doc, reply_to_message_id=reply_msg_id)
        else:
            return bot.send_document(chat_id, doc, reply_to_message_id=reply_msg_id)


class ColorCodeBot:
    def __init__(
        self,
        api_key: str,
        lang: Mapping[str, str],
        theme_image_ids: tuple[str],
        keyboards: Mapping[str, InlineKeyboardMarkup],
        guesslang_syntaxes: Mapping[str, str],
        *args: Any,
        admin_chat_id: Optional[str] = None,
        db_path: str = str(local.path(__file__).up() / 'user_themes.sqlite'),
        **kwargs: Any,
    ):
        self.lang = lang
        self.theme_image_ids = theme_image_ids
        self.kb = keyboards
        self.guesslang_syntaxes = guesslang_syntaxes
        self.admin_chat_id = admin_chat_id
        self.db_path = db_path
        self.user_themes = KeyValue(
            key_field=IntegerField(primary_key=True),
            value_field=CharField(),
            database=APSWDatabase(db_path),
        )
        self.log = mk_logger()
        self.bot = TeleBot(api_key, *args, **kwargs)
        self.register_handlers()
        self.guesser = Guess()

    def register_handlers(self):
        # fmt: off
        self.welcome              = self.bot.message_handler(commands=['start', 'help'])(self.welcome)
        self.browse_themes        = self.bot.message_handler(commands=['theme', 'themes'])(self.browse_themes)
        self.mk_theme_previews    = self.bot.message_handler(commands=['previews'])(self.mk_theme_previews)
        self.intake_snippet       = self.bot.message_handler(func=lambda m: m.content_type == 'text')(self.intake_snippet)
        self.recv_photo           = self.bot.message_handler(content_types=['photo'])(self.recv_photo)
        self.restore_kb           = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'restore')(self.restore_kb)
        self.set_snippet_filetype = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')(self.set_snippet_filetype)
        self.set_theme            = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set theme')(self.set_theme)
        self.send_photo_elsewhere = self.bot.inline_handler(lambda q: q.query.startswith("img "))(self.send_photo_elsewhere)
        self.switch_from_inline   = self.bot.inline_handler(lambda q: True)(self.switch_from_inline)
        # fmt: on

    @retry
    def switch_from_inline(self, inline_query: InlineQuery):
        self.log.msg(
            "receiving inline query",
            user_id=inline_query.from_user.id,
            user_first_name=inline_query.from_user.first_name,
            query=inline_query.query,
        )
        self.bot.answer_inline_query(
            inline_query.id,
            [],
            switch_pm_text=self.lang['switch to direct'],
            switch_pm_parameter='x',
        )

    @retry
    def welcome(self, message: Message):
        self.log.msg(
            "introducing myself",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )
        self.bot.reply_to(
            message,
            self.lang['welcome'],
            parse_mode='Markdown',
            reply_markup=ForceReply(
                input_field_placeholder=self.lang['input field placeholder']
            ),
        )

    @retry
    def mk_theme_previews(self, message: Message):
        if not self.admin_chat_id or str(message.chat.id) != self.admin_chat_id:
            self.log.msg(
                "naughty preview attempt",
                user_id=message.from_user.id,
                user_first_name=message.from_user.first_name,
                chat_id=message.chat.id,
                admin_chat_id=self.admin_chat_id,
            )
            return
        sample_code = dedent(
            """
            # palinDay :: Int -> [ISO Date]
            def palinDay(y):
                '''A possibly empty list containing the palindromic
                   date for the given year, if such a date exists.
                '''
                s = str(y)
                r = s[::-1]
                iso = '-'.join([s, r[0:2], r[2:]])
                try:
                    datetime.strptime(iso, '%Y-%m-%d')
                    return [iso]
                except ValueError:
                    return []
        """
        )
        themes = message.text.split()[1:] or [
            btn.text for btn in chain.from_iterable(self.kb['theme'].keyboard)
        ]
        self.log.msg("mk_theme_previews", themes=themes)
        for theme in themes:
            html = mk_html(f"# {theme}{sample_code}", 'py', theme)
            with local.tempdir() as folder:
                png_path = mk_png(html, folder=folder)
                photo_msg = send_image(
                    bot=self.bot,
                    chat_id=message.chat.id,
                    png_path=png_path,
                    reply_msg_id=message.message_id,
                )
            self.log.msg(
                "generated theme preview",
                theme=theme,
                file_id=photo_msg.photo[-1].file_id,
            )

    @retry
    def browse_themes(self, message: Message):
        self.log.msg(
            "browsing themes",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )
        albums = [
            self.theme_image_ids[i : i + 10]
            for i in range(0, len(self.theme_image_ids), 10)
        ]
        for album in albums:
            self.bot.send_media_group(
                message.chat.id,
                map(InputMediaPhoto, album),
                reply_to_message_id=message.message_id,
            )
        self.bot.reply_to(
            message, self.lang['select theme'], reply_markup=self.kb['theme']
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
            chat_id=cb_query.message.chat.id,
        )
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=minikb('theme'),
        )
        self.user_themes[user.id] = data['theme']
        self.bot.answer_callback_query(
            cb_query.id, text=self.lang['acknowledge theme'].format(data['theme'])
        )
        if self.admin_chat_id:
            with open(self.db_path, 'rb') as doc:
                self.bot.send_document(self.admin_chat_id, doc)

    def guess_ext(self, code: str, probability_min: float = 0.12) -> Optional[str]:
        syntax, probability = self.guesser.probabilities(code)[0]
        ext = self.guesslang_syntaxes.get(syntax)
        self.log.msg(
            "guessed syntax",
            probability_min=probability_min,
            probability=probability,
            syntax=syntax,
            ext=ext,
        )
        if probability >= probability_min:
            return ext
        for start, ext in {
            # fmt: off
            '{':     'json',
            '---\n': 'yaml',
            '[[':    'toml', '[': 'ini',
            '<?php': 'php',  '<': 'xml',
            '-- ':   'lua'
            # fmt: on
        }.items():
            if code.startswith(start):
                self.log.msg("simple-guessed syntax", ext=ext)
                return ext

    @retry
    def intake_snippet(self, message: Message):
        self.log.msg(
            "receiving code",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )
        ext = self.guess_ext(message.text)
        if ext:
            kb_msg = self.bot.reply_to(
                message,
                f"{self.lang['query ext']}\n\n{self.lang['guessed syntax'].format(ext)}",
                reply_markup=minikb('syntax', self.lang['syntax picker']),
                parse_mode='Markdown',
                disable_web_page_preview=True,
            )
            self.set_snippet_filetype(cb_query=None, query_message=kb_msg, ext=ext)
        else:
            self.bot.reply_to(
                message,
                self.lang['query ext'],
                reply_markup=self.kb['syntax'],
                parse_mode='Markdown',
                disable_web_page_preview=True,
            )

    @retry
    def send_photo_elsewhere(self, inline_query: InlineQuery):
        file_id = inline_query.query.split('img ', 1)[-1]
        self.log.msg(
            "creating inline query result",
            file_id=file_id,
            file_info=str(self.bot.get_file(file_id)),
        )
        self.bot.answer_inline_query(
            inline_query.id,
            [
                InlineQueryResultCachedPhoto(
                    id=str(uuid4()), photo_file_id=file_id, title="Send Image"
                )
            ],
            is_personal=True,
        )

    @retry
    def restore_kb(self, cb_query: CallbackQuery):
        data = yload(cb_query.data)
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=self.kb[data['kb_name']],
        )
        self.bot.answer_callback_query(cb_query.id)

    @retry
    def set_snippet_filetype(
        self,
        cb_query: Optional[CallbackQuery] = None,
        query_message: Optional[Message] = None,
        ext: Optional[str] = None,
    ):
        if cb_query:
            query_message = cb_query.message
            ext = yload(cb_query.data)['ext']
        elif not (query_message and ext):
            raise Exception("Either cb_query or both query_message and ext are required")
        self.log.msg(
            "colorizing code",
            user_id=query_message.reply_to_message.from_user.id,
            user_first_name=query_message.reply_to_message.from_user.first_name,
            syntax=ext,
            chat_id=query_message.chat.id,
        )
        if cb_query:
            self.bot.edit_message_reply_markup(
                query_message.chat.id,
                query_message.message_id,
                reply_markup=minikb('syntax', self.lang['syntax picker']),
            )
        snippet = query_message.reply_to_message
        theme = self.user_themes.get(snippet.from_user.id, 'base16/gruvbox-dark-hard')

        html = mk_html(snippet.text, ext, theme)
        send_html(
            bot=self.bot,
            chat_id=snippet.chat.id,
            html=html,
            reply_msg_id=snippet.message_id,
        )

        with local.tempdir() as folder:
            png_path = mk_png(html, folder=folder)
            did_send = False
            if len(snippet.text.splitlines()) <= 30:
                try:
                    photo_msg = send_image(
                        bot=self.bot,
                        chat_id=snippet.chat.id,
                        png_path=png_path,
                        reply_msg_id=snippet.message_id,
                    )
                except ApiException as e:
                    self.log.error(
                        "failed to send compressed image",
                        exc_info=e,
                        chat_id=snippet.chat.id,
                    )
                else:
                    did_send = True
                    kb_to_chat = InlineKeyboardMarkup()
                    kb_to_chat.add(
                        InlineKeyboardButton(
                            self.lang['send to chat'],
                            switch_inline_query=f"img {photo_msg.photo[-1].file_id}",
                        )
                    )
                    self.bot.edit_message_reply_markup(
                        photo_msg.chat.id, photo_msg.message_id, reply_markup=kb_to_chat
                    )
            if not did_send:
                send_image(
                    bot=self.bot,
                    chat_id=snippet.chat.id,
                    png_path=png_path,
                    reply_msg_id=snippet.message_id,
                    compress=False,
                )

        if cb_query:
            self.bot.answer_callback_query(cb_query.id)

    def recv_photo(self, message: Message):
        self.log.msg(
            'received photo',
            file_id=message.photo[0].file_id,
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )


if __name__ == '__main__':
    cfg = load_configs()
    ColorCodeBot(
        api_key=os.environ['TG_API_KEY'],
        admin_chat_id=os.environ.get('ADMIN_CHAT_ID'),
        lang=cfg['lang'],
        theme_image_ids=cfg['theme_image_ids'],
        keyboards=cfg['kb'],
        guesslang_syntaxes=cfg['guesslang'],
    ).bot.polling()
