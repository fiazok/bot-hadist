# handlers.py (v2)
# Teks polos (tanpa parse_mode) agar tidak gagal oleh karakter _ * [ dari API.
# Navigasi lewat tombol (edit pesan), sumber HadeethEnc.com selalu dicantumkan.
import logging
from typing import List, Optional

from telegram import InlineKeyboardButton as Btn, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import api_client as api
from config import ADMIN_ID

logger = logging.getLogger(__name__)

LANG = "id"
PER_PAGE = 8
MAX_LEN = 3800
MAX_RESULTS = 10
FOOTER = "\n\nSumber: HadeethEnc.com"
ERR_API = "⚠️ Server HadeethEnc sedang tidak bisa dihubungi. Coba lagi sebentar lagi."


# ---------- helper ----------

def _chunks(text: str, n: int = MAX_LEN) -> List[str]:
    out = []
    while len(text) > n:
        cut = text.rfind("\n", 0, n)
        cut = cut if cut > n // 2 else n
        out.append(text[:cut])
        text = text[cut:].lstrip("\n")
    out.append(text)
    return out


def _markup(rows: Optional[list] = None) -> InlineKeyboardMarkup:
    nav = [Btn("🏠 Beranda", callback_data="menu_home"),
           Btn("📚 Kategori", callback_data="menu_kategori"),
           Btn("🔍 Cari", callback_data="menu_cari")]
    return InlineKeyboardMarkup((rows or []) + [nav])


async def _send(update: Update, text: str, markup=None, edit: bool = True) -> None:
    """Kirim/edit pesan. Teks panjang dipecah; tombol di bagian terakhir."""
    parts = _chunks(text)
    q = update.callback_query
    if edit and q and len(parts) == 1:
        try:
            await q.edit_message_text(parts[0], reply_markup=markup,
                                      disable_web_page_preview=True)
            return
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return
    msg = update.effective_message
    for i, p in enumerate(parts):
        await msg.reply_text(p, disable_web_page_preview=True,
                             reply_markup=markup if i == len(parts) - 1 else None)


def _parse_id(arg: str) -> Optional[int]:
    base = arg.split("-")[0]
    return int(base) if base.isdigit() else None


def _is_shahih(grade: str) -> bool:
    g = (grade or "").lower()
    return "shahih" in g or "sahih" in g


# ---------- perintah ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("await_search", None)
    text = (
        "🕌 Bot Hadist - baca hadist dari HadeethEnc.com\n\n"
        "Perintah:\n"
        "/kategori - daftar kategori\n"
        "/daftar <id_kategori> [halaman] - daftar hadist\n"
        "/hadist <id> [bahasa] - terjemah, perawi, derajat\n"
        "/arab <id> - teks Arab\n"
        "/cari <kata> - cari berdasarkan judul\n\n"
        "Contoh: /hadist 2962"
    )
    await _send(update, text + FOOTER, _markup())


