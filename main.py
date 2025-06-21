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
client = OpenAI(api_key="Open AI Key")

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
        input_content = [{"type": "input_text", "text": "You are a music analysis assistant that creates optimized prompts for SUNO AI based on the user's music taste. The user will provide one or more song links or titles. Analyze the provided songs deeply — considering their beats (tempo, rhythm, syncopation), instrumentation (types of instruments used and how they are layered), tone and mood (emotional feel, e.g. happy, dark, melancholic, energetic, relaxed), style (genre/sub-genre, cultural influences, vocal style), production qualities (analog/digital, lo-fi, clean, lush, minimalistic), melodic structure (hooks, vocal phrasing, chord progressions), lyrical themes (stories or emotions conveyed), and vocal processing (natural, auto-tuned, layered, reverb-heavy, etc.). Then generate the following: (1) a Lyrics Prompt of no more than 200 characters to guide SUNO AI’s lyric generation; (2) a Style Description with 1000 char limit, describing in detail the musical style and feel SUNO AI should aim for, mentioning relevant elements such as instruments, mood, beat structure, production style, genre influences, vocal style, and — if the LLM deems it important — whether a male or female voice should be used. Do not include any artist names in this section. (3) Generate a full Song Title to be used for the song — you may include the artist name in the Song Title if you think it enhances the listener’s perception of the song or aligns with the style, but provide only the Song Title here with no explanation. (4) Provide a Reasoning section that explains, in simple and clear language, how the provided songs influenced your choices. Describe what aspects of the songs (beats, mood, instrumentation, lyrical themes, etc.) appeared most commonly or most strongly, what they reveal about the user’s musical preferences, and why you selected this particular Lyrics Prompt, Style Description, and Song Title based on that understanding of the user’s taste."}] + image_blocks

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
    BOT_TOKEN = "Bot api token"
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

    # by jarifdja@caltech.edu
