#!/usr/bin/env python3
import functools
import io
import os
from contextlib import suppress
from threading import Thread
from time import sleep
from typing import Any, Callable, Iterable, List, Mapping, Optional, TypedDict, Union
from uuid import uuid4

import strictyaml
import structlog
from guesslang import Guess
from peewee import BooleanField, CharField, IntegerField
from playhouse.kv import KeyValue
from playhouse.sqliteq import SqliteQueueDatabase as SqliteDatabase
from plumbum import local
from plumbum.cmd import highlight, silicon
from requests.exceptions import ConnectionError
from structlog.types import BindableLogger
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import (
    CallbackQuery, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQuery, InlineQueryResultCachedPhoto, InputMediaPhoto, Message
)
from wrapt import decorator

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


BEGONE_BUTTON = InlineKeyboardButton('🗑️', callback_data=ydump({'action': 'begone'}))

BEGONE_KB = InlineKeyboardMarkup()
BEGONE_KB.add(BEGONE_BUTTON)

BG_IMAGE = str(local.path(__file__).up() / 'sharon-mccutcheon-33xSu0EWgP4-unsplash.jpg')


def is_from_group_admin_or_creator(bot, message_or_query: Union[Message, CallbackQuery]):
    if isinstance(message_or_query, Message):
        message = message_or_query
        return message.chat.type == 'private' or bot.get_chat_member(
            message.chat.id, message.from_user.id
        ).status in ('administrator', 'creator')
    elif isinstance(message_or_query, CallbackQuery):
        query = message_or_query
        return query.message.chat.type == 'private' or bot.get_chat_member(
            query.message.chat.id, query.from_user.id
        ).status in ('administrator', 'creator')


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
        ],
        BEGONE_BUTTON,
    )

    kb_syntax = InlineKeyboardMarkup()
    kb_syntax.add(
        *[
            InlineKeyboardButton(
                name, callback_data=ydump({'action': 'set ext', 'ext': ext})
            )
            for name, ext in syntax_names_exts.items()
        ],
        BEGONE_BUTTON,
    )

    kb_group_syntax = InlineKeyboardMarkup()
    kb_group_syntax.add(
        *[
            InlineKeyboardButton(
                name, callback_data=ydump({'action': 'set default ext', 'ext': ext})
            )
            for name, ext in syntax_names_exts.items()
        ],
        InlineKeyboardButton(
            "None", callback_data=ydump({'action': 'set default ext', 'ext': ''})
        ),
        BEGONE_BUTTON,
    )

    kb_group_options = InlineKeyboardMarkup()
    kb_group_options.add(
        InlineKeyboardButton(
            data['lang']['select default syntax'],
            callback_data=ydump({'action': 'browse group syntax'}),
        ),
        InlineKeyboardButton(
            data['lang']['toggle watch mode'],
            callback_data=ydump({'action': 'toggle watch mode'}),
        ),
        BEGONE_BUTTON,
    )

    data['kb'] = {
        'theme': kb_theme,
        'syntax': kb_syntax,
        'group options': kb_group_options,
        'group syntax': kb_group_syntax,
    }

    return data


def mk_html(code: str, ext: str, theme: str = 'base16/bright') -> str:
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


def mk_png(code: str, ext: str, theme: str = 'Coldark-Dark', folder=None) -> str:
    """Return generated PNG file path"""
    folder = (local.path(folder) if folder else local.path('/tmp/ccb_png')) / uuid4()
    folder.mkdir()

    # TODO: test all ext values...

    png = folder / f'{uuid4()}.png'
    # fmt: off
    (
        silicon[
            '-o', png,
            '-l', ext,
            '--theme', theme,
            '--pad-horiz', 20,
            '--pad-vert', 25,
            '--shadow-blur-radius', 5,
            '--background-image', BG_IMAGE,
            '-f', '; '.join((
                'Iosevka Term Custom',
                'Symbols Nerd Font',
                'NanumGothicCoding',
                'OpenMoji',
            ))
        ]
        << code
    )()
    # fmt: on

    return str(png)


def minikb(kb_name: str, mini_text: str = '. . .') -> InlineKeyboardMarkup:
    """
    Return an inline KB with just one button,
    which restores the specified KB by name when pressed.
    """
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton(
            mini_text, callback_data=ydump({'action': 'restore', 'kb_name': kb_name})
        ),
        BEGONE_BUTTON,
    )
    return kb


def retry(
    original: Callable = None,  # needed to make args altogether optional
    exceptions: Union[Exception, Iterable[Exception]] = ConnectionError,
    attempts: int = 6,
    seconds: float = 3,
) -> Union[WraptFunc, functools.partial[WraptFunc]]:

    if not original:  # needed to make args altogether optional
        return functools.partial(
            retry, exceptions=exceptions, attempts=attempts, seconds=seconds
        )

    @decorator
    def wrapper(original, instance, args, kwargs):
        has_logger = isinstance(getattr(instance, 'log', None), BindableLogger)
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


def mk_logger(json=True) -> BindableLogger:
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
        return bot.send_document(
            chat_id, doc, reply_to_message_id=reply_msg_id, reply_markup=BEGONE_KB
        )


@retry
def delete_after_delay(bot, message, delay=60, log: Optional[BindableLogger] = None):
    sleep(delay)
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except ApiException as e:
        if log:
            log.error(
                "failed to delete message (it's probably gone already)",
                exc_info=e,
                chat_id=message.chat.id,
            )


@retry
def send_image(
    bot, chat_id, png_path: str, reply_msg_id=None, log: Optional[BindableLogger] = None
) -> Message:
    bot.send_chat_action(chat_id, 'upload_photo')

    if local.path(png_path).stat().st_size < 300000:
        try:
            with open(png_path, 'rb') as doc:
                return bot.send_photo(chat_id, doc, reply_to_message_id=reply_msg_id)
        except ApiException as e:
            if log:
                log.error(
                    "failed to send compressed image",
                    exc_info=e,
                    chat_id=chat_id,
                )

    with open(png_path, 'rb') as doc:
        return bot.send_document(chat_id, doc, reply_to_message_id=reply_msg_id)


