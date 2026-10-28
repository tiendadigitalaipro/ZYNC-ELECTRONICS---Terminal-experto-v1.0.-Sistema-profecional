#!/usr/bin/env python3
"""
ZYNC Electronics Telegram Bot - Single instance deployment for Render.
Uses DeepSeek API and ZYNC product catalog.
Environment: BOT_TOKEN (Telegram), DEEPSEEK_API_KEY
"""

import os
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI

# ─── Config ───
BOT_TOKEN = os.getenv("BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN no definida en variables de entorno")
if not DEEPSEEK_API_KEY:
    raise RuntimeError("❌ DEEPSEEK_API_KEY no definida en variables de entorno")

# ─── DeepSeek Client ───
deepseek = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1",
    timeout=60.0,
)

# ─── ZYNC SYSTEM_PROMPT ───
SYSTEM_PROMPT = """Eres el vendedor estrella de ZYNC Electronics. Atiendes por Telegram.
- Amable, cercano y entusiasta. Usa emojis (1 a 3 por mensaje).
- Respuestas cortas (máximo 120 palabras).
- Regla de oro: Si el cliente dice que está caro, ofrécele llevar 2 productos para ENVÍO GRATIS.
CATÁLOGO OFICIAL:
- 💧 Filtro Purificador de Agua: $11.62
- 🪨 Cartucho de Repuesto: $6.07
- 🔪 Combo de 2 Peladores: $7.87
- 🎙️ Micrófono K9 One: $9.65
- 🎙️ Micrófonos K9 Duos (2 unids): $12.94
- 🎧 Audífonos Airmax: $12.96
- ⌚ Reloj i30 Ultra 3 MAX: $25.99
ENVÍO: Gratis desde 2 productos. Entrega personal en Ocumare del Tuy."""

AUDIO_FALLBACK = "¡Hola! 😊 No puedo escuchar notas de voz, pero si me escribes tu consulta por aquí te atenderé de inmediato. 🎁 ¡Envío GRATIS si llevas 2 productos! 🚚"

# ─── Conversation Memory ───
conversations: dict[int, list[dict]] = {}

# ─── Logging ───
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)


async def ask_brain(chat_id: int, user_text: str) -> str:
    """Query DeepSeek with conversation history."""
    history = conversations.get(chat_id, [])[-10:]
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history, {"role": "user", "content": user_text}]
    resp = await deepseek.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
        max_tokens=300,
    )
    answer = resp.choices[0].message.content.strip()
    conversations.setdefault(chat_id, []).extend([
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": answer},
    ])
    # Keep only last 20 messages
    conversations[chat_id] = conversations[chat_id][-20:]
    return answer


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    msg = update.message
    if not msg or not msg.text or msg.text.startswith("/"):
        return

    if msg.voice or msg.audio:
        await msg.reply_text(AUDIO_FALLBACK)
        return

    await context.bot.send_chat_action(chat_id=msg.chat_id, action="typing")
    try:
        answer = await ask_brain(msg.chat_id, msg.text)
        await msg.reply_text(answer)
    except Exception as e:
        log.error("Error procesando mensaje: %s", e)
        await msg.reply_text("😓 Problemita técnico. Repite por favor.")


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    welcome = (
        "¡Hola! 👋 Soy tu asistente de ZYNC Electronics.\n\n"
        "💧 Filtros de agua\n🎙️ Micrófonos K9\n🎧 Audífonos Airmax\n⌚ Relojes i30 Ultra\n\n"
        "🎁 ¡Envío GRATIS si llevas 2 productos!\n📍 Entrega personal en Ocumare del Tuy\n\n"
        "¿En qué te ayudo hoy? 😊"
    )
    await update.message.reply_text(welcome)


def main() -> None:
    """Run the bot with single-instance polling (prevents 409 Conflict)."""
    # Build application with drop_pending_updates=True to clear old updates
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .drop_pending_updates(True)  # Critical: prevents 409 on restart
        .build()
    )

    application.add_handler(CommandHandler("start", on_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    log.info("🤖 Bot de Telegram ZYNC iniciado (single instance)...")
    # run_polling with close_loop=False for Render compatibility
    application.run_polling(close_loop=False, allowed_updates=["message"])


if __name__ == "__main__":
    main()