async def cmd_kategori(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cats = await api.get_categories_roots(LANG)
    except api.ApiError:
        await _send(update, ERR_API, _markup())
        return
    if not cats:
        await _send(update, "Belum ada kategori." + FOOTER, _markup())
        return
    rows = [[Btn(f"{c.get('title')} ({c.get('hadeeths_count', '?')})"[:60],
                 callback_data=f"list:{c.get('id')}:1")] for c in cats]
    await _send(update, "📚 Pilih kategori:" + FOOTER, _markup(rows))


async def _show_list(update: Update, cat: int, page: int):
    try:
        data = await api.get_hadiths_list(LANG, cat, page, PER_PAGE)
    except api.ApiError:
        await _send(update, ERR_API, _markup())
        return
    items = data.get("data", [])
    if not items:
        await _send(update, f"Tidak ada hadist di kategori {cat} halaman {page}." + FOOTER,
                    _markup())
        return
    meta = data.get("meta") or {}
    try:
        last = int(meta.get("last_page") or 0)
    except (TypeError, ValueError):
        last = 0
    has_next = page < last if last else len(items) >= PER_PAGE
    rows = [[Btn((h.get("title") or f"Hadis {h.get('id')}")[:55],
                 callback_data=f"h:{h.get('id')}")] for h in items]
    nav = []
    if page > 1:
        nav.append(Btn("◀ Sebelumnya", callback_data=f"list:{cat}:{page - 1}"))
    if has_next:
        nav.append(Btn("Berikutnya ▶", callback_data=f"list:{cat}:{page + 1}"))
    if nav:
        rows.append(nav)
    total = meta.get("total_items")
    head = f"📚 Kategori {cat} - halaman {page}" + (f"/{last}" if last else "")
    if total:
        head += f" ({total} hadist)"
    await _send(update, head + FOOTER, _markup(rows))


async def cmd_daftar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await _send(update, "Format: /daftar <id_kategori> [halaman]\nContoh: /daftar 1",
                    _markup())
        return
    page = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 1
    await _show_list(update, int(context.args[0]), max(page, 1))


async def _show_hadith(update: Update, hid: int, lang: str = LANG):
    try:
        h = await api.get_hadith_one(hid, lang)
    except api.ApiError:
        await _send(update, ERR_API, _markup(), edit=False)
        return
    if not h:
        await _send(update, f"Hadis #{hid} tidak ditemukan." + FOOTER, _markup(), edit=False)
        return
    grade = h.get("grade") or ""
    parts = [h.get("title", ""), "", h.get("hadeeth", ""), ""]
    if h.get("attribution"):
        parts.append(f"Perawi: {h['attribution']}")
    parts.append(f"Derajat: {grade or '(tidak tersedia)'}")
    if h.get("reference"):
        parts.append(f"Rujukan: {h['reference']}")
    if h.get("explanation"):
        parts += ["", "Penjelasan:", h["explanation"]]
    if not _is_shahih(grade):
        parts += ["", "⚠️ Derajat bukan 'shahih' atau tidak terbaca. Periksa sebelum dikutip."]
    parts.append(f"\nID HadeethEnc: {hid}")
    rows = [[Btn("🇸🇦 Teks Arab", callback_data=f"ar:{hid}")]]
    await _send(update, "\n".join(parts) + FOOTER, _markup(rows), edit=False)


async def _show_arabic(update: Update, hid: int):
    try:
        h = await api.get_hadith_one(hid, "ar")
    except api.ApiError:
        await _send(update, ERR_API, _markup(), edit=False)
        return
    text = (h.get("hadeeth") or "(tidak tersedia)") + f"\n\nID HadeethEnc: {hid}"
    await _send(update, text + FOOTER, _markup(), edit=False)


async def cmd_hadist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hid = _parse_id(context.args[0]) if context.args else None
    if hid is None:
        await _send(update, "Format: /hadist <id> [bahasa]\nContoh: /hadist 2962", _markup())
        return
    lang = context.args[1] if len(context.args) > 1 else (
        context.args[0].split("-", 1)[1] if "-" in context.args[0] else LANG)
    await _show_hadith(update, hid, lang or LANG)


async def cmd_arab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    hid = _parse_id(context.args[0]) if context.args else None
    if hid is None:
        await _send(update, "Format: /arab <id>\nContoh: /arab 2962", _markup())
        return
    await _show_arabic(update, hid)


async def _do_search(update: Update, query: str):
    async def notify():
        await update.effective_message.reply_text(
            "Membangun indeks hadist (hanya sekali, bisa beberapa menit)...")
    try:
        index = await api.get_index(on_build=notify)
    except api.ApiError:
        await _send(update, ERR_API, _markup(), edit=False)
        return
    hits = api.search_index(index, query)
    if not hits:
        await _send(update, f"Tidak ditemukan untuk '{query}' (pencarian hanya pada judul). "
                            "Coba kata lain atau buka /kategori." + FOOTER,
                    _markup(), edit=False)
        return
    rows = [[Btn((t or f"Hadis {i}")[:55], callback_data=f"h:{i}")]
            for i, t in hits[:MAX_RESULTS]]
    note = (f"\nMenampilkan {MAX_RESULTS} dari {len(hits)}, persempit kata kunci."
            if len(hits) > MAX_RESULTS else "")
    await _send(update, f"🔍 Hasil untuk '{query}': {len(hits)} hadist.{note}" + FOOTER,
                _markup(rows), edit=False)


async def cmd_cari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip()
    if not query:
        context.user_data["await_search"] = True
        await _send(update, "Ketik kata kunci yang ingin dicari (pada judul hadist).",
                    _markup(), edit=False)
        return
    await _do_search(update, query)


async def cmd_perbarui(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_ID or str(update.effective_user.id) != ADMIN_ID:
        await _send(update, "Perintah ini hanya untuk admin (set ADMIN_ID).", edit=False)
        return
    await update.effective_message.reply_text("Membangun ulang indeks...")
    try:
        n = await api.refresh_index()
    except api.ApiError:
        await update.effective_message.reply_text(ERR_API)
        return
    await update.effective_message.reply_text(f"Selesai. {n} hadist terindeks.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.pop("await_search", False):
        await _do_search(update, (update.message.text or "").strip())
    else:
        await cmd_start(update, context)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data or ""
    try:
        if d in ("menu_home", "menu_help"):
            await cmd_start(update, context)
        elif d == "menu_kategori":
            await cmd_kategori(update, context)
        elif d == "menu_cari":
            context.user_data["await_search"] = True
            await _send(update, "Ketik kata kunci yang ingin dicari (pada judul hadist).",
                        _markup(), edit=False)
        elif d.startswith("list:"):
            _, cat, page = d.split(":")
            await _show_list(update, int(cat), int(page))
        elif d.startswith("h:") and d[2:].isdigit():
            await _show_hadith(update, int(d[2:]))
        elif d.startswith("ar:") and d[3:].isdigit():
            await _show_arabic(update, int(d[3:]))
    except ValueError:
        logger.warning("callback_data tidak valid: %r", d)
