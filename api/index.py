# -*- coding: utf-8 -*-
import os
import sys
import re
from flask import Flask, request, abort, render_template_string
import requests
from bs4 import BeautifulSoup
import telebot

# --- Dict.cc Scraping Logic (Self-contained) ---

AVAILABLE_LANGUAGES = {
    "en": "english",
    "de": "german",
    "fr": "french",
    "sv": "swedish",
    "no": "norwegian (bokmål)",
    "es": "spanish",
    "nl": "dutch",
    "bg": "bulgarian",
    "ro": "romanian",
    "it": "italian",
    "pt": "portuguese",
    "ru": "russian"
}

class UnavailableLanguageError(Exception):
    def __str__(self):
        return "Languages have to be in the following list: {}".format(
            ", ".join(AVAILABLE_LANGUAGES.keys()))

class Result(object):
    def __init__(self, from_lang=None, to_lang=None, translation_tuples=None):
        self.from_lang = from_lang
        self.to_lang = to_lang
        self.translation_tuples = list(translation_tuples) if translation_tuples else []

    @property
    def n_results(self):
        return len(self.translation_tuples)

class DictccScraper(object):
    @classmethod
    def translate(cls, word, from_language, to_language):
        if any(map(lambda l: l.lower() not in AVAILABLE_LANGUAGES.keys(), [from_language, to_language])):
            raise UnavailableLanguageError

        response_body = cls._get_response(word, from_language, to_language)
        result = cls._parse_response(response_body)

        return cls._correct_translation_order(result, word)

    @classmethod
    def _get_response(cls, word, from_language, to_language):
        res = requests.get(
            url="https://" + from_language.lower() + to_language.lower() + ".dict.cc",
            params={"s": word.encode("utf-8")},
            headers={'User-agent': 'Mozilla/5.0 (Windows NT 6.3; WOW64; rv:30.0) Gecko/20100101 Firefox/30.0'}
        )
        return res.content.decode("utf-8")

    @classmethod
    def _parse_response(cls, response_body):
        soup = BeautifulSoup(response_body, "html.parser")

        suggestions = [tds.find_all("a") for tds in soup.find_all("td", class_="td3nl")]
        if len(suggestions) == 2:
            languages = [lang.string for lang in soup.find_all("td", class_="td2")][:2]
            if len(languages) != 2:
                raise Exception("dict.cc results page layout change, please raise an issue.")

            return Result(
                from_lang=languages[0],
                to_lang=languages[1],
                translation_tuples=zip(
                    [e.string for e in suggestions[0]],
                    [e.string for e in suggestions[1]]
                ),
            )

        translations = [tds.find_all(["a", "var"]) for tds in soup.find_all("td", class_="td7nl", attrs={'dir': "ltr"})]
        if len(translations) >= 2:
            languages = [next(lang.strings) for lang in soup.find_all("td", class_="td2", attrs={'dir': "ltr"})]
            if len(languages) != 2:
                raise Exception("dict.cc results page layout change, please raise an issue.")

            return Result(
                from_lang=languages[0],
                to_lang=languages[1],
                translation_tuples=zip(
                    [" ".join(map(lambda e: " ".join(e.strings), r)) for r in translations[0:-1:2]],
                    [" ".join(map(lambda e: e.string if e.string else "".join(e.strings), r)) for r in translations[1:-1:2]]
                ),
            )

        return Result()

    @classmethod
    def _correct_translation_order(cls, result, word):
        if not result.translation_tuples:
            return result

        [from_words, to_words] = zip(*result.translation_tuples)

        n_from_lang = sum(from_word.lower().count(word.lower()) for from_word in from_words)
        n_to_lang = sum(to_word.lower().count(word.lower()) for to_word in to_words)

        return result if n_from_lang >= n_to_lang else Result(
            from_lang=result.to_lang,
            to_lang=result.from_lang,
            translation_tuples=zip(to_words, from_words),
        )

# --- Telegram Bot Setup ---

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
if not TOKEN:
    TOKEN = "PLACEHOLDER_TOKEN"

bot = telebot.TeleBot(TOKEN, threaded=False)
app = Flask(__name__)

# User Preferences store (in-memory, ephemeral)
USER_PREFS = {}

