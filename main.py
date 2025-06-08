import os
import time
import logging
from openai import OpenAI
from telegram import Update, ReplyKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Initialize OpenAI client
client = OpenAI(api_key="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")

# States for conversation
ASK_FOR_MORE_SONGS = 1

# Directory to store screenshots
SCREENSHOT_DIR = "user_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.info(f"User {user_id} started the bot.")
    await update.message.reply_text(
        "Hi! Please send me your playlist link or screenshots of your playlist so I can analyze your music taste."
    )

# Handle receiving a playlist link or screenshot
async def receive_playlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = context.user_data

    if update.message.photo:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_path = os.path.join(SCREENSHOT_DIR, f"user_{user_id}_screenshot_{int(time.time())}.jpg")
        await file.download_to_drive(file_path)

        user_data.setdefault("playlist_images", []).append(file_path)
        logging.info(f"User {user_id} sent a screenshot: {file_path}")

    elif update.message.text:
        message_content = update.message.text.strip()
        user_data.setdefault("playlist_data", []).append(message_content)
        logging.info(f"User {user_id} sent playlist link/text.")

    else:
        await update.message.reply_text("Please send a valid playlist link or screenshot.")
        return ConversationHandler.END

    reply_keyboard = [["Yes", "No"]]
    await update.message.reply_text(
        "Do you want to add more songs or screenshots?",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    )
    return ASK_FOR_MORE_SONGS

# Handle the user’s response to whether they want to add more songs
async def ask_for_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip().lower()

    if text == "yes":
        await update.message.reply_text("Please send another song, playlist link, or screenshot.")
        return ConversationHandler.END
    else:
        await update.message.reply_text("Thanks! I'll analyze your playlist now. 🎧")

        user_data = context.user_data
        playlist_data = user_data.get("playlist_data", [])
        playlist_text = "\n".join(playlist_data)

        image_paths = user_data.get("playlist_images", [])
        image_blocks = []

        # Upload images to OpenAI and construct input content
        for path in image_paths:
            with open(path, "rb") as file_content:
                file_obj = client.files.create(file=file_content, purpose="vision")
                image_blocks.append({
                    "type": "input_image",
                    "file_id": file_obj.id
                })

        # Build the request content
        input_content = [{"type": "input_text", "text": "Analyze this music playlist and describe the genres, moods, and user preference."}] + image_blocks

        if playlist_text:
            input_content.insert(0, {"type": "input_text", "text": f"Here are some playlist links or text data:\n{playlist_text}"})

        try:
            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[{
                    "role": "user",
                    "content": input_content
                }]
            )
            analysis = response.output_text
            logging.info(f"User {user_id} analysis completed.")

            await update.message.reply_text(f"Here's your personalized music profile:\n\n{analysis}")

        except Exception as e:
            logging.error(f"OpenAI error for user {user_id}: {e}")
            await update.message.reply_text("There was an error analyzing your playlist. Please try again later.")

        # Delete images
        for img_path in image_paths:
            if os.path.exists(img_path):
                os.remove(img_path)
                logging.info(f"Deleted screenshot {img_path}")

        return ConversationHandler.END

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logging.info(f"User {user_id} cancelled the conversation.")
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

if __name__ == '__main__':
    BOT_TOKEN = "7881105998:AAGxlndN3hnOQqbO1iw8OoTzk7cG-OfeH-M"
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT | filters.PHOTO, receive_playlist)],
        states={
            ASK_FOR_MORE_SONGS: [
                MessageHandler(filters.Regex("^(Yes|No)$"), ask_for_more),
                MessageHandler(filters.TEXT | filters.PHOTO, receive_playlist)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv_handler)
    print("Bot is running...")
    app.run_polling()
