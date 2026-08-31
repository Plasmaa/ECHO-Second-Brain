import os
import logging
import asyncio
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, Application

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("echo.telegram")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.environ.get("ECHO_API_URL", "http://localhost:8000")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    welcome_text = (
        "👋 *Hello! I am ECHO, your Second Brain & Personal Memory Agent.*\n\n"
        "I remember details about your life, work, relationships, and goals across conversations.\n\n"
        "Commands:\n"
        "• `/facts` — View what I currently remember about you\n"
        "• `/help` — How to interact with ECHO\n\n"
        "Send me any message to start chatting!"
    )
    if update.message:
        await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /help command."""
    help_text = (
        "🧠 *ECHO Second Brain Help*\n\n"
        "As we talk, I continuously extract and update facts about your life.\n"
        "When your circumstances change (e.g. new job, new favorite food, moved cities), "
        "I update the active facts while maintaining full historical memory.\n\n"
        "• Send any regular message to chat with me\n"
        "• Use `/facts` to see all current active memories"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")

async def facts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /facts command."""
    if not update.message:
        return
    await update.message.reply_chat_action("typing")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{API_BASE_URL}/facts")
            if res.status_code != 200:
                await update.message.reply_text("⚠️ Could not reach ECHO Memory API.")
                return

            facts = res.json()
            if not facts:
                await update.message.reply_text("🧠 I don't have any facts stored yet. Tell me about yourself!")
                return

            lines = ["🧠 *Active Facts in Memory:*\n"]
            for f in facts:
                entity = f.get("entity", "").capitalize()
                attr = f.get("attribute", "").replace("_", " ").title()
                val = f.get("value", "")
                lines.append(f"• *{entity} ({attr})*: {val}")

            await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error fetching facts: {e}")
        await update.message.reply_text("⚠️ Failed to connect to ECHO backend.")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for regular text messages."""
    if not update.message or not update.message.text:
        return

    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.reply_chat_action("typing")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                f"{API_BASE_URL}/chat",
                json={"platform": "telegram", "message": user_text}
            )

            if res.status_code != 200:
                await update.message.reply_text("⚠️ ECHO backend encountered an error. Please try again.")
                return

            data = res.json()
            reply_text = data.get("reply", "")
            extracted_facts = data.get("extracted_facts", [])

            # Send main conversational reply
            await update.message.reply_text(reply_text)

            # If facts were extracted or superseded, send subtle memory notification
            if extracted_facts:
                fact_notifs = []
                for f in extracted_facts:
                    icon = "🔄 Updated" if f.get("contradicts_existing") else "✨ Learned"
                    fact_notifs.append(f"{icon}: `{f.get('entity')}.{f.get('attribute')}` = _{f.get('value')}_")
                
                memory_footer = "🧠 *Memory Note:*\n" + "\n".join(fact_notifs)
                await update.message.reply_text(memory_footer, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error processing Telegram message: {e}")
        await update.message.reply_text(f"⚠️ Connection error: {e}")

def create_telegram_app() -> Application:
    """Builds and configures the Telegram bot application instance."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

    t_request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )

    app = ApplicationBuilder().token(token).request(t_request).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("facts", facts_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    return app

def main():
    try:
        app = create_telegram_app()
        logger.info("Starting ECHO Telegram Bot standalone polling...")
        app.run_polling()
    except Exception as e:
        logger.error(f"Could not start bot: {e}")

if __name__ == "__main__":
    main()
