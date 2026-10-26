from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import discord

from config import settings

from .activity_state import set_pending
from .constants import EMBED_COLOR, MAX_SELECT_OPTIONS
from .engine import MovieItem, SeriesItem, UnlimPlayEngine
from .flight import resolve_stream


def _user_in_voice(interaction: discord.Interaction) -> bool:
    user = interaction.user
    if isinstance(user, discord.Member) and user.voice and user.voice.channel:
        return True
    return False


async def _create_activity_invite(interaction: discord.Interaction) -> Optional[discord.Invite]:
    """
    Invitación nativa de Discord Activity.
    Prioriza el canal de voz del usuario (abre la Activity ahí al unirse).
    """
    client_id = getattr(settings, "DISCORD_CLIENT_ID", None)
    if not client_id:
        return None

    # 1) Canal de voz del usuario (mejor UX: Join entra directo a la Activity)
    voice_ch = None
    user = interaction.user
    if isinstance(user, discord.Member) and user.voice and user.voice.channel:
        voice_ch = user.voice.channel

    targets = []
    if voice_ch is not None:
        targets.append(voice_ch)
    ch = interaction.channel
    if isinstance(ch, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
        if ch not in targets:
            targets.append(ch)

    for channel in targets:
        try:
            return await channel.create_invite(
                max_age=3600,
                max_uses=0,
                unique=True,
                target_type=discord.InviteTarget.embedded_application,
                target_application_id=int(client_id),
                reason="UnlimPlay Activity",
            )
        except Exception:
            continue
    return None


_BG_TASKS: set = set()


def _prewarm(p: Dict[str, Any]) -> None:
    """Resuelve el stream en segundo plano; los clientes reutilizan el resultado."""
    cid = p.get("imdb_id") or p.get("tmdb_id")
    if not cid:
        return
    alt = str(p["tmdb_id"]) if p.get("imdb_id") and p.get("tmdb_id") else None
    try:
        resolve_stream(
            p.get("source") or "unlimplay",
            p.get("type") or "movie",
            str(cid),
            int(p.get("season") or 1),
            int(p.get("episode") or 1),
            alt_id=alt,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[prewarm] {exc}")


async def launch_activity(
    interaction: discord.Interaction,
    *,
    payload: Dict[str, Any],
    fallback_stream_url: str,
) -> None:
    """
    Guarda el contenido pendiente y lanza la Activity.
    Discord exige un clic de 'Unirse' por seguridad; usamos invite en el
    canal de voz para que ese clic entre directo al reproductor.
    """
    # Pending en canal de texto Y de voz (el HTML lee channel_id de la Activity)
    channel = interaction.channel
    channel_id = channel.id if channel else None
    voice_id = None
    user = interaction.user
    if isinstance(user, discord.Member) and user.voice and user.voice.channel:
        voice_id = user.voice.channel.id

    pending_payload = {
        **payload,
        "activity": "unlimplay",
        "requested_by": interaction.user.id,
        "guild_id": interaction.guild.id if interaction.guild else None,
    }
    primary = channel_id if channel_id is not None else voice_id
    if primary is not None:
        set_pending(
            primary,
            pending_payload,
            also=[voice_id] if voice_id not in (None, primary) else [],
            guild_id=pending_payload.get("guild_id"),
        )

    # Mientras el usuario pulsa "Unirse", ya vamos resolviendo el stream.
    task = asyncio.create_task(asyncio.to_thread(_prewarm, pending_payload))
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)

    invite = await _create_activity_invite(interaction)

    if invite is not None:
        # Un solo mensaje: Discord renderiza el panel nativo de Activity.
        # Si el usuario está en voz, al pulsar Unirse entra al player de una.
        await interaction.response.send_message(invite.url)
        return

    view = discord.ui.View(timeout=300)
    view.add_item(
        discord.ui.Button(
            label="Abrir reproductor",
            style=discord.ButtonStyle.link,
            url=fallback_stream_url,
            emoji="▶️",
        )
    )
    note = ""
    if not _user_in_voice(interaction):
        note = (
            "\n⚠️ Únete a un **canal de voz** y asegúrate de que la app "
            "esté configurada como Activity en el Developer Portal."
        )
    await interaction.response.send_message(
        content=(
            f"No pude crear la invitación de Activity.{note}\n"
            f"Usa el reproductor directo:"
        ),
        view=view,
        ephemeral=False,
    )


# ─────────────────────────────────────────────────────────────────────
# PELÍCULAS
# ─────────────────────────────────────────────────────────────────────

class MoviePaginatorView(discord.ui.View):
    """Navegación entre resultados de película: Anterior | Reproducir | Siguiente."""

    def __init__(
        self,
        items: List[MovieItem],
        query: str,
        engine: UnlimPlayEngine,
        *,
        lang: str = "es",
        timeout: Optional[float] = 300,
    ):
        super().__init__(timeout=timeout)
        self.items = items
        self.query = query
        self.engine = engine
        self.lang = (lang or "es").lower()
        self.source = "vidsrc" if self.lang.startswith("en") else "unlimplay"
        self.page = 0
        self._enriched: dict[int, MovieItem] = {}
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear_items()
        total = len(self.items)

        en = self.lang.startswith("en")
        prev_btn = discord.ui.Button(
            label="Previous" if en else "Anterior",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
            disabled=(self.page <= 0),
            row=0,
        )
        prev_btn.callback = self._prev
        self.add_item(prev_btn)

        play_btn = discord.ui.Button(
            label="Play" if en else "Reproducir",
            style=discord.ButtonStyle.success,
            emoji="▶️",
            row=0,
        )
        play_btn.callback = self._play
        self.add_item(play_btn)

        next_btn = discord.ui.Button(
            label="Next" if en else "Siguiente",
            style=discord.ButtonStyle.secondary,
            emoji="➡️",
            disabled=(self.page >= total - 1),
            row=0,
        )
        next_btn.callback = self._next
        self.add_item(next_btn)

    async def _current(self) -> MovieItem:
        item = self.items[self.page]
        if item.tmdb_id not in self._enriched:
            item = await self.engine.enrich_movie_async(item)
            self._enriched[item.tmdb_id] = item
            self.items[self.page] = item
        return item

    async def build_embed(self) -> discord.Embed:
        item = await self._current()
        total = len(self.items)

        lines = []
        en = self.lang.startswith("en")
        if item.year:
            lines.append(f"📅 **{'Year' if en else 'Año'}:** `{item.year}`")
        if item.director:
            lines.append(f"🎬 **Director:** `{item.director}`")
        if item.runtime:
            lines.append(f"⏱️ **{'Runtime' if en else 'Duración'}:** `{item.runtime} min`")
        if item.vote_average and item.vote_average > 0:
            lines.append(f"⭐ **{'Rating' if en else 'Nota'}:** `{item.vote_average:.1f}/10`")
        if item.overview:
            lines.append("\n" + item.overview)

        emb = discord.Embed(
            title=item.title,
            description="\n".join(lines) if lines else ("No extra info." if en else "Sin información adicional."),
            color=EMBED_COLOR,
        )
        if item.poster_url:
            emb.set_image(url=item.poster_url)
        src = "VidSrc" if self.source == "vidsrc" else "UnlimPlay"
        if en:
            emb.set_footer(
                text=f"Movie {self.page + 1} of {total}  •  Search: {self.query}  •  {src}"
            )
        else:
            emb.set_footer(
                text=f"Película {self.page + 1} de {total}  •  Búsqueda: {self.query}  •  {src}"
            )
        return emb

    async def _prev(self, interaction: discord.Interaction) -> None:
        self.page = max(0, self.page - 1)
        self._rebuild()
        emb = await self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.page = min(len(self.items) - 1, self.page + 1)
        self._rebuild()
        emb = await self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def _play(self, interaction: discord.Interaction) -> None:
        item = await self._current()
        stream_url = self.engine.movie_embed_url(item.tmdb_id, item.imdb_id)
        await launch_activity(
            interaction,
            payload={
                "type": "movie",
                "source": self.source,
                "lang": self.lang,
                "tmdb_id": item.tmdb_id,
                "imdb_id": item.imdb_id,
                "title": item.title,
                "year": item.year,
                "poster_url": item.poster_url,
                "embed_url": stream_url,
            },
            fallback_stream_url=stream_url,
        )


# ─────────────────────────────────────────────────────────────────────
# SERIES / ANIME
# ─────────────────────────────────────────────────────────────────────

class SeriesPaginatorView(discord.ui.View):
    """Navegación entre series + selectores de temporada y episodio."""

    def __init__(
        self,
        items: List[SeriesItem],
        query: str,
        engine: UnlimPlayEngine,
        *,
        kind: str = "Serie",
        lang: str = "es",
        timeout: Optional[float] = 300,
    ):
        super().__init__(timeout=timeout)
        self.lang = (lang or "es").lower()
        self.source = "vidsrc" if self.lang.startswith("en") else "unlimplay"
        self.items = items
        self.query = query
        self.engine = engine
        self.kind = kind
        self.page = 0
        self.selected_season: int = 1
        self.selected_episode: int = 1
        self._enriched: dict[int, SeriesItem] = {}
        self._rebuild()

    async def _current(self) -> SeriesItem:
        item = self.items[self.page]
        if item.tmdb_id not in self._enriched:
            item = await self.engine.enrich_series_async(item)
            self._enriched[item.tmdb_id] = item
            self.items[self.page] = item
            if item.seasons:
                self.selected_season = item.seasons[0].season_number
                self.selected_episode = 1
            else:
                self.selected_season = 1
                self.selected_episode = 1
        return item

    def _episode_count_for_season(self, item: SeriesItem, season: int) -> int:
        for s in item.seasons:
            if s.season_number == season:
                return max(1, s.episode_count)
        return 1

    def _rebuild(self) -> None:
        self.clear_items()
        total = len(self.items)
        item = self.items[self.page]
        if item.tmdb_id in self._enriched:
            item = self._enriched[item.tmdb_id]

        en = self.lang.startswith("en")
        prev_btn = discord.ui.Button(
            label="Previous" if en else "Anterior",
            style=discord.ButtonStyle.secondary,
            emoji="⬅️",
            disabled=(self.page <= 0),
            row=0,
        )
        prev_btn.callback = self._prev
        self.add_item(prev_btn)

        play_btn = discord.ui.Button(
            label="Play" if en else "Reproducir",
            style=discord.ButtonStyle.success,
            emoji="▶️",
            row=0,
        )
        play_btn.callback = self._play
        self.add_item(play_btn)

        next_btn = discord.ui.Button(
            label="Next" if en else "Siguiente",
            style=discord.ButtonStyle.secondary,
            emoji="➡️",
            disabled=(self.page >= total - 1),
            row=0,
        )
        next_btn.callback = self._next
        self.add_item(next_btn)

        seasons = item.seasons or []
        if seasons:
            season_opts = []
            for s in seasons[:MAX_SELECT_OPTIONS]:
                season_opts.append(
                    discord.SelectOption(
                        label=s.name[:100],
                        value=str(s.season_number),
                        description=f"{s.episode_count} episodio(s)",
                        emoji="📺",
                        default=(s.season_number == self.selected_season),
                    )
                )
            season_select = discord.ui.Select(
                placeholder=f"📺 Temporada (actual: T{self.selected_season})",
                options=season_opts,
                min_values=1,
                max_values=1,
                row=1,
            )
            season_select.callback = self._on_season
            self.add_item(season_select)

            ep_count = self._episode_count_for_season(item, self.selected_season)
            ep_count = min(ep_count, MAX_SELECT_OPTIONS)
            if self.selected_episode > ep_count:
                self.selected_episode = 1

            ep_opts = []
            for ep in range(1, ep_count + 1):
                ep_opts.append(
                    discord.SelectOption(
                        label=f"Episodio {ep}",
                        value=str(ep),
                        emoji="▶️",
                        default=(ep == self.selected_episode),
                    )
                )
            ep_select = discord.ui.Select(
                placeholder=f"🎬 Episodio (actual: E{self.selected_episode})",
                options=ep_opts,
                min_values=1,
                max_values=1,
                row=2,
            )
            ep_select.callback = self._on_episode
            self.add_item(ep_select)
        else:
            hint = discord.ui.Button(
                label="Cargando temporadas…",
                style=discord.ButtonStyle.secondary,
                disabled=True,
                row=1,
            )
            self.add_item(hint)

    async def build_embed(self) -> discord.Embed:
        item = await self._current()
        self._rebuild()

        total = len(self.items)
        lines = []
        en = self.lang.startswith("en")
        if item.year:
            lines.append(f"📅 **{'Year' if en else 'Año'}:** `{item.year}`")
        if getattr(item, "number_of_seasons", None):
            lines.append(
                f"📚 **{'Seasons' if en else 'Temporadas'}:** `{item.number_of_seasons}`"
            )
        if item.vote_average and item.vote_average > 0:
            lines.append(f"⭐ **{'Rating' if en else 'Nota'}:** `{item.vote_average:.1f}/10`")
        if item.overview:
            lines.append("\n" + item.overview)

        emb = discord.Embed(
            title=item.title,
            description="\n".join(lines) if lines else ("No extra info." if en else "Sin información adicional."),
            color=EMBED_COLOR,
        )
        if item.poster_url:
            emb.set_image(url=item.poster_url)
        src = "VidSrc" if self.source == "vidsrc" else "UnlimPlay"
        kind = self.kind if getattr(self, "kind", None) else "Serie"
        if en:
            kind_en = "Anime" if kind == "Anime" else "Series"
            emb.set_footer(
                text=f"{kind_en} {self.page + 1} of {total}  •  Search: {self.query}  •  {src}"
            )
        else:
            emb.set_footer(
                text=f"{kind} {self.page + 1} de {total}  •  Búsqueda: {self.query}  •  {src}"
            )
        return emb

    async def _prev(self, interaction: discord.Interaction) -> None:
        self.page = max(0, self.page - 1)
        self.selected_season = 1
        self.selected_episode = 1
        emb = await self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def _next(self, interaction: discord.Interaction) -> None:
        self.page = min(len(self.items) - 1, self.page + 1)
        self.selected_season = 1
        self.selected_episode = 1
        emb = await self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def _on_season(self, interaction: discord.Interaction) -> None:
        self.selected_season = int(interaction.data["values"][0])
        self.selected_episode = 1
        self._rebuild()
        emb = await self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def _on_episode(self, interaction: discord.Interaction) -> None:
        self.selected_episode = int(interaction.data["values"][0])
        self._rebuild()
        emb = await self.build_embed()
        await interaction.response.edit_message(embed=emb, view=self)

    async def _play(self, interaction: discord.Interaction) -> None:
        item = await self._current()
        stream_url = self.engine.tv_embed_url(
            item.tmdb_id,
            self.selected_season,
            self.selected_episode,
            item.imdb_id,
        )
        kind = "anime" if self.kind == "Anime" else "tv"
        ep_count = self._episode_count_for_season(item, self.selected_season)
        seasons_meta = [
            {"season": s.season_number, "episodes": s.episode_count}
            for s in (item.seasons or [])
            if s.season_number > 0
        ]
        await launch_activity(
            interaction,
            payload={
                "type": kind,
                "source": self.source,
                "lang": self.lang,
                "tmdb_id": item.tmdb_id,
                "imdb_id": item.imdb_id,
                "title": item.title,
                "year": item.year,
                "poster_url": item.poster_url,
                "season": self.selected_season,
                "episode": self.selected_episode,
                "episode_count": ep_count,
                "number_of_seasons": item.number_of_seasons or len(seasons_meta),
                "seasons": seasons_meta,
                "embed_url": stream_url,
            },
            fallback_stream_url=stream_url,
        )