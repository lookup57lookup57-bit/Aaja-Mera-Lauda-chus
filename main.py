import os
import asyncio
import logging
import time
from typing import Optional, List
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest

# Configuration
BOT_TOKEN = "8706943346:AAGKYoyf-u5McVll4RQcujt8n0uCbeYLVVw"  # Replace with your token
FORCE_SUB_CHANNELS = ["@Ninjahattori900"]  # Add your channel
ADMIN_IDS = [7935621079]

# User cooldown tracking
user_cooldowns = {}

logging.basicConfig(
    format='%(asctime)s │ %(name)s │ %(levelname)s │ %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class UI:
    LOGO = "🎬"
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    LOADING = "⏳"
    DOWNLOAD = "⬇️"
    UPLOAD = "📤"
    SEARCH = "🔍"
    QUALITY = "🎥"
    USER = "👤"
    TIME = "⏱"
    LOCK = "🔒"
    UNLOCK = "🔓"
    CHANNEL = "📢"
    STAR = "⭐"
    
    @staticmethod
    def divider(char: str = "━") -> str:
        return char * 20

class VideoDownloader:
    def __init__(self):
        self.download_path = "downloads"
        os.makedirs(self.download_path, exist_ok=True)
    
    def get_ydl_opts(self, quality: str, output_path: str) -> dict:
        format_spec = {
            'best': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]',
            '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]',
            '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]',
            '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]'
        }.get(quality, 'best[ext=mp4]')
        
        return {
            'format': format_spec,
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        }
    
    async def get_video_info(self, url: str) -> Optional[dict]:
        try:
            loop = asyncio.get_event_loop()
            ydl_opts = {'quiet': True, 'skip_download': True}
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown Channel'),
                    'thumbnail': info.get('thumbnail'),
                    'view_count': info.get('view_count') or 0,  # Fix NoneType error
                }
        except Exception as e:
            logger.error(f"Info extraction error: {e}")
            return None
    
    async def download(self, url: str, quality: str, progress_callback=None) -> Optional[str]:
        try:
            loop = asyncio.get_event_loop()
            output_path = os.path.join(self.download_path, str(int(time.time())))
            os.makedirs(output_path, exist_ok=True)
            
            ydl_opts = self.get_ydl_opts(quality, output_path)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, lambda: ydl.download([url]))
                
                files = os.listdir(output_path)
                if files:
                    return os.path.join(output_path, files[0])
                return None
                
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None
    
    def cleanup(self, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                dir_path = os.path.dirname(file_path)
                if os.path.exists(dir_path) and not os.listdir(dir_path):
                    os.rmdir(dir_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

downloader = VideoDownloader()

async def check_force_sub(user_id: int, bot) -> tuple[bool, List[str]]:
    not_joined = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await bot.get_chat_member(channel, user_id)
            if member.status in [ChatMember.LEFT, ChatMember.BANNED]:
                not_joined.append(channel)
        except Exception as e:
            logger.error(f"Force sub check error: {e}")
            not_joined.append(channel)
    return len(not_joined) == 0, not_joined

async def force_sub_message(update: Update, not_joined: List[str]) -> None:
    buttons = []
    text = f"""
{UI.LOGO} <b><u>Vɪᴅᴇᴏ Dᴏᴡɴʟᴏᴀᴅᴇʀ Bᴏᴛ</u></b>

{UI.LOCK} <b>Aᴄᴄᴇss Rᴇsᴛʀɪᴄᴛᴇᴅ</b>
Yᴏᴜ ɴᴇᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ!

{UI.CHANNEL} <b>Rᴇǫᴜɪʀᴇᴅ Cʜᴀɴɴᴇʟs:</b>
"""
    for i, channel in enumerate(not_joined, 1):
        ch_name = channel.replace("@", "").replace("_", " ").title()
        text += f"\n{i}. {channel}"
        buttons.append([InlineKeyboardButton(f"{UI.UNLOCK} Join {ch_name}", url=f"https://t.me/{channel.replace('@', '')}")])
    
    buttons.append([InlineKeyboardButton(f"{UI.SUCCESS} I'ᴠᴇ Jᴏɪɴᴇᴅ", callback_data="check_sub")])
    
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    is_subbed, not_joined = await check_force_sub(user.id, context.bot)
    if not is_subbed:
        await force_sub_message(update, not_joined)
        return
    
    welcome_text = f"""
{UI.LOGO} <b><u>Vɪᴅᴇᴏ Dᴏᴡɴʟᴏᴀᴅᴇʀ Bᴏᴛ Pʀᴏ</u></b> {UI.STAR}

<b>Hᴇʏ {user.first_name}! 👋</b>

<blockquote>
{UI.SUCCESS} <b>Sᴜᴘᴘᴏʀᴛᴇᴅ Pʟᴀᴛғᴏʀᴍs:</b>
{UI.CHANNEL} YᴏᴜTᴜʙᴇ, Iɴsᴛᴀɢʀᴀᴍ, Fᴀᴄᴇʙᴏᴏᴋ

{UI.QUALITY} <b>Fᴇᴀᴛᴜʀᴇs:</b>
• 4K/HDR Sᴜᴘᴘᴏʀᴛ
• Nᴏ Wᴀᴛᴇʀᴍᴀʀᴋ
• Fᴀsᴛ Dᴏᴡɴʟᴏᴀᴅ
</blockquote>

<b>Sᴇɴᴅ ᴀ ᴠɪᴅᴇᴏ ʟɪɴᴋ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ... 🚀</b>
"""
    
    keyboard = [[InlineKeyboardButton(f"{UI.CHANNEL} Cʜᴀɴɴᴇʟ", url=f"https://t.me/{FORCE_SUB_CHANNELS[0].replace('@', '')}")]]
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    
    is_subbed, not_joined = await check_force_sub(user.id, context.bot)
    
    if is_subbed:
        await query.answer(f"{UI.SUCCESS} Vᴇʀɪғɪᴇᴅ!", show_alert=True)
        # Simulate start command
        fake_update = type('obj', (object,), {
            'effective_user': user,
            'message': query.message
        })()
        await start(fake_update, context)
    else:
        await query.answer(f"{UI.ERROR} Pʟᴇᴀsᴇ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ғɪʀsᴛ!", show_alert=True)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()
    
    # Check Force Sub
    is_subbed, not_joined = await check_force_sub(user.id, context.bot)
    if not is_subbed:
        await force_sub_message(update, not_joined)
        return
    
    # Check URL
    supported = ['youtube.com', 'youtu.be', 'instagram.com', 'facebook.com', 'fb.watch']
    if not any(x in url.lower() for x in supported):
        await update.message.reply_text(f"{UI.ERROR} Usɴᴜᴘᴘᴏʀᴛᴇᴅ URL!", parse_mode=ParseMode.HTML)
        return
    
    # Processing message
    processing_msg = await update.message.reply_text(f"{UI.SEARCH} Aɴᴀʟʏᴢɪɴɢ...", parse_mode=ParseMode.HTML)
    
    info = await downloader.get_video_info(url)
    if not info:
        await processing_msg.edit_text(f"{UI.ERROR} Fᴀɪʟᴇᴅ ᴛᴏ ғᴇᴛᴄʜ ᴠɪᴅᴇᴏ!", parse_mode=ParseMode.HTML)
        return
    
    # Store data
    context.user_data['video_url'] = url
    context.user_data['video_title'] = info['title']
    context.user_data['message_id'] = processing_msg.message_id
    context.user_data['chat_id'] = update.effective_chat.id
    
    duration_mins = info['duration'] // 60 if info['duration'] else 0
    
    qualities = [
        ('🎬 Best Quality (4K)', 'best'),
        ('🎥 Full HD (1080p)', '1080p'),
        ('📺 HD (720p)', '720p'),
        ('📱 SD (480p)', '480p'),
        ('💾 Low (360p)', '360p')
    ]
    
    keyboard = [[InlineKeyboardButton(name, callback_data=f"quality:{q}")] for name, q in qualities]
    keyboard.append([InlineKeyboardButton(f"{UI.ERROR} Cᴀɴᴄᴇʟ", callback_data="cancel")])
    
    info_text = f"""
{UI.QUALITY} <b>{info['title'][:50]}{'...' if len(info['title']) > 50 else ''}</b>

{UI.divider('─')}
{UI.USER} <b>Cʜᴀɴɴᴇʟ:</b> <code>{info['uploader'][:30]}</code>
{UI.TIME} <b>Dᴜʀᴀᴛɪᴏɴ:</b> {duration_mins} ᴍɪɴ
{UI.STAR} <b>Vɪᴇᴡs:</b> {info['view_count']:,}

<b>Sᴇʟᴇᴄᴛ Qᴜᴀʟɪᴛʏ:</b>
"""
    
    try:
        if info['thumbnail']:
            await update.message.reply_photo(
                photo=info['thumbnail'],
                caption=info_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            await processing_msg.delete()
        else:
            await processing_msg.edit_text(info_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await processing_msg.edit_text(info_text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    
    # SPAM PROTECTION: Check cooldown
    current_time = time.time()
    if user_id in user_cooldowns:
        if current_time - user_cooldowns[user_id] < 3:  # 3 seconds cooldown
            await query.answer("⏳ Pʟᴇᴀsᴇ ᴡᴀɪᴛ...", show_alert=True)
            return
    
    user_cooldowns[user_id] = current_time
    await query.answer()
    
    if query.data == "cancel":
        try:
            await query.delete_message()
        except:
            pass
        return
    
    if query.data.startswith("quality:"):
        quality = query.data.split(":")[1]
        url = context.user_data.get('video_url')
        title = context.user_data.get('video_title', 'Video')
        
        if not url:
            await query.answer("Sᴇssɪᴏɴ ᴇxᴘɪʀᴇᴅ!", show_alert=True)
            return
        
        # IMPORTANT: Check if message is photo or text
        is_photo = query.message.photo is not None
        
        status_text = f"{UI.DOWNLOAD} <b>Dᴏᴡɴʟᴏᴀᴅɪɴɢ...</b>\n\n<b>Tɪᴛʟᴇ:</b> <code>{title[:40]}</code>\n<b>Qᴜᴀʟɪᴛʏ:</b> <code>{quality}</code>\n\n<code>[░░░░░░░░░░] 0%</code>"
        
        try:
            if is_photo:
                # Edit caption for photos
                await query.edit_message_caption(caption=status_text, parse_mode=ParseMode.HTML)
            else:
                # Edit text for text messages
                await query.edit_message_text(status_text, parse_mode=ParseMode.HTML)
        except BadRequest as e:
            logger.error(f"Edit error: {e}")
            # If edit fails, send new message
            await context.bot.send_message(chat_id=update.effective_chat.id, text=status_text, parse_mode=ParseMode.HTML)
        
        # Download
        file_path = await downloader.download(url, quality)
        
        if not file_path:
            error_text = f"{UI.ERROR} <b>Dᴏᴡɴʟᴏᴀᴅ Fᴀɪʟᴇᴅ!</b>\nVɪᴅᴇᴏ ᴍᴀʏ ʙᴇ ᴘʀɪᴠᴀᴛᴇ ᴏʀ ᴛᴏᴏ ʟᴀʀɢᴇ."
            try:
                if is_photo:
                    await query.edit_message_caption(caption=error_text, parse_mode=ParseMode.HTML)
                else:
                    await query.edit_message_text(error_text, parse_mode=ParseMode.HTML)
            except:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=error_text, parse_mode=ParseMode.HTML)
            return
        
        file_size = os.path.getsize(file_path)
        size_mb = file_size / (1024 * 1024)
        
        try:
            upload_text = f"{UI.UPLOAD} <b>Uᴘʟᴏᴀᴅɪɴɢ...</b>\n<code>{size_mb:.1f} MB</code>"
            try:
                if is_photo:
                    await query.edit_message_caption(caption=upload_text, parse_mode=ParseMode.HTML)
                else:
                    await query.edit_message_text(upload_text, parse_mode=ParseMode.HTML)
            except:
                pass
            
            caption = f"{UI.SUCCESS} <b>Dᴏᴡɴʟᴏᴀᴅ Cᴏᴍᴘʟᴇᴛᴇ!</b>\n\n<b>Qᴜᴀʟɪᴛʏ:</b> <code>{quality}</code>\n<b>Sɪᴢᴇ:</b> <code>{size_mb:.1f} MB</code>"
            
            with open(file_path, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=video_file,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300
                )
            
            # Delete the original selection message
            try:
                await query.delete_message()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Upload error: {e}")
            error_text = f"{UI.ERROR} Uᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ: {str(e)[:100]}"
            await context.bot.send_message(chat_id=update.effective_chat.id, text=error_text, parse_mode=ParseMode.HTML)
        finally:
            downloader.cleanup(file_path)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Proper async error handler"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if isinstance(context.error, BadRequest):
        if "There is no text in the message" in str(context.error):
            logger.info("Ignored photo edit error")
            return
    
    # Notify user
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(f"{UI.ERROR} An error occurred. Please try again.")
        except:
            pass

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^(quality:|cancel)"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    # Error handler - MUST be async function
    application.add_error_handler(error_handler)
    
    print("✅ Fixed bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
