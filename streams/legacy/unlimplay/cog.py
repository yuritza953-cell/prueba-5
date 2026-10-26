from __future__ import annotations

import traceback
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.logger import log

from .engine import UnlimPlayEngine
from .views import MoviePaginatorView, SeriesPaginatorView


class UnlimPlay(commands.Cog):
    """
    Películas, series y anime con UnlimPlay.
    Búsqueda por nombre + paginador interactivo.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.engine = UnlimPlayEngine()
        print("🎬 UnlimPlay Cog cargado:", __file__, flush=True)

    def _need_tmdb(self) -> Optional[str]:
        if not self.engine.has_tmdb:
            return (
                "⚠️ Falta la **TMDB API key**.\n"
                "Añade `TMDB_API_KEY=tu_key` en el `.env` "
                "(gratis en https://www.themoviedb.org/settings/api) y reinicia el bot."
            )
        return None

    @staticmethod
    def _normalize_lang(idioma: Optional[str]) -> str:
        """'Español'/'es' → es ; 'English'/'en' → en."""
        v = (idioma or "es").strip().lower()
        if v.startswith("en") or v == "english":
            return "en"
        return "es"

    @app_commands.command(
        name="pelicula",
        description="Busca una película por nombre y reprodúcela",
    )
    @app_commands.describe(
        nombre="Nombre de la película (ej: Super Mario Bros)",
        idioma="Idioma de reproducción: Español (UnlimPlay) o English (VidSrc)",
    )
    @app_commands.choices(
        idioma=[
            app_commands.Choice(name="Español", value="es"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def pelicula(
        self,
        interaction: discord.Interaction,
        nombre: str,
        idioma: Optional[app_commands.Choice[str]] = None,
    ):
        err = self._need_tmdb()
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        nombre = nombre.strip()
        if not nombre:
            await interaction.response.send_message(
                "Escribe el nombre de la película.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            lang = self._normalize_lang(idioma.value if idioma else "es")
            results = await self.engine.search_movies_async(nombre, lang=lang)
            if not results:
                msg = (
                    f"🚫 No movies found for **{nombre}**."
                    if lang == "en"
                    else f"🚫 No encontré películas para **{nombre}**."
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            view = MoviePaginatorView(results, nombre, self.engine, lang=lang)
            embed = await view.build_embed()
            await interaction.followup.send(embed=embed, view=view)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception:
            log.error("Error en /pelicula")
            traceback.print_exc()
            await interaction.followup.send(
                "Hubo un error al buscar la película. Inténtalo de nuevo.",
                ephemeral=True,
            )

    @app_commands.command(
        name="serie",
        description="Busca una serie por nombre y elige temporada/episodio",
    )
    @app_commands.describe(
        nombre="Nombre de la serie (ej: Breaking Bad)",
        idioma="Idioma de reproducción: Español (UnlimPlay) o English (VidSrc)",
    )
    @app_commands.choices(
        idioma=[
            app_commands.Choice(name="Español", value="es"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def serie(
        self,
        interaction: discord.Interaction,
        nombre: str,
        idioma: Optional[app_commands.Choice[str]] = None,
    ):
        err = self._need_tmdb()
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        nombre = nombre.strip()
        if not nombre:
            await interaction.response.send_message(
                "Escribe el nombre de la serie.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            lang = self._normalize_lang(idioma.value if idioma else "es")
            results = await self.engine.search_tv_async(nombre, lang=lang)
            if not results:
                msg = (
                    f"🚫 No series found for **{nombre}**."
                    if lang == "en"
                    else f"🚫 No encontré series para **{nombre}**."
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            view = SeriesPaginatorView(results, nombre, self.engine, kind="Serie", lang=lang)
            embed = await view.build_embed()
            await interaction.followup.send(embed=embed, view=view)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception:
            log.error("Error en /serie")
            traceback.print_exc()
            await interaction.followup.send(
                "Hubo un error al buscar la serie. Inténtalo de nuevo.",
                ephemeral=True,
            )

    @app_commands.command(
        name="anime",
        description="Busca un anime por nombre y elige temporada/episodio",
    )
    @app_commands.describe(
        nombre="Nombre del anime (ej: Attack on Titan)",
        idioma="Idioma de reproducción: Español (UnlimPlay) o English (VidSrc)",
    )
    @app_commands.choices(
        idioma=[
            app_commands.Choice(name="Español", value="es"),
            app_commands.Choice(name="English", value="en"),
        ]
    )
    async def anime(
        self,
        interaction: discord.Interaction,
        nombre: str,
        idioma: Optional[app_commands.Choice[str]] = None,
    ):
        err = self._need_tmdb()
        if err:
            await interaction.response.send_message(err, ephemeral=True)
            return

        nombre = nombre.strip()
        if not nombre:
            await interaction.response.send_message(
                "Escribe el nombre del anime.", ephemeral=True
            )
            return

        await interaction.response.defer(thinking=True)

        try:
            lang = self._normalize_lang(idioma.value if idioma else "es")
            results = await self.engine.search_tv_async(nombre, lang=lang)
            if not results:
                msg = (
                    f"🚫 No anime found for **{nombre}**."
                    if lang == "en"
                    else f"🚫 No encontré anime para **{nombre}**."
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

            view = SeriesPaginatorView(results, nombre, self.engine, kind="Anime", lang=lang)
            embed = await view.build_embed()
            await interaction.followup.send(embed=embed, view=view)
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
        except Exception:
            log.error("Error en /anime")
            traceback.print_exc()
            await interaction.followup.send(
                "Hubo un error al buscar el anime. Inténtalo de nuevo.",
                ephemeral=True,
            )

    @commands.command(name="pelicula", aliases=["movie", "film"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def pelicula_prefix(self, ctx: commands.Context, *, nombre: str = None):
        if not nombre:
            await ctx.reply("Uso: `!pelicula <nombre>` (ej: `!pelicula Super Mario`)")
            return
        err = self._need_tmdb()
        if err:
            await ctx.reply(err)
            return

        msg = await ctx.reply(f"🔎 Buscando **{nombre}**...")
        try:
            results = await self.engine.search_movies_async(nombre, lang="es")
            if not results:
                await msg.edit(content=f"🚫 No encontré películas para **{nombre}**.")
                return
            view = MoviePaginatorView(results, nombre, self.engine, lang="es")
            embed = await view.build_embed()
            await msg.edit(content=None, embed=embed, view=view)
        except Exception:
            log.error("Error en !pelicula")
            traceback.print_exc()
            await msg.edit(content="Error al buscar la película.")

    @commands.command(name="serie", aliases=["tv", "show"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def serie_prefix(self, ctx: commands.Context, *, nombre: str = None):
        if not nombre:
            await ctx.reply("Uso: `!serie <nombre>` (ej: `!serie Breaking Bad`)")
            return
        err = self._need_tmdb()
        if err:
            await ctx.reply(err)
            return

        msg = await ctx.reply(f"🔎 Buscando **{nombre}**...")
        try:
            results = await self.engine.search_tv_async(nombre, lang="es")
            if not results:
                await msg.edit(content=f"🚫 No encontré series para **{nombre}**.")
                return
            view = SeriesPaginatorView(results, nombre, self.engine, kind="Serie", lang="es")
            embed = await view.build_embed()
            await msg.edit(content=None, embed=embed, view=view)
        except Exception:
            log.error("Error en !serie")
            traceback.print_exc()
            await msg.edit(content="Error al buscar la serie.")

    @commands.command(name="anime")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anime_prefix(self, ctx: commands.Context, *, nombre: str = None):
        if not nombre:
            await ctx.reply("Uso: `!anime <nombre>` (ej: `!anime Attack on Titan`)")
            return
        err = self._need_tmdb()
        if err:
            await ctx.reply(err)
            return

        msg = await ctx.reply(f"🔎 Buscando **{nombre}**...")
        try:
            results = await self.engine.search_tv_async(nombre, lang="es")
            if not results:
                await msg.edit(content=f"🚫 No encontré anime para **{nombre}**.")
                return
            view = SeriesPaginatorView(results, nombre, self.engine, kind="Anime", lang="es")
            embed = await view.build_embed()
            await msg.edit(content=None, embed=embed, view=view)
        except Exception:
            log.error("Error en !anime")
            traceback.print_exc()
            await msg.edit(content="Error al buscar el anime.")