import os
import logging
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("echo_telegram_bot")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.environ.get("ECHO_API_URL", "http://localhost:8000")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    welcome_text = (
        "👋 *Hello! I am ECHO, your Second Brain & Personal Memory Agent.*\n\n"
        "I remember your life, work, relationships, and goals across conversations.\n\n"
        "Commands:\n"
        "• `/facts` — View what I currently remember about you\n"
        "• `/help` — How to interact with ECHO\n\n"
        "Just send me a message to start chatting!"
    )
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
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def facts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /facts command."""
    await update.message.reply_chat_action("typing")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
    user_text = update.message.text.strip()
    if not user_text:
        return

    await update.message.reply_chat_action("typing")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
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

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN is not configured in .env. Please set it to run the Telegram bot.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("facts", facts_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Starting ECHO Telegram Bot polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
