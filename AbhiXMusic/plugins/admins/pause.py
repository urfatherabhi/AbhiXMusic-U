from pyrogram import filters
from pyrogram.types import Message

from AbhiXMusic import app
from AbhiXMusic.core.call import Hotty
from AbhiXMusic.utils.database import is_music_playing, music_off
from AbhiXMusic.utils.decorators import AdminRightsCheck
from AbhiXMusic.utils.inline import close_markup
from config import BANNED_USERS


@app.on_message(filters.command(["pause", "cpause"]) & filters.group & ~BANNED_USERS)
@AdminRightsCheck
async def pause_admin(cli, message: Message, _, chat_id):
    if not await is_music_playing(chat_id):
        return await message.reply_text(_["admin_1"])
    await music_off(chat_id)
    await Hotty.pause_stream(chat_id)
    await message.reply_text(
        _["admin_2"].format(message.from_user.mention), reply_markup=close_markup(_)
    )
