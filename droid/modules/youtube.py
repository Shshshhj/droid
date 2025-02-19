from pathlib import Path

from iytdl import Process, iYTDL
from iytdl.constants import YT_VID_URL
from iytdl.exceptions import NoResultFoundError
from pyrogram.types import (
    CallbackQuery,
    InlineQuery,
    InlineQueryResultPhoto,
    InputMediaPhoto,
)

from .. import mod
from ..decor import OnCallback, OnInline

LOG_CHANNEL_ID = -1001430351422


class YoutubeDL(mod.Module):
    async def on_load(self) -> None:
        cache_path = Path("cache")
        cache_path.mkdir(exist_ok=True)
        self.ytdl = await iYTDL.init(
            session=self.bot.http,
            silent=True,
            loop=self.bot.loop,
            log_group_id=LOG_CHANNEL_ID,
            cache_path=str(cache_path),
            delete_media=True,
        )

    async def on_exit(self) -> None:
        await self.ytdl.stop()

    @OnInline(r"ytdl (.+)", owner_only=True)
    async def on_inline(self, i_q: InlineQuery):
        query = i_q.matches[0].group(1)
        try:
            data = await self.ytdl.parse(query, extract=False)
        except NoResultFoundError:
            return
        await i_q.answer(
            results=[
                InlineQueryResultPhoto(
                    photo_url=data.image_url,
                    title=f"🔍 {query}",
                    description="[click here]",
                    caption=data.caption,
                    reply_markup=data.buttons,
                ),
            ],
            cache_time=1,
        )

    @OnCallback(r"^yt_(back|next)\|(?P<key>[\w-]{5,11})\|(?P<pg>\d+)$", owner_only=True)
    async def callback_next(self, c_q: CallbackQuery):
        match = c_q.matches[0]
        if match.group(1) == "next":
            index = int(match.group("pg")) + 1
        else:
            index = int(match.group("pg")) - 1
        if data := await self.ytdl.next_result(key=match.group("key"), index=index):
            await c_q.edit_message_media(
                media=(
                    InputMediaPhoto(
                        media=data.image_url,
                        caption=data.caption,
                    )
                ),
                reply_markup=data.buttons,
            )
        else:
            await c_q.answer("That's All Folks !", show_alert=True)

    @OnCallback(r"^yt_listall\|(?P<key>[\w-]{5,11})$", owner_only=True)
    async def callback_listall(self, c_q: CallbackQuery):
        await c_q.answer()
        media, buttons = await self.ytdl.listview(c_q.matches[0].group("key"))
        await c_q.edit_message_media(media=media, reply_markup=buttons)

    @OnCallback(r"^yt_extract_info\|(?P<key>[\w-]{5,11})$", owner_only=True)
    async def extract_info(self, c_q: CallbackQuery):
        await c_q.answer()
        key = c_q.matches[0].group("key")
        if data := await self.ytdl.extract_info_from_key(key):
            if len(key) == 11:
                await c_q.edit_message_text(
                    text=data.caption,
                    reply_markup=data.buttons,
                )
            else:
                await c_q.edit_message_media(
                    media=(
                        InputMediaPhoto(
                            media=data.image_url,
                            caption=data.caption,
                        )
                    ),
                    reply_markup=data.buttons,
                )

    @OnCallback(
        r"yt_(?P<mode>gen|dl)\|(?P<key>[\w-]+)\|(?P<choice>[\w-]+)\|(?P<dl_type>a|v)$",
        owner_only=True,
    )
    async def yt_download(self, c_q: CallbackQuery):
        data = c_q.matches[0].group

        if data("mode") == "gen":
            yt_url = False
            video_link = await self.ytdl.cache.get_url(data("key"))
        else:
            yt_url = True
            video_link = f"{YT_VID_URL}{data('key')}"
        print(video_link)

        downtype = "video" if data("dl_type") == "v" else "audio"

        uid, disp_str = self.ytdl.get_choice_by_id(
            data("choice"), downtype, yt_url=yt_url
        )

        await c_q.answer(f"⬇️ Downloading {downtype} - {disp_str}", show_alert=True)

        if key := await self.ytdl.download(
            url=video_link,
            uid=uid,
            downtype=downtype,
            update=c_q,
        ):
            await self.ytdl.upload(
                client=self.bot.client,
                key=key,
                downtype=downtype,
                update=c_q,
                caption_link=video_link,
            )

    @OnCallback(r"^yt_cancel\|(?P<process_id>[\w\.]+)$", owner_only=True)
    async def yt_cancel(self, c_q: CallbackQuery):
        await c_q.answer("Trying to Cancel Process..")
        process_id = c_q.matches[0].group("process_id")
        Process.cancel_id(process_id)
        if c_q.message:
            await c_q.message.delete()
        else:
            await c_q.edit_message_text("`Stopped Successfully`")