def code_subcontent(message: Message) -> Optional[str]:
    if message.entities:
        code_entities = [e for e in message.entities if e.type in ('code', 'pre')]
        if code_entities:
            code_content = '\n\n'.join(
                message.text[e.offset : e.offset + e.length] for e in code_entities
            )
            if len(code_content.split()) > 1:
                return code_content


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
        db_path: str = str(local.path(__file__).up() / 'db-files' / 'ccb.sqlite'),
        **kwargs: Any,
    ):
        self.lang = lang
        self.theme_image_ids = theme_image_ids
        self.kb = keyboards
        self.guesslang_syntaxes = guesslang_syntaxes
        self.admin_chat_id = admin_chat_id
        self.log = mk_logger()
        self.db_path = db_path
        self.db = SqliteDatabase(self.db_path)
        self.user_themes = KeyValue(
            key_field=IntegerField(primary_key=True),
            value_field=CharField(),
            database=self.db,
            table_name='user_theme',
        )
        self.group_syntaxes = KeyValue(
            key_field=IntegerField(primary_key=True),
            value_field=CharField(),
            database=self.db,
            table_name='group_syntax',
        )
        self.ignore_mode_groups = KeyValue(
            key_field=IntegerField(primary_key=True),
            value_field=BooleanField(),
            database=self.db,
            table_name='group_in_ignore_mode',
        )
        self.group_user_current_watchme_requests = KeyValue(
            key_field=CharField(primary_key=True),
            value_field=CharField(),
            database=self.db,
            table_name='group_user_current_watchme_request',
        )
        self.bot = TeleBot(api_key, *args, **kwargs)
        self.register_handlers()
        self.guesser = Guess()

    def register_handlers(self):
        # fmt: off
        self.welcome              = self.bot.message_handler(commands=['start', 'help'])(self.welcome)
        self.browse_themes        = self.bot.message_handler(commands=['theme', 'themes'])(self.browse_themes)
        self.manage_group_options = self.bot.message_handler(commands=['settings'])(self.manage_group_options)
        self.ignore_group_user    = self.bot.message_handler(commands=['ignoreme'])(self.ignore_group_user)
        self.watch_group_user     = self.bot.message_handler(commands=['watchme'])(self.watch_group_user)
        self.intake_snippet       = self.bot.message_handler(func=lambda m: m.content_type == 'text')(self.intake_snippet)
        self.recv_photo           = self.bot.message_handler(content_types=['photo'])(self.recv_photo)
        self.restore_kb           = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'restore')(self.restore_kb)
        self.set_snippet_filetype = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')(self.set_snippet_filetype)
        self.set_group_syntax     = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set default ext')(self.set_group_syntax)
        self.browse_group_syntax  = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'browse group syntax')(self.browse_group_syntax)
        self.toggle_group_watch   = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'toggle watch mode')(self.toggle_group_watch)
        self.set_theme            = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set theme')(self.set_theme)
        self.begone               = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'begone')(self.begone)
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
            parse_mode='MarkdownV2',
            reply_markup=ForceReply(
                input_field_placeholder=self.lang['input field placeholder']
            ),
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
            msgs = self.bot.send_media_group(
                message.chat.id,
                map(InputMediaPhoto, album),
                reply_to_message_id=message.message_id,
            )
            for msg in msgs:
                Thread(
                    target=delete_after_delay, args=(self.bot, msg, 30, self.log)
                ).start()
        self.bot.reply_to(
            message, self.lang['select theme'], reply_markup=self.kb['theme']
        )

    @retry
    def get_group_config_md(self, chat_id):
        return self.lang['current config'].format(
            default_syntax=str(self.group_syntaxes.get(chat_id)),
            ignore_mode="ignore"
            if self.ignore_mode_groups.get(chat_id, False)
            else "watch",
        )

    @retry
    def manage_group_options(self, message: Message):
        is_admin_or_creator = is_from_group_admin_or_creator(self.bot, message)
        self.log.msg(
            "user requesting group options for viewing or changing",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
            user_is_admin=is_admin_or_creator,
        )
        if is_admin_or_creator:
            self.bot.send_message(
                message.chat.id,
                self.get_group_config_md(message.chat.id),
                parse_mode='MarkdownV2',
                reply_markup=self.kb['group options'],
            )

    @retry
    def browse_group_syntax(self, cb_query: CallbackQuery):
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=self.kb['group syntax'],
        )

    def toggle_group_watch(self, cb_query: CallbackQuery):
        is_admin_or_creator = is_from_group_admin_or_creator(self.bot, cb_query)
        self.log.msg(
            "user trying to toggle group watch mode",
            user_id=cb_query.from_user.id,
            chat_id=cb_query.message.chat.id,
            user_is_admin=is_admin_or_creator,
        )
        if is_admin_or_creator:
            self.ignore_mode_groups[
                cb_query.message.chat.id
            ] = not self.ignore_mode_groups.get(cb_query.message.chat.id, False)
            self.bot.edit_message_text(
                self.get_group_config_md(cb_query.message.chat.id),
                cb_query.message.chat.id,
                cb_query.message.message_id,
                parse_mode='MarkdownV2',
                reply_markup=self.kb['group options'],
            )

    @retry
    def ignore_group_user(self, message: Message):
        self.log.msg(
            "ignoring group user",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )
        self.group_user_current_watchme_requests[
            f"{message.chat.id}:{message.from_user.id}"
        ] = 'ignore'

    @retry
    def watch_group_user(self, message: Message):
        self.log.msg(
            "watching group user",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )
        self.group_user_current_watchme_requests[
            f"{message.chat.id}:{message.from_user.id}"
        ] = 'watch'

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

    @retry
    def begone(self, cb_query: CallbackQuery):
        has_permission = False
        try:
            if cb_query.message.reply_to_message.from_user.id == cb_query.from_user.id:
                has_permission = True
            log = self.log.bind(
                reply_to_msg_user_id=cb_query.message.reply_to_message.from_user.id
            )
        except AttributeError as e:
            has_permission = is_from_group_admin_or_creator(self.bot, cb_query)
            log = self.log.bind(query_is_from_admin=has_permission, exc_info=e)
        log.msg("Got deletion request", user_id=cb_query.from_user.id)
        if has_permission:
            self.bot.delete_message(
                cb_query.message.chat.id, cb_query.message.message_id
            )

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
            '--- ':  'diff',
            '-- ':   'lua',
            '\\':    'tex',
            '[[':    'toml', '[': 'ini',
            '<?php': 'php',  '<': 'xml'
            # fmt: on
        }.items():
            if code.startswith(start):
                self.log.msg("simple-guessed syntax", ext=ext)
                return ext

    @retry
    def intake_snippet(self, message: Message):
        if self.ignore_mode_groups.get(message.chat.id, False):
            if (
                self.group_user_current_watchme_requests.get(
                    f"{message.chat.id}:{message.from_user.id}", 'ignore'
                )
                != 'watch'
            ):
                return
        elif (
            self.group_user_current_watchme_requests.get(
                f"{message.chat.id}:{message.from_user.id}", 'watch'
            )
            == 'ignore'
        ):
            return
        text_content = message.text
        if message.chat.type != 'private':
            text_content = code_subcontent(message)
            if not text_content:
                return
        self.log.msg(
            "receiving code",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name,
            chat_id=message.chat.id,
        )
        ext = self.guess_ext(text_content)
        if not ext:
            with suppress(KeyError):
                ext = self.group_syntaxes[message.chat.id]
        if ext:
            kb_msg = self.bot.reply_to(
                message,
                f"{self.lang['query ext']}\n\n{self.lang['guessed syntax'].format(ext)}",
                reply_markup=minikb('syntax', self.lang['syntax picker']),
                parse_mode='MarkdownV2',
                disable_web_page_preview=True,
            )
            self.set_snippet_filetype(cb_query=None, query_message=kb_msg, ext=ext)
        else:
            kb_msg = self.bot.reply_to(
                message,
                self.lang['query ext'],
                reply_markup=self.kb['syntax'],
                parse_mode='MarkdownV2',
                disable_web_page_preview=True,
            )
        Thread(target=delete_after_delay, args=(self.bot, kb_msg, 30, self.log)).start()

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
    def set_group_syntax(self, cb_query: CallbackQuery):
        ext = yload(cb_query.data)['ext']
        is_admin_or_creator = is_from_group_admin_or_creator(self.bot, cb_query)
        self.log.msg(
            "user trying to set group default syntax",
            ext=ext,
            user_id=cb_query.from_user.id,
            chat_id=cb_query.message.chat.id,
            user_is_admin=is_admin_or_creator,
        )
        if is_admin_or_creator:
            if ext:
                self.group_syntaxes[cb_query.message.chat.id] = ext
            else:
                del self.group_syntaxes[cb_query.message.chat.id]
            self.bot.edit_message_text(
                self.get_group_config_md(cb_query.message.chat.id),
                cb_query.message.chat.id,
                cb_query.message.message_id,
                parse_mode='MarkdownV2',
                reply_markup=self.kb['group options'],
            )

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
            self.bot.edit_message_reply_markup(
                query_message.chat.id,
                query_message.message_id,
                reply_markup=minikb('syntax', self.lang['syntax picker']),
            )
        elif not (query_message and ext):
            raise Exception("Either cb_query or both query_message and ext are required")

        self.log.msg(
            "colorizing code",
            user_id=query_message.reply_to_message.from_user.id,
            user_first_name=query_message.reply_to_message.from_user.first_name,
            syntax=ext,
            chat_id=query_message.chat.id,
        )

        snippet = query_message.reply_to_message
        text_content = snippet.text
        do_send_html, do_send_image_dark, do_send_image_light, do_attach_send_kb = (
            True,
        ) * 4
        if snippet.chat.type != 'private':
            text_content = code_subcontent(snippet)
            do_send_html, do_send_image_light, do_attach_send_kb = (False,) * 3
        theme = self.user_themes.get(snippet.from_user.id, 'base16/bright')

        if do_send_html:
            html = mk_html(text_content, ext, theme)
            send_html(
                bot=self.bot,
                chat_id=snippet.chat.id,
                html=html,
                reply_msg_id=snippet.message_id,
            )

        themes = []
        if do_send_image_dark:
            themes.append('Coldark-Dark')
        if do_send_image_light:
            themes.append('Coldark-Cold')
        with local.tempdir() as folder:
            for theme in themes:
                png_path = mk_png(text_content, ext, theme, folder=folder)
                photo_msg = send_image(
                    bot=self.bot,
                    chat_id=snippet.chat.id,
                    png_path=png_path,
                    reply_msg_id=snippet.message_id,
                )
                image_kb = InlineKeyboardMarkup()
                if do_attach_send_kb and photo_msg.content_type == 'photo':
                    image_kb.add(
                        InlineKeyboardButton(
                            self.lang['send to chat'],
                            switch_inline_query=f"img {photo_msg.photo[-1].file_id}",
                        )
                    )
                image_kb.add(BEGONE_BUTTON)
                self.bot.edit_message_reply_markup(
                    photo_msg.chat.id,
                    photo_msg.message_id,
                    reply_markup=image_kb,
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
