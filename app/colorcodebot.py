#!/usr/bin/env python3
import io
from pathlib import Path

import strictyaml
import structlog
from peewee import IntegerField, CharField
from playhouse.kv import KeyValue
from playhouse.apsw_ext import APSWDatabase
from pygments import formatters, lexers, highlight
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    InputMediaPhoto
)


def yload(yamltxt: str) -> dict:
    return strictyaml.load(yamltxt).data


def ydump(data: dict) -> str:
    return strictyaml.as_document(data).as_yaml()


def load_configs() -> {
    'lang': {str: str},
    'theme_image_ids': [str],
    'kb': {str: InlineKeyboardMarkup},
    'secrets': {str: str}
}:
    data = {}
    data['lang'], secrets, theme_names_ids, syntax_names_exts = (
        yload((Path(__file__).parent / f'{yml}.yml').read_text())
        for yml in ('english', 'vault', 'theme_previews', 'syntaxes')
    )
    data['secrets'] = secrets
    data['theme_image_ids'] = tuple(theme_names_ids.values())
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


def mk_html(code: str, ext: str, theme: str='native') -> str:
    """Return HTML content"""
    return highlight(
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
    return highlight(
        code,
        lexers.get_lexer_by_name(ext),
        formatters.ImageFormatter(
            font_name='Iosevka Custom',
            font_size=35,
            line_number_chars=3,
            style=theme
        )
    )


def minikb(kb_name: str):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(
        '. . .', callback_data=ydump({'action': 'restore', 'kb_name': kb_name})
    ))
    return kb


class ColorCodeBot:

    def __init__(
        self,
        api_key: str,
        lang: {str: str},
        theme_image_ids: [str],
        keyboards: {str: InlineKeyboardMarkup},
        *args,
        admin_chat_id: {str, None}=None,
        db_path: str='user_themes.sqlite',
        **kwargs
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
        self.log = structlog.get_logger()
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

    def switch_from_inline(self, inline_query):
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

    def welcome(self, message):
        self.log.msg(
            "introducing myself",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name
        )
        self.bot.reply_to(message, self.lang['welcome'])

    def browse_themes(self, message):
        self.log.msg(
            "browsing themes",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name
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

    def set_theme(self, cb_query):
        data = yload(cb_query.data)
        self.log.msg(
            "setting theme",
            user_id=cb_query.message.reply_to_message.from_user.id,
            user_first_name=cb_query.message.reply_to_message.from_user.first_name,
            theme=data['theme']
        )
        self.user_themes[cb_query.message.reply_to_message.from_user.id] = data['theme']
        self.bot.reply_to(
            cb_query.message,
            self.lang['acknowledge theme'].format(data['theme'])
        )
        if self.admin_chat_id:
            with open(self.db_path, 'rb') as doc:
                self.bot.send_document(self.admin_chat_id, doc)

    def intake_snippet(self, message):
        self.log.msg(
            "receiving code",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name
        )
        self.bot.reply_to(
            message,
            self.lang['query ext'],
            reply_markup=self.kb['syntax'],
            parse_mode='Markdown',
            disable_web_page_preview=True
        )

    def send_html(self, snippet: Message, ext: str, theme: str='native'):
        self.bot.send_chat_action(snippet.chat.id, 'upload_document')
        self.log.msg('started mk_html')
        html = mk_html(snippet.text, ext, theme)
        self.log.msg('completed mk_html')
        with io.StringIO(html) as doc:
            doc.name = 'code.html'
            self.bot.send_document(
                snippet.chat.id,
                doc,
                reply_to_message_id=snippet.message_id
            )

    def send_image(
        self,
        snippet: Message,
        ext: str,
        theme: str='native',
        max_lines_for_compressed: int=12
    ):
        self.bot.send_chat_action(snippet.chat.id, 'upload_photo')
        self.log.msg('started mk_png')
        png = mk_png(snippet.text, ext, theme)
        self.log.msg('completed mk_png')
        with io.BytesIO(png) as doc:
            doc.name = 'code.png'
            if snippet.text.count('\n') <= max_lines_for_compressed:
                try:
                    self.bot.send_photo(
                        snippet.chat.id,
                        doc,
                        reply_to_message_id=snippet.message_id
                    )
                except ApiException as e:
                    self.log.error("failed to send compressed image", exc_info=e)
                    self.bot.send_document(
                        snippet.chat.id,
                        doc,
                        reply_to_message_id=snippet.message_id
                    )
            else:
                self.bot.send_document(
                    snippet.chat.id,
                    doc,
                    reply_to_message_id=snippet.message_id
                )

    def restore_kb(self, cb_query):
        data = yload(cb_query.data)
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=self.kb[data['kb_name']]
        )

    def set_snippet_filetype(self, cb_query):
        data = yload(cb_query.data)
        self.log.msg(
            "colorizing code",
            user_id=cb_query.message.reply_to_message.from_user.id,
            user_first_name=cb_query.message.reply_to_message.from_user.first_name,
            syntax=data['ext']
        )
        self.bot.edit_message_reply_markup(
            cb_query.message.chat.id,
            cb_query.message.message_id,
            reply_markup=minikb('syntax')
        )
        snippet = cb_query.message.reply_to_message
        theme = self.user_themes.get(cb_query.message.reply_to_message.from_user.id, 'native')
        self.send_html(snippet, data['ext'], theme)
        self.send_image(snippet, data['ext'], theme)

    def recv_photo(self, message):
        self.log.msg('received photo', file_id=message.photo[0].file_id)


if __name__ == '__main__':
    cfg = load_configs()
    ColorCodeBot(
        api_key=cfg['secrets']['TG_API_KEY'],
        admin_chat_id=cfg['secrets'].get('ADMIN_CHAT_ID'),
        lang=cfg['lang'],
        theme_image_ids=cfg['theme_image_ids'],
        keyboards=cfg['kb'],
    ).bot.polling()
