#!/usr/bin/env python3
import io
from pathlib import Path

# from joblib import Parallel, delayed
import strictyaml
import structlog
from peewee import IntegerField, CharField
from playhouse.kv import KeyValue
from playhouse.apsw_ext import APSWDatabase
from pygments import formatters, lexers, highlight
from telebot import TeleBot
from telebot.apihelper import ApiException
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, InputMediaPhoto


def yload(yamltxt: str) -> dict:
    return strictyaml.load(yamltxt).data


def ydump(data: dict) -> str:
    return strictyaml.as_document(data).as_yaml()


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


class ColorCodeBot:

    def __init__(self, api_key: str, *args, admin_chat_id: {str, None}=None, **kwargs):
        self.bot = TeleBot(api_key, *args, **kwargs)
        self.ADMIN_CHAT_ID = admin_chat_id
        appdir = Path(__file__).parent
        self.THEME_PREVIEWS = yload((appdir / 'theme_previews.yml').read_text())
        self.LANG = yload((appdir / 'english.yml').read_text())
        self.SYNTAXES = yload((appdir / 'syntaxes.yml').read_text())
        self.log = structlog.get_logger()
        self.user_themes = KeyValue(
            key_field=IntegerField(primary_key=True),
            value_field=CharField(),
            database=APSWDatabase('user_themes.sqlite')
        )
        self.register_handlers()

    def register_handlers(self):
        self.switch_from_inline = self.bot.inline_handler(lambda q: True)(self.switch_from_inline)
        self.welcome = self.bot.message_handler(commands=['start', 'help'])(self.welcome)
        self.browse_themes = self.bot.message_handler(commands=['theme', 'themes'])(self.browse_themes)
        self.set_theme = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set theme')(self.set_theme)
        self.intake_snippet = self.bot.message_handler(func=lambda m: m.content_type == 'text')(self.intake_snippet)
        self.set_snippet_filetype = self.bot.callback_query_handler(lambda q: yload(q.data)['action'] == 'set ext')(self.set_snippet_filetype)
        self.recv_photo = self.bot.message_handler(content_types=['photo'])(self.recv_photo)

    def switch_from_inline(self, inline_query):
        self.log.msg(
            "receiving inline query",
            user_id=inline_query.from_user.id,
            user_first_name=inline_query.from_user.first_name,
            query=inline_query.query
        )
        self.bot.answer_inline_query(
            inline_query.id, [],
            switch_pm_text=self.LANG['switch to direct'], switch_pm_parameter='x'
        )

    def welcome(self, message):
        self.log.msg(
            "introducing myself",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name
        )
        self.bot.reply_to(message, self.LANG['welcome'])

    def browse_themes(self, message):
        self.log.msg(
            "browsing themes",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name
        )
        self.bot.send_media_group(
            message.chat.id,
            map(InputMediaPhoto, self.THEME_PREVIEWS.values()),
            reply_to_message_id=message.message_id
        )
        kb = InlineKeyboardMarkup()
        kb.add(*(
            InlineKeyboardButton(
                name, callback_data=ydump({'action': 'set theme', 'theme': name})
            ) for name in self.THEME_PREVIEWS.keys()
        ))
        self.bot.reply_to(message, self.LANG['select theme'], reply_markup=kb)

    def set_theme(self, cb_query):
        data = yload(cb_query.data)
        self.log.msg(
            "setting theme",
            user_id=cb_query.message.reply_to_message.from_user.id,
            user_first_name=cb_query.message.reply_to_message.from_user.first_name,
            theme=data['theme']
        )
        self.user_themes[cb_query.message.reply_to_message.from_user.id] = data['theme']
        self.bot.reply_to(cb_query.message, self.LANG['acknowledge theme'].format(data['theme']))
        if self.ADMIN_CHAT_ID:
            with open('user_themes.sqlite', 'rb') as doc:
                self.bot.send_document(self.ADMIN_CHAT_ID, doc)

    def intake_snippet(self, message):
        self.log.msg(
            "receiving code",
            user_id=message.from_user.id,
            user_first_name=message.from_user.first_name
        )
        kb = InlineKeyboardMarkup()
        kb.add(*(
            InlineKeyboardButton(
                name, callback_data=ydump({'action': 'set ext', 'ext': ext})
            ) for name, ext in self.SYNTAXES.items()
        ))
        self.bot.reply_to(message, self.LANG['query ext'], reply_markup=kb)

    def send_html(self, snippet: Message, ext: str, theme: str='native'):
        self.bot.send_chat_action(snippet.chat.id, 'upload_document')
        self.log.msg('started mk_html')
        html = mk_html(snippet.text, ext, theme)
        self.log.msg('completed mk_html')
        with io.StringIO(html) as doc:
            doc.name = 'code.html'
            self.bot.send_document(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)

    def send_image(self, snippet: Message, ext: str, theme: str='native', max_lines_for_compressed: int=80):
        self.bot.send_chat_action(snippet.chat.id, 'upload_photo')
        self.log.msg('started mk_png')
        png = mk_png(snippet.text, ext, theme)
        self.log.msg('completed mk_png')
        with io.BytesIO(png) as doc:
            doc.name = 'code.png'
            if snippet.text.count('\n') <= max_lines_for_compressed:
                try:
                    self.bot.send_photo(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)
                except ApiException as e:
                    self.log.error("failed to send compressed image", exc_info=e)
                    self.bot.send_document(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)
            else:
                self.bot.send_document(snippet.chat.id, doc, reply_to_message_id=snippet.message_id)

    def set_snippet_filetype(self, cb_query):
        data = yload(cb_query.data)
        self.log.msg(
            "colorizing code",
            user_id=cb_query.message.reply_to_message.from_user.id,
            user_first_name=cb_query.message.reply_to_message.from_user.first_name,
            syntax=data['ext']
        )
        snippet = cb_query.message.reply_to_message
        theme = self.user_themes.get(cb_query.message.reply_to_message.from_user.id, 'native')
        # Parallel(n_jobs=2, backend="threading")(
        #     delayed(snd)(snippet, data['ext'], theme)
        #     for snd in (self.send_html, self.send_image)
        # )
        self.send_html(snippet, data['ext'], theme)
        self.send_image(snippet, data['ext'], theme)

    def recv_photo(self, message):
        self.log.msg('received photo', file_id=message.photo[0].file_id)


if __name__ == '__main__':
    secrets = yload((Path(__file__).parent / 'vault.yml').read_text())
    ColorCodeBot(secrets['TG_API_KEY'], admin_chat_id=secrets['ADMIN_CHAT_ID']).bot.polling()

