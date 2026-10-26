"""
Estado temporal de lo que se va a reproducir en la Discord Activity.

Claves: channel_id (texto y voz) y, como respaldo, guild_id.
- Leer NO borra: todos los que entren a la MISMA instancia de la Activity
  (instance_id del SDK de Discord) ven lo mismo, aunque se unan después.
- La primera lectura "ata" el pending a su instancia; otra instancia nueva
  (p.ej. abrir otra Activity en el canal) ya no lo ve → no se repite la peli vieja.
- TTL de 30 min para que no se quede para siempre.
- Thread-safe (Flask corre en hilos).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, Iterable, Optional

_PENDING: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_TTL_SECONDS = 30 * 60


def _k(channel_id: int | str) -> str:
    return f"c:{channel_id}"


def _g(guild_id: int | str) -> str:
    return f"g:{guild_id}"


def set_pending(
    channel_id: int | str,
    payload: Dict[str, Any],
    *,
    also: Iterable[int | str] = (),
    guild_id: int | str | None = None,
) -> None:
    """Guarda el pending bajo el canal, canales extra (p.ej. voz) y el guild."""
    data = {**payload, "_ts": time.time()}
    with _LOCK:
        _PENDING[_k(channel_id)] = data
        for extra in also:
            if extra is not None:
                _PENDING[_k(extra)] = data
        gid = guild_id or payload.get("guild_id")
        if gid:
            _PENDING[_g(gid)] = data


def get_pending(
    channel_id: int | str | None,
    *,
    guild_id: int | str | None = None,
    instance_id: str | None = None,
    consume: bool = False,
) -> Optional[Dict[str, Any]]:
    now = time.time()
    keys = []
    if channel_id:
        keys.append(_k(channel_id))
    if guild_id:
        keys.append(_g(guild_id))  # respaldo si el canal de voz no coincide
    with _LOCK:
        for key in keys:
            data = _PENDING.get(key)
            if not data:
                continue
            if now - data.get("_ts", 0) > _TTL_SECONDS:
                _PENDING.pop(key, None)
                continue
            if instance_id:
                bound = data.get("_instance")
                if bound is None:
                    data["_instance"] = instance_id      # primera lectura: la ata
                elif bound != instance_id:
                    continue                             # otra sesión: ya fue usado
            out = {k: v for k, v in data.items() if not k.startswith("_")}
            if consume:
                _PENDING.pop(key, None)
            return out
    return None


def clear_pending(channel_id: int | str) -> None:
    with _LOCK:
        _PENDING.pop(_k(channel_id), None)


def cleanup_expired() -> None:
    now = time.time()
    with _LOCK:
        dead = [k for k, v in _PENDING.items() if now - v.get("_ts", 0) > _TTL_SECONDS]
        for k in dead:
            _PENDING.pop(k, None)