# Emoji flags matching supported languages
LANG_FLAGS = {
    "en": "🇬🇧",
    "de": "🇩🇪",
    "fr": "🇫🇷",
    "sv": "🇸🇪",
    "no": "🇳🇴",
    "es": "🇪🇸",
    "nl": "🇳🇱",
    "bg": "🇧🇬",
    "ro": "🇷🇴",
    "it": "🇮🇹",
    "pt": "🇵🇹",
    "ru": "🇷🇺"
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dict.cc Telegram Bot Status</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f172a, #1e1b4b);
            color: #f8fafc;
            min-height: 100vh;
            margin: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            box-sizing: border-box;
        }
        .card {
            background: rgba(30, 41, 59, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            max-width: 550px;
            width: 100%;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            margin-top: 0;
            color: #38bdf8;
            font-size: 28px;
        }
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            margin: 20px 0;
        }
        .success {
            background-color: rgba(34, 197, 94, 0.2);
            color: #4ade80;
            border: 1px solid rgba(34, 197, 94, 0.4);
        }
        .error {
            background-color: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }
        p {
            line-height: 1.6;
            color: #cbd5e1;
            text-align: left;
        }
        .center-p {
            text-align: center;
        }
        code {
            background: #0f172a;
            padding: 3px 6px;
            border-radius: 4px;
            color: #f472b6;
            font-family: monospace;
        }
        .btn {
            display: inline-block;
            background-color: #38bdf8;
            color: #0f172a;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            margin-top: 20px;
            transition: all 0.3s ease;
        }
        .btn:hover {
            background-color: #0ea5e9;
            transform: translateY(-2px);
        }
        .footer {
            margin-top: 30px;
            font-size: 12px;
            color: #64748b;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Dict.cc Telegram Bot</h1>
        <p class="center-p">A premium translation bot powered by the dict.cc unofficial API.</p>
        
        <div class="status-badge {{ status_class }}">
            {{ status_text }}
        </div>
        
        <p>{{ message }}</p>
        
        {% if show_setup_btn %}
        <a href="/setup_webhook" class="btn">Register Webhook on Telegram</a>
        {% endif %}
        
        <div class="footer">
            Unofficial Dict.cc Telegram Bot setup & status panel.
        </div>
    </div>
</body>
</html>
"""

def escape_html(text):
    """Escapes special HTML characters to prevent parsing issues on Telegram."""
    if not text:
        return ""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def get_settings_keyboard(chat_id):
    """Generates the settings keyboard."""
    prefs = USER_PREFS.get(chat_id, {"lang1": "en", "lang2": "de"})
    l1 = prefs["lang1"]
    l2 = prefs["lang2"]
    
    markup = telebot.types.InlineKeyboardMarkup()
    
    btn1 = telebot.types.InlineKeyboardButton(
        text=f"Lang 1: {LANG_FLAGS.get(l1, '')} {l1.upper()}",
        callback_data="set_l1"
    )
    btn2 = telebot.types.InlineKeyboardButton(
        text=f"Lang 2: {LANG_FLAGS.get(l2, '')} {l2.upper()}",
        callback_data="set_l2"
    )
    markup.row(btn1, btn2)
    
    btn_swap = telebot.types.InlineKeyboardButton(
        text="🔄 Swap Selection",
        callback_data="swap_settings"
    )
    markup.add(btn_swap)
    
    btn_close = telebot.types.InlineKeyboardButton(
        text="❌ Close Settings",
        callback_data="close_settings"
    )
    markup.add(btn_close)
    
    return markup

def get_languages_keyboard(target_param):
    """Generates a selection grid for languages."""
    markup = telebot.types.InlineKeyboardMarkup()
    buttons = []
    for code in sorted(AVAILABLE_LANGUAGES.keys()):
        flag = LANG_FLAGS.get(code, "")
        buttons.append(
            telebot.types.InlineKeyboardButton(
                text=f"{flag} {code.upper()}",
                callback_data=f"select_{target_param}_{code}"
            )
        )
    for i in range(0, len(buttons), 3):
        markup.row(*buttons[i:i+3])
        
    btn_back = telebot.types.InlineKeyboardButton(
        text="🔙 Back to Settings",
        callback_data="show_settings"
    )
    markup.add(btn_back)
    return markup

def get_translation_keyboard(word, from_code, to_code):
    """Generates inline buttons for swapping and fast-switching translation languages."""
    markup = telebot.types.InlineKeyboardMarkup()
    
    swap_btn = telebot.types.InlineKeyboardButton(
        text=f"🔄 Swap ({to_code.upper()} ➔ {from_code.upper()})",
        callback_data=f"swap:{to_code}:{from_code}:{word}"
    )
    markup.add(swap_btn)
    
    popular_langs = ["en", "de", "fr", "es", "it"]
    quick_buttons = []
    for lang in popular_langs:
        if lang != to_code and lang != from_code:
            flag = LANG_FLAGS.get(lang, "")
            quick_buttons.append(
                telebot.types.InlineKeyboardButton(
                    text=f"{flag} {lang.upper()}",
                    callback_data=f"swap:{from_code}:{lang}:{word}"
                )
            )
    if quick_buttons:
        for i in range(0, len(quick_buttons), 2):
            markup.row(*quick_buttons[i:i+2])
            
    return markup

def format_translation(word, result, from_code, to_code):
    """Formats dict.cc translation results into Telegram HTML."""
    if not result.translation_tuples:
        from_flag = LANG_FLAGS.get(from_code, "❓")
        to_flag = LANG_FLAGS.get(to_code, "❓")
        return (
            f"❌ <b>No results found</b> for '{escape_html(word)}'\n"
            f"Direction: {from_flag} <code>{from_code.upper()}</code> ⬌ {to_flag} <code>{to_code.upper()}</code>"
        )
    
    from_flag = LANG_FLAGS.get(from_code, "")
    to_flag = LANG_FLAGS.get(to_code, "")
    
    lines = []
    lines.append(f"🔍 <b>Translation for:</b> <code>{escape_html(word)}</code>")
    lines.append(f"{from_flag} <b>{escape_html(result.from_lang)}</b> ➔ {to_flag} <b>{escape_html(result.to_lang)}</b>")
    lines.append("")
    
    # Display top 10 results
    for from_w, to_w in result.translation_tuples[:10]:
        escaped_from = escape_html(from_w)
        escaped_to = escape_html(to_w)
        lines.append(f"• <b>{escaped_from}</b> ➔ {escaped_to}")
        
    return "\n".join(lines)

def perform_translation(chat_id, word, from_code, to_code):
    """Performs translation lookup and sends the HTML result."""
    bot.send_chat_action(chat_id, 'typing')
    try:
        result = DictccScraper.translate(word, from_code, to_code)
        text = format_translation(word, result, from_code, to_code)
        
        callback_len = len(f"swap:{to_code}:{from_code}:{word}".encode('utf-8'))
        
        if result.translation_tuples and callback_len <= 64:
            markup = get_translation_keyboard(word, from_code, to_code)
            bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
        else:
            bot.send_message(chat_id, text, parse_mode="HTML")
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ <b>Error occurred during translation:</b>\n<code>{escape_html(str(e))}</code>", parse_mode="HTML")

# --- Flask Server Routes ---

@app.route('/')
def home():
    if TOKEN == "PLACEHOLDER_TOKEN" or not TOKEN:
        status_class = "error"
        status_text = "Configuration Error"
        message = (
            "The <code>TELEGRAM_BOT_TOKEN</code> environment variable is missing or empty. "
            "Please configure it on Koyeb or Vercel before attempting to use the bot."
        )
        show_setup_btn = False
    else:
        status_class = "success"
        status_text = "Bot Active"
        webhook_url = os.environ.get('WEBHOOK_URL')
        if webhook_url:
            message = (
                f"Bot is configured correctly and listening for webhooks. "
                f"Webhook URL is configured to point to: <code>{webhook_url}</code>."
            )
        else:
            detected_url = request.url_root.rstrip('/')
            message = (
                f"Bot is running! Since the <code>WEBHOOK_URL</code> environment variable is not set, "
                f"it will be automatically detected as <code>{detected_url}</code> when registering."
            )
        show_setup_btn = True
            
    return render_template_string(
        HTML_TEMPLATE,
        status_class=status_class,
        status_text=status_text,
        message=message,
        show_setup_btn=show_setup_btn
    )

@app.route('/setup_webhook', methods=['GET', 'POST'])
def setup_webhook():
    if TOKEN == "PLACEHOLDER_TOKEN" or not TOKEN:
        return "Telegram Bot Token is not set in environment variables.", 400
        
    webhook_url = os.environ.get('WEBHOOK_URL')
    if not webhook_url:
        webhook_url = request.url_root.rstrip('/')
        
    url = f"{webhook_url}/{TOKEN}"
    success = bot.set_webhook(url=url)
    if success:
        return f"Webhook successfully registered with Telegram! Path: {url}", 200
    else:
        return "Telegram API rejected webhook registration. Verify your Token.", 500

@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    print("[Webhook] Received POST request to webhook endpoint.")
    
    json_dict = request.get_json(force=True, silent=True)
    if json_dict:
        print(f"[Webhook] Successfully parsed JSON: {json_dict}")
        try:
            update = telebot.types.Update.de_json(json_dict)
            print(f"[Webhook] Processing update ID: {update.update_id}")
            bot.process_new_updates([update])
            print("[Webhook] Update processed successfully.")
            return 'ok', 200
        except Exception as e:
            print(f"[Webhook] Error processing update: {e}")
            import traceback
            traceback.print_exc()
            return 'internal error', 500
            
    try:
        raw_data = request.get_data()
        print(f"[Webhook] Fallback: Raw data received (length {len(raw_data)})")
        json_string = raw_data.decode('utf-8')
        if json_string:
            update = telebot.types.Update.de_json(json_string)
            print(f"[Webhook] Processing update ID from raw: {update.update_id}")
            bot.process_new_updates([update])
            print("[Webhook] Raw update processed successfully.")
            return 'ok', 200
    except Exception as e:
        print(f"[Webhook] Fallback parsing failed: {e}")
        
    print("[Webhook] Failed to parse request payload as JSON.")
    abort(400)

# --- Telegram Bot Handlers (HTML Mode) ---

def send_help(message):
    text = (
        "📖 <b>Dict.cc Translation Bot</b>\n\n"
        "Translate words and phrases between 12 languages instantly!\n\n"
        "🚀 <b>How to use:</b>\n"
        "• <b>Plain Text:</b> Send any word or phrase (e.g. <code>beer</code> or <code>Bier</code>). The bot translates it using your default pair.\n"
        "• <b>Translate Command:</b> <code>/tr &lt;from&gt; &lt;to&gt; &lt;word&gt;</code>\n  Example: <code>/tr en es beer</code>\n"
        "• <b>Shortcut Commands:</b>\n"
        "  <code>/ensv beer</code> (English ➔ Swedish)\n"
        "  <code>/defr Brot</code> (German ➔ French)\n"
        "• <b>Inline Mode:</b> Type <code>@bot_username &lt;word&gt;</code> in any chat to query translation inline.\n\n"
        "🛠 <b>Settings:</b>\n"
        "Use <code>/settings</code> or <code>/langs</code> to change your active translation pair.\n\n"
        "🌐 <b>Supported Languages:</b>\n"
    )
    for code, name in sorted(AVAILABLE_LANGUAGES.items()):
        flag = LANG_FLAGS.get(code, "")
        text += f"• {flag} <code>{code}</code> ➔ {escape_html(name.capitalize())}\n"
        
    bot.send_message(message.chat.id, text, parse_mode="HTML")

def send_settings(message):
    chat_id = message.chat.id
    if chat_id not in USER_PREFS:
        USER_PREFS[chat_id] = {"lang1": "en", "lang2": "de"}
    
    prefs = USER_PREFS[chat_id]
    l1 = prefs["lang1"]
    l2 = prefs["lang2"]
    l1_name = escape_html(AVAILABLE_LANGUAGES.get(l1, "").capitalize())
    l2_name = escape_html(AVAILABLE_LANGUAGES.get(l2, "").capitalize())
    
    markup = get_settings_keyboard(chat_id)
    text = (
        f"🛠 <b>Settings Panel</b>\n\n"
        f"Configure your default translation pair:\n"
        f"• Language 1: {LANG_FLAGS.get(l1, '')} <b>{l1_name}</b>\n"
        f"• Language 2: {LANG_FLAGS.get(l2, '')} <b>{l2_name}</b>\n\n"
        f"Send any text without commands to translate between these active languages."
    )
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)

@bot.message_handler(commands=['start', 'help'])
def handle_start_help(message):
    send_help(message)

@bot.message_handler(commands=['settings', 'langs'])
def handle_settings_command(message):
    send_settings(message)

@bot.message_handler(commands=['tr'])
def handle_tr_command(message):
    parts = message.text.split(None, 3)
    if len(parts) < 4:
        bot.reply_to(message, "⚠️ <b>Usage:</b> <code>/tr &lt;from&gt; &lt;to&gt; &lt;word&gt;</code>\nExample: <code>/tr en es beer</code>", parse_mode="HTML")
        return
    l1 = parts[1].lower()
    l2 = parts[2].lower()
    word = parts[3]
    
    if l1 not in AVAILABLE_LANGUAGES or l2 not in AVAILABLE_LANGUAGES:
        bot.reply_to(
            message, 
            f"⚠️ Invalid language codes. Supported codes:\n<code>{', '.join(sorted(AVAILABLE_LANGUAGES.keys()))}</code>", 
            parse_mode="HTML"
        )
        return
        
    perform_translation(message.chat.id, word, l1, l2)

@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def handle_all_commands(message):
    text = message.text.strip()
    parts = text.split(None, 1)
    cmd = parts[0][1:].lower()
    
    if len(cmd) == 4:
        l1, l2 = cmd[:2], cmd[2:]
        if l1 in AVAILABLE_LANGUAGES and l2 in AVAILABLE_LANGUAGES:
            if len(parts) > 1:
                word = parts[1]
                perform_translation(message.chat.id, word, l1, l2)
            else:
                bot.reply_to(
                    message, 
                    f"⚠️ Please provide the word to translate. Example: <code>/{cmd} beer</code>", 
                    parse_mode="HTML"
                )
            return
            
    bot.reply_to(message, "⚠️ Unknown command. Use <code>/help</code> to see available commands.", parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text and not message.text.startswith('/'))
def handle_plain_text(message):
    word = message.text.strip()
    chat_id = message.chat.id
    
    if chat_id not in USER_PREFS:
        USER_PREFS[chat_id] = {"lang1": "en", "lang2": "de"}
        
    prefs = USER_PREFS[chat_id]
    l1 = prefs["lang1"]
    l2 = prefs["lang2"]
    
    perform_translation(chat_id, word, l1, l2)

# --- Callback Query Handlers ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('swap:'))
def handle_swap_callback(call):
    parts = call.data.split(':', 3)
    if len(parts) < 4:
        return
    from_code = parts[1]
    to_code = parts[2]
    word = parts[3]
    
    bot.answer_callback_query(call.id, text="Swapping translation...")
    
    try:
        result = DictccScraper.translate(word, from_code, to_code)
        text = format_translation(word, result, from_code, to_code)
        markup = get_translation_keyboard(word, from_code, to_code)
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup
        )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ <b>Error during swap:</b>\n<code>{escape_html(str(e))}</code>", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data in ['set_l1', 'set_l2', 'show_settings', 'swap_settings', 'close_settings'] or call.data.startswith('select_l1_') or call.data.startswith('select_l2_'))
def handle_settings_callbacks(call):
    chat_id = call.message.chat.id
    
    if chat_id not in USER_PREFS:
        USER_PREFS[chat_id] = {"lang1": "en", "lang2": "de"}
        
    data = call.data
    
    if data == 'show_settings':
        bot.answer_callback_query(call.id)
        markup = get_settings_keyboard(chat_id)
        prefs = USER_PREFS[chat_id]
        l1 = prefs["lang1"]
        l2 = prefs["lang2"]
        l1_name = escape_html(AVAILABLE_LANGUAGES.get(l1, "").capitalize())
        l2_name = escape_html(AVAILABLE_LANGUAGES.get(l2, "").capitalize())
        text = (
            f"🛠 <b>Settings Panel</b>\n\n"
            f"Configure your default translation pair:\n"
            f"• Language 1: {LANG_FLAGS.get(l1, '')} <b>{l1_name}</b>\n"
            f"• Language 2: {LANG_FLAGS.get(l2, '')} <b>{l2_name}</b>\n\n"
            f"Send any text without commands to translate between these active languages."
        )
        bot.edit_message_text(text, chat_id=chat_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)
        
    elif data == 'set_l1':
        bot.answer_callback_query(call.id)
        markup = get_languages_keyboard('l1')
        bot.edit_message_text("Select a new language for <b>Language 1</b>:", chat_id=chat_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)
        
    elif data == 'set_l2':
        bot.answer_callback_query(call.id)
        markup = get_languages_keyboard('l2')
        bot.edit_message_text("Select a new language for <b>Language 2</b>:", chat_id=chat_id, message_id=call.message.message_id, parse_mode="HTML", reply_markup=markup)
        
    elif data.startswith('select_l1_'):
        lang = data.split('_')[2]
        USER_PREFS[chat_id]["lang1"] = lang
        bot.answer_callback_query(call.id, text=f"Language 1 set to {lang.upper()}")
        handle_settings_callbacks(telebot.types.CallbackQuery(
            id=call.id,
            from_user=call.from_user,
            message=call.message,
            chat_instance=call.chat_instance,
            data='show_settings'
        ))
        
    elif data.startswith('select_l2_'):
        lang = data.split('_')[2]
        USER_PREFS[chat_id]["lang2"] = lang
        bot.answer_callback_query(call.id, text=f"Language 2 set to {lang.upper()}")
        handle_settings_callbacks(telebot.types.CallbackQuery(
            id=call.id,
            from_user=call.from_user,
            message=call.message,
            chat_instance=call.chat_instance,
            data='show_settings'
        ))
        
    elif data == 'swap_settings':
        l1 = USER_PREFS[chat_id]["lang1"]
        l2 = USER_PREFS[chat_id]["lang2"]
        USER_PREFS[chat_id]["lang1"] = l2
        USER_PREFS[chat_id]["lang2"] = l1
        bot.answer_callback_query(call.id, text="Languages swapped!")
        handle_settings_callbacks(telebot.types.CallbackQuery(
            id=call.id,
            from_user=call.from_user,
            message=call.message,
            chat_instance=call.chat_instance,
            data='show_settings'
        ))
        
    elif data == 'close_settings':
        bot.answer_callback_query(call.id)
        bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)

# --- Inline Query Handlers ---

@bot.inline_handler(lambda query: len(query.query) > 0)
def handle_inline_query(inline_query):
    query = inline_query.query.strip()
    parts = query.split(None, 2)
    
    from_code = "en"
    to_code = "de"
    word = query
    
    if len(parts) >= 3 and parts[0].lower() in AVAILABLE_LANGUAGES and parts[1].lower() in AVAILABLE_LANGUAGES:
        from_code = parts[0].lower()
        to_code = parts[1].lower()
        word = parts[2]
    elif len(parts) >= 2 and len(parts[0]) == 4:
        l1, l2 = parts[0][:2].lower(), parts[0][2:].lower()
        if l1 in AVAILABLE_LANGUAGES and l2 in AVAILABLE_LANGUAGES:
            from_code = l1
            to_code = l2
            word = " ".join(parts[1:])
            
    try:
        result = DictccScraper.translate(word, from_code, to_code)
        if not result.translation_tuples:
            item = telebot.types.InlineQueryResultArticle(
                id='no_results',
                title=f"No results for '{word}'",
                description=f"Checked {from_code.upper()} ➔ {to_code.upper()}",
                input_message_content=telebot.types.InputTextMessageContent(
                    message_text=f"❌ No translation results found for <b>{escape_html(word)}</b>.",
                    parse_mode="HTML"
                )
            )
            bot.answer_inline_query(inline_query.id, [item])
            return
            
        from_flag = LANG_FLAGS.get(from_code, "")
        to_flag = LANG_FLAGS.get(to_code, "")
        
        snippets = []
        for f_w, t_w in result.translation_tuples[:3]:
            snippets.append(f"{f_w} -> {t_w}")
        description = "; ".join(snippets)
        
        formatted_text = format_translation(word, result, from_code, to_code)
        
        callback_len = len(f"swap:{to_code}:{from_code}:{word}".encode('utf-8'))
        markup = None
        if callback_len <= 64:
            markup = get_translation_keyboard(word, from_code, to_code)
            
        item = telebot.types.InlineQueryResultArticle(
            id=str(hash(query)),
            title=f"Translate '{word}' ({from_code.upper()} ➔ {to_code.upper()})",
            description=description,
            input_message_content=telebot.types.InputTextMessageContent(
                message_text=formatted_text,
                parse_mode="HTML"
            ),
            reply_markup=markup
        )
        bot.answer_inline_query(inline_query.id, [item])
        
    except Exception as e:
        item = telebot.types.InlineQueryResultArticle(
            id='error',
            title="Translation Error",
            description=str(e),
            input_message_content=telebot.types.InputTextMessageContent(
                message_text=f"❌ Error occurred: {escape_html(str(e))}",
                parse_mode="HTML"
            )
        )
        bot.answer_inline_query(inline_query.id, [item])

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
