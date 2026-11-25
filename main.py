from flask import Flask
from threading import Thread
import os as _os_for_port

app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot is alive!"

def run_web():
    port = int(_os_for_port.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

keep_alive()
import os
from flask import Flask
import sqlite3
from html import escape

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ضعي رمز البوت من BotFather هنا
TOKEN = "9130779328:AAFGfsAthcDRcAutSr92VgpWGvS9AKLlQAY"

DB = "warshiyat.db"
ACADEMY = "🌿 ورشيات طريق التوبة 🌿"


# =========================
# قاعدة البيانات
# =========================

def connect():
    return sqlite3.connect(DB)


def init_db():
    with connect() as con:
        
                con.execute("""
            CREATE TABLE IF NOT EXISTS reading_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                thread_id INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL,
                is_open INTEGER NOT NULL DEFAULT 1,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        columns = [r[1]]  for r in con.execute("PRAGMA table_info(queue_members)").fetchall()]

        # ترحيل بيانات الكود القديم دون حذف الأسماء
        if columns and "list_id" not in columns:
            con.execute(
                "ALTER TABLE queue_members RENAME TO queue_members_old"
            )

            con.execute("""
                CREATE TABLE queue_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'waiting',
                    UNIQUE(list_id, user_id)
                )
            """)

            old_chats = con.execute(
                "SELECT DISTINCT chat_id FROM queue_members_old"
            ).fetchall()

            for (chat_id,) in old_chats:
                con.execute(
                    """INSERT INTO reading_lists
                       (chat_id, title, is_open, is_active)
                       VALUES (?, ?, 1, 1)""",
                    (chat_id, "قائمة ورشيات القديمة")
                )

                list_id = con.execute(
                    "SELECT last_insert_rowid()"
                ).fetchone()[0]

                con.execute("""
                    INSERT INTO queue_members
                    (list_id, chat_id, user_id, name, role, status)
                    SELECT ?, chat_id, user_id, name, role, status
                    FROM queue_members_old
                    WHERE chat_id = ?
                """, (list_id, chat_id))

            con.execute("DROP TABLE queue_members_old")

        else:
            con.execute("""
                CREATE TABLE IF NOT EXISTS queue_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'waiting',
                    UNIQUE(list_id, user_id)
                )
            """)


def get_active_list(chat_id, thread_id=0):
    if thrad_id is None:
        thread_id = 0
    with connect() as con:
        row = con.execute("""
            SELECT id, title, is_open, is_active
            FROM reading_lists
            WHERE chat_id = ? AND thread_id = ? AND is_active = 1
            ORDER BY id DESC LIMIT 1
        """, (chat_id, thread_id)).fetchone()

        if row:
            return row

        number = con.execute(
            "SELECT COUNT(*) FROM reading_lists WHERE chat_id = ? AND thread_id = ?",
            (chat_id, thread_id),
        ).fetchone()[0] + 1

        title = f"قائمة ورشيات رقم {number}"

        con.execute("""
            INSERT INTO reading_lists
            (chat_id, thread_id, title, is_open, is_active)
            VALUES (?, ?, ?, 1, 1)
        """, (chat_id, thread_id, title))

        list_id = con.execute(
            "SELECT last_insert_rowid()"
        ).fetchone()[0]

        return list_id, title, 1, 1


def get_list(list_id):
    with connect() as con:
        return con.execute("""
            SELECT id, chat_id, title, is_open, is_active
            FROM reading_lists
            WHERE id = ?
        """, (list_id,)).fetchone()


def get_members(list_id):
    with connect() as con:
        return con.execute("""
            SELECT user_id, name, role, status
            FROM queue_members
            WHERE list_id = ?
            ORDER BY id ASC
        """, (list_id,)).fetchall()


def get_current_reader(list_id):
    with connect() as con:
        return con.execute("""
            SELECT user_id, name
            FROM queue_members
            WHERE list_id = ?
            AND role = 'قارئة'
            AND status = 'waiting'
            ORDER BY id ASC LIMIT 1
        """, (list_id,)).fetchone()


# =========================
# التحقق من أدمنات المجموعة
# =========================

async def is_group_admin(context, chat_id, user_id):
    try:
        member = await context.bot.get_chat_member(
            chat_id=chat_id,
            user_id=user_id
        )

        return member.status in ("administrator", "creator")

    except TelegramError:
        return False


# =========================
# أزرار القائمة
# =========================

def keyboard(list_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🌷 سجّلي اسمي",
                callback_data=f"register_reader:{list_id}"
            ),
            InlineKeyboardButton(
                "🎧 مستمعة",
                callback_data=f"register_listener:{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🌸 قرأت",
                callback_data=f"done:{list_id}"
            ),
            InlineKeyboardButton(
                "🗑️ احذف اسمي",
                callback_data=f"delete_me:{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "⏭️ الطالبة التالية",
                callback_data=f"admin_next:{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🔒 إغلاق القائمة",
                callback_data=f"close_list:{list_id}"
            ),
            InlineKeyboardButton(
                "🔓 فتح القائمة",
                callback_data=f"open_list:{list_id}"
            )
        ],
        [
            InlineKeyboardButton(
                "🌷 قائمة جديدة",
                callback_data=f"new_list:{list_id}"
            )
        ]
    ])


# =========================
# عرض القائمة
# =========================

def build_panel(list_id):
    info = get_list(list_id)

    if not info:
        return "القائمة غير موجودة."

    _, chat_id, title, is_open, is_active = info

    members = get_members(list_id)
    current = get_current_reader(list_id)

    readers = [m for m in members if m[2] == "قارئة"]
    listeners = [m for m in members if m[2] == "مستمعة"]

    lines = [
        "<b>بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ</b>",
        "",
        f"<b>{ACADEMY}</b>",
        "📖 <b>مجلس تلاوة القرآن الكريم</b>",
        "━━━━━━━━━━━━━━━━━━",
        f"🌸 <b>{escape(title)}</b>",
        ""
    ]

    if not is_active:
        lines.append("📦 <b>قائمة محفوظة سابقة</b>")
    elif is_open:
        lines.append("🟢 <b>القائمة مفتوحة للتسجيل</b>")
    else:
        lines.append("🔒 <b>القائمة مغلقة للتسجيل</b>")

    lines.extend(["", "🌹 <b>الدور الحالي:</b>"])

    if current:
        current_id, current_name = current
        lines.append(
            f'🌷 <a href="tg://user?id={current_id}">'
            f'{escape(current_name)}</a> — ننتظر تلاوتكِ'
        )
    else:
        lines.append("🌱 لا توجد قارئة تنتظر دورها حاليًا.")

    lines.extend(["", "🌷 <b>ترتيب القارئات:</b>"])

    if readers:
        for number, (user_id, name, role, status) in enumerate(readers, 1):
            if status == "done":
                state = "✅ قرأت"
            elif current and user_id == current[0]:
                state = "🌹 دورها الآن"
            else:
                state = "⏳ بانتظار دورها"

            lines.append(
                f'{number}. 🌷 <a href="tg://user?id={user_id}">'
                f'{escape(name)}</a> — {state}'
            )
    else:
        lines.append("لا توجد قارئات مسجلات بعد.")

    lines.extend(["", "🎧 <b>المستمعات:</b>"])

    if listeners:
        for number, (user_id, name, role, status) in enumerate(listeners, 1):
            lines.append(
                f'{number}. 🎧 <a href="tg://user?id={user_id}">'
                f'{escape(name)}</a>'
            )
    else:
        lines.append("لا توجد مستمعات مسجلات بعد.")

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"📖 عدد القارئات: <b>{len(readers)}</b>",
        f"🎧 عدد المستمعات: <b>{len(listeners)}</b>",
        "",
        "🤍 اللهم اجعل القرآن ربيع قلوبنا ونور صدورنا",
        "وارزقنا تلاوته آناء الليل وأطراف النهار",
        "🌿 اللهم علّمنا منه ما جهلنا وذكّرنا منه ما نُسّينا"
    ])

    return "\n".join(lines)


async def refresh_panel(message, list_id):
    try:
        await message.edit_text(
            build_panel(list_id),
            reply_markup=keyboard(list_id),
            parse_mode=ParseMode.HTML
        )
    except TelegramError:
        pass


async def notify_current(context, list_id, thread_id=0):
    current = get_current_reader(list_id)

    if not current:
        return

    user_id, name = current

    mention = (
        f'<a href="tg://user?id={user_id}">'
        f'{escape(name)}</a>'
    )

    info = get_list(list_id)

    if not info:
        return

    try:
        await context.bot.send_message(
            chat_id=info[1],
            text=(
                f"🌹 حان دور القارئة التالية: {mention}\n"
                "تفضّلي، ننتظر تلاوتكِ 🤍"
            ),
            parse_mode=ParseMode.HTML,
            message_thread_id=thread_id if thread_id None
        )
    except TelegramError:
        pass


# =========================
# الأوامر
# =========================

async def start(update, context):
    await update.message.reply_text(
        f"🌿 أهلاً وسهلاً بكِ في {ACADEMY}\n\n"
        "📖 نسعد بمشاركتكِ في مجالس القرآن الكريم.\n"
        "استخدمي /help لمعرفة الأوامر."
    )


async def help_command(update, context):
    await update.message.reply_text(
        "🌿 دليل أوامر بوت ورشيات\n\n"
        "/post - نشر القائمة في المجموعة\n"
        "/myid - معرفة رقم حسابك\n"
        "/archives - عرض القوائم السابقة\n"
        "/help - المساعدة\n\n"
        "🌷 عند انتهاء الطالبة من القراءة تضغط قرأت، "
        "فينتقل الدور تلقائيًا إلى التالية."
    )


async def myid(update, context):
    await update.message.reply_text(
        f"رقم حسابك: {update.effective_user.id}"
    )


async def post(update, context):
    chat_id = update.effective_chat.id
    thread_id = update.message.message_thread_id or 0

    if not await is_group_admin(
        context, chat_id, update.effective_user.id
    ):
        await update.message.reply_text(
            "🌷 عذرًا، نشر القائمة خاص بمشرفات المجموعة."
        )
        return

    list_id, title, is_open, active = get_active_list(chat_id, thread_id)

    await update.message.reply_text(
        build_panel(list_id),
        reply_markup=keyboard(list_id),
        parse_mode=ParseMode.HTML
    )


async def archives(update, context):
    chat_id = update.effective_chat.id

    if not await is_group_admin(
        context, chat_id, update.effective_user.id
    ):
        await update.message.reply_text(
            "هذا الأمر خاص بمشرفات المجموعة."
        )
        return

    with connect() as con:
        rows = con.execute("""
            SELECT id, title, created_at
            FROM reading_lists
            WHERE chat_id = ? AND is_active = 0
            ORDER BY id DESC
        """, (chat_id,)).fetchall()

        if not rows:
            await update.message.reply_text(
                "🌷 لا توجد قوائم سابقة محفوظة حتى الآن."
            )
            return

        lines = ["📚 <b>القوائم السابقة المحفوظة:</b>", ""]

        for list_id, title, created_at in rows:
            count = con.execute(
                "SELECT COUNT(*) FROM queue_members WHERE list_id = ?",
                (list_id,)
            ).fetchone()[0]

            lines.append(
                f"🌸 <b>{escape(title)}</b>\n"
                f"عدد المسجلات: {count}\n"
                f"تاريخ الإنشاء: {created_at}\n"
            )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML
    )


# =========================
# التعامل مع الأزرار
# =========================

async def handle_buttons(update, context):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat_id
    thread_id = query.message.message_thread_id or 0

    try:
        action, list_id_text = query.data.split(":")
        list_id = int(list_id_text)
    except (ValueError, AttributeError):
        await query.answer("حدث خطأ، حاولي مرة أخرى.")
        return

    info = get_list(list_id)

    if not info:
        await query.answer("هذه القائمة غير موجودة.", show_alert=True)
        return

    _, list_chat_id, title, is_open, is_active = info

    if list_chat_id != chat_id:
        await query.answer("القائمة غير صحيحة.", show_alert=True)
        return

    if not is_active:
        await query.answer(
            "🌷 هذه قائمة سابقة محفوظة ولا يمكن تعديلها.",
            show_alert=True
        )
        return

    # التسجيل والاستماع
    if action in ("register_reader", "register_listener"):

        if not is_open:
            await query.answer(
                "🔒 القائمة مغلقة حاليًا.",
                show_alert=True
            )
            return

        role = (
            "قارئة"
            if action == "register_reader"
            else "مستمعة"
        )

        with connect() as con:
            existing = con.execute("""
                SELECT role FROM queue_members
                WHERE list_id = ? AND user_id = ?
            """, (list_id, user.id)).fetchone()

            if existing:
                await query.answer(
                    "أنتِ مسجلة بالفعل. احذفي اسمك أولًا.",
                    show_alert=True
                )
                return

            con.execute("""
                INSERT INTO queue_members
                (list_id, chat_id, user_id, name, role, status)
                VALUES (?, ?, ?, ?, ?, 'waiting')
            """, (
                list_id, chat_id, user.id,
                user.full_name, role
            ))

        await query.answer("تم تسجيلك بنجاح 🌷")

        await query.message.reply_text(
            f"🌷 تم تسجيلكِ يا {escape(user.full_name)}\n"
            f"📖 الصفة: {role}\n"
            "🤍 بارك الله فيكِ.",
            parse_mode=ParseMode.HTML
        )

        await refresh_panel(query.message, list_id)

        if role == "قارئة":
            current = get_current_reader(list_id)

            if current and current[0] == user.id:
                await notify_current(context, list_id thread_id)

        return

    # حذف الاسم
    if action == "delete_me":
        with connect() as con:
            row = con.execute("""
                SELECT role, status FROM queue_members
                WHERE list_id = ? AND user_id = ?
            """, (list_id, user.id)).fetchone()

            if row:
                con.execute("""
                    DELETE FROM queue_members
                    WHERE list_id = ? AND user_id = ?
                """, (list_id, user.id))

        if not row:
            await query.answer(
                "اسمك غير موجود في القائمة.",
                show_alert=True
            )
            return

        await query.answer("تم حذف اسمك 🌷")

        await query.message.reply_text(
            "🗑️ تم حذف اسمك من القائمة."
        )

        await refresh_panel(query.message, list_id)

        if row[0] == "قارئة" and row[1] == "waiting":
            await notify_current(context, list_id thread_id)

        return

    # انتهاء القراءة
    if action == "done":
        current = get_current_reader(list_id)

        if not current:
            await query.answer(
                "لا توجد قارئة عليها الدور الآن.",
                show_alert=True
            )
            return

        if current[0] != user.id:
            await query.answer(
                "🌷 ليس دورك الآن. انتظري دورك.",
                show_alert=True
            )
            return

        with connect() as con:
            con.execute("""
                UPDATE queue_members
                SET status = 'done'
                WHERE list_id = ? AND user_id = ?
            """, (list_id, user.id))

        await query.answer("تقبل الله منكِ 🌸")

        await query.message.reply_text(
            f"🌸 تقبل الله منكِ يا {escape(user.full_name)}\n"
            "انتقل الدور إلى القارئة التالية بإذن الله.",
            parse_mode=ParseMode.HTML
        )

        await refresh_panel(query.message, list_id)
        await notify_current(context, list_id thread_id)
        return

    # التحقق من صلاحيات المشرفة
    admin_actions = (
        "admin_next",
        "close_list",
        "open_list",
        "new_list"
    )

    if action in admin_actions:
        if not await is_group_admin(
            context, chat_id, user.id
        ):
            await query.answer(
                "🌷 هذا الزر خاص بمشرفات المجموعة.",
                show_alert=True
            )
            return

    # الطالبة التالية
    if action == "admin_next":
        current = get_current_reader(list_id)

        if not current:
            await query.answer(
                "لا توجد قارئة حالية.",
                show_alert=True
            )
            return

        with connect() as con:
            con.execute("""
                UPDATE queue_members
                SET status = 'done'
                WHERE list_id = ? AND user_id = ?
            """, (list_id, current[0]))

        await query.answer("تم الانتقال للطالبة التالية.")

        await query.message.reply_text(
            "⏭️ تم تجاوز الدور والانتقال إلى الطالبة التالية."
        )

        await refresh_panel(query.message, list_id)
        await notify_current(context, list_id thread_id)
        return

    # إغلاق القائمة
    if action == "close_list":
        with connect() as con:
            con.execute("""
                UPDATE reading_lists
                SET is_open = 0
                WHERE id = ?
            """, (list_id,))

        await query.answer("🔒 تم إغلاق القائمة.")

        await refresh_panel(query.message, list_id)
        return

    # فتح القائمة
    if action == "open_list":
        with connect() as con:
            con.execute("""
                UPDATE reading_lists
                SET is_open = 1
                WHERE id = ?
            """, (list_id,))

        await query.answer("🔓 تم فتح القائمة.")

        await refresh_panel(query.message, list_id)
        return

    # إنشاء قائمة جديدة مع حفظ القديمة
    if action == "new_list":
        with connect() as con:
            con.execute("""
                UPDATE reading_lists
                SET is_active = 0
               WHERE chat_id = ? AND thread_id = ? AND is_active = 1
            """, (chat_id, thread_id))

            number = con.execute("""
                SELECT COUNT(*) FROM reading_lists
                WHERE chat_id = ? AND thread_id = ?
            """, (chat_id, thread_id)).fetchone()[0] + 1

            new_title = f"قائمة ورشيات رقم {number}"

            con.execute("""
                INSERT INTO reading_lists
              (chat_id, thread_id, title, is_open, is_active)
VALUES (?, ?, ?, 1, 1)
            """, (chat_id, thread_id, new_title))

            new_id = con.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

        await query.answer("🌷 تم إنشاء قائمة جديدة.")

        await query.message.reply_text(
            "🌸 <b>تم إنشاء قائمة جديدة بنجاح!</b>\n"
            "📚 القائمة السابقة محفوظة ولن تُحذف.\n"
            "🌷 يمكن للطالبات الجدد التسجيل الآن.\n\n"
            + build_panel(new_id),
            reply_markup=keyboard(new_id),
            parse_mode=ParseMode.HTML
        )
        return


# =========================
# تشغيل البوت
# =========================

def main():
    if not TOKEN:
        raise RuntimeError(
            "ضعي رمز البوت الحقيقي في TOKEN أولًا."
        )

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(CommandHandler("post", post))
    app.add_handler(CommandHandler("archives", archives))

    app.add_handler(
        CallbackQueryHandler(handle_buttons)
    )

    print("🌿 بوت ورشيات طريق التوبة يعمل الآن...")

    app.run_polling()


flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running"

import threading
def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

threading.Thread(target=run_flask, daemon=True).start()
if __name__ == "__main__":
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
