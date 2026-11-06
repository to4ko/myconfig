import asyncio
import ipaddress
import json
import logging
import time
import uuid
from asyncio import Future
from typing import Callable, Dict, Optional

from aiohttp import ClientError, ClientWebSocketResponse, WSMsgType
from zeroconf import ServiceBrowser, ServiceStateChange, Zeroconf

from .yandex_session import YandexSession

_LOGGER = logging.getLogger(__name__)


class YandexGlagol:
    """Класс для работы с колонкой по локальному протоколу."""

    device_token = None
    url: Optional[str] = None
    ws: Optional[ClientWebSocketResponse] = None

    update_handler: Callable = None

    waiters: Dict[str, Future] = {}

    def __init__(self, session: YandexSession, device: dict):
        self.session = session
        self.device = device
        self.loop = asyncio.get_event_loop()

    def debug(self, text: str):
        _LOGGER.debug(f"{self.device['name']} | {text}")

    def is_device(self, device: str):
        return (
            self.device["quasar_info"]["device_id"] == device
            or self.device["name"] == device
        )

    @property
    def name(self):
        return self.device["name"]

    async def get_device_token(self):
        self.debug("Обновление токена устройства")

        payload = {
            "device_id": self.device["quasar_info"]["device_id"],
            "platform": self.device["quasar_info"]["platform"],
        }
        r = await self.session.get(
            "https://quasar.yandex.net/glagol/token", params=payload
        )
        # @dext0r: fix bug with wrong content-type
        resp = json.loads(await r.text())
        assert resp["status"] == "ok", resp

        return resp["token"]

    async def start_or_restart(self):
        # first time
        if not self.url:
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            _ = asyncio.create_task(self._connect(0))

        # check IP change
        elif self.device["host"] not in self.url:
            self.debug("Обновление IP-адреса устройства")
            self.url = f"wss://{self.device['host']}:{self.device['port']}"
            # force close session
            if self.ws:
                await self.ws.close()

    async def stop(self):
        self.debug("Останавливаем локальное подключение")
        self.url = None
        if self.ws:
            await self.ws.close()

    async def _connect(self, fails: int):
        self.debug("Локальное подключение")

        fails += 1  # will be reset with first msg from station
        ws = None
        connection_token = None
        connected_at = time.monotonic()
        last_message_at = None
        close_reason = ""
        error_type = None
        player = {}
        keep_task = None
        keep_state = {"sent": 0}

        try:
            if not self.device_token:
                self.device_token = await self.get_device_token()

            connection_token = self.device_token
            ws = await self.session.ws_connect(self.url, heartbeat=55, ssl=False)
            self.ws = ws
            connected_at = time.monotonic()
            await self.ping(command="softwareVersion")
            if self.name == "Yandex S":
                keep_task = self.loop.create_task(self._keep_connection(ws, keep_state))


            while True:
                msg = await ws.receive()
                if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                    close_reason = str(msg.extra or "")
                    break
                if msg.type == WSMsgType.ERROR:
                    error = ws.exception() or msg.data
                    if isinstance(error, BaseException):
                        raise error
                    raise ConnectionError("WebSocket error without an exception")
                if msg.type not in (WSMsgType.TEXT, WSMsgType.BINARY):
                    continue

                data = json.loads(msg.data)
                last_message_at = time.monotonic()
                state = data.get("state") or {}
                player = state.get("playerState") or {}
                fails = 0  # any message - reset fails

                request_id = data.get("requestId")
                waiter = self.waiters.get(request_id)
                if waiter is not None and not waiter.done():
                    result = {"status": data["status"]}

                    if vinsResponse := data.get("vinsResponse"):
                        try:
                            # payload only in yandex module
                            if payload := vinsResponse.get("payload"):
                                response = payload["response"]
                            else:
                                response = vinsResponse["response"]

                            if card := response.get("card"):
                                result.update(card)
                            elif cards := response.get("cards"):
                                result.update(cards[0])
                            elif is_streaming := response.get("is_streaming"):
                                result["is_streaming"] = is_streaming
                            elif output_speech := response.get("output_speech"):
                                result.update(output_speech)

                        except Exception as e:
                            _LOGGER.debug(f"Response error: {e}")

                    waiter.set_result(result)

                self.update_handler(data)

            # TODO: find better place
            self.device_token = None

        except (ClientError, ConnectionResetError, TimeoutError) as e:
            error_type = type(e).__name__
            self.debug(f"Ошибка подключения: {repr(e)}")

        except (asyncio.CancelledError, RuntimeError) as e:
            # сюда попадаем при остановке HA
            if isinstance(e, RuntimeError):
                assert e.args[0] == "Session is closed", repr(e)

            self.debug(f"Останавливаем подключение: {repr(e)}")
            if self.ws and not self.ws.closed:
                await self.ws.close()
            return

        except Exception as e:
            error_type = type(e).__name__
            _LOGGER.error(f"{self.name} => local | {repr(e)}")

        finally:
            if keep_task is not None:
                keep_task.cancel()
                try:
                    await keep_task
                except asyncio.CancelledError:
                    pass
            if ws is not None:
                close_code = ws.close_code
                ws_error = ws.exception()
                if self.url:
                    reason = close_reason
                    if connection_token:
                        reason = reason.replace(connection_token, "[redacted]")
                    _LOGGER.info(
                        "%s | Local WS disconnected: code=%s reason=%r error=%s "
                        "lifetime=%.1fs last_message_age=%s track_id=%s position=%s duration=%s keepalive_sent=%s",
                        self.name,
                        close_code,
                        reason[:160],
                        error_type or (type(ws_error).__name__ if ws_error else None),
                        time.monotonic() - connected_at,
                        round(time.monotonic() - last_message_at, 1)
                        if last_message_at is not None else None,
                        player.get("id"),
                        player.get("progress"),
                        player.get("duration"),
                        keep_state["sent"],
                    )
                try:
                    if not ws.closed:
                        await asyncio.wait_for(ws.close(), timeout=5)
                except Exception as close_error:
                    self.debug(f"WebSocket cleanup: {type(close_error).__name__}")
                finally:
                    if self.ws is ws:
                        self.ws = None

        # возвращаемся в облачный режим
        self.update_handler(None)

        # останавливаем попытки
        if not self.url:
            return

        if fails:
            # 0s, 30s, 60s, ... 5 min
            delay = 30 * min(fails - 1, 10)
            self.debug(f"Таймаут до следующего подключения {delay}")
            await asyncio.sleep(delay)

        _ = asyncio.create_task(self._connect(fails))

    async def _keep_connection(self, ws, state):
        try:
            while self.url and self.ws is ws and not ws.closed:
                await asyncio.sleep(5)
                if not self.url or self.ws is not ws or ws.closed:
                    return
                await asyncio.wait_for(ws.send_json({
                    "conversationToken": self.device_token,
                    "id": str(uuid.uuid4()),
                    "payload": {"command": "ping"},
                    "sentTime": int(round(time.time() * 1000)),
                }), timeout=5)
                state["sent"] += 1
                if state["sent"] == 1 or state["sent"] % 12 == 0:
                    _LOGGER.info("%s | Local keepalive ping sent: count=%s", self.name, state["sent"])
        except asyncio.CancelledError:
            raise
        except Exception as error:
            _LOGGER.warning("%s | Local keepalive failed: %s", self.name, type(error).__name__)
            try:
                await asyncio.wait_for(ws.close(), timeout=5)
            except Exception:
                pass

    async def ping(self, command="ping"):
        # _LOGGER.debug("ping")
        try:
            await self.ws.send_json(
                {
                    "conversationToken": self.device_token,
                    "id": str(uuid.uuid4()),
                    "payload": {"command": command},
                    "sentTime": int(round(time.time() * 1000)),
                }
            )
        except:
            pass

    async def send(self, payload: dict) -> Optional[dict]:
        _LOGGER.debug(f"{self.name} => local | {payload}")

        request_id = str(uuid.uuid4())

        try:
            await self.ws.send_json(
                {
                    "conversationToken": self.device_token,
                    "id": request_id,
                    "payload": payload,
                    "sentTime": int(round(time.time() * 1000)),
                }
            )

            self.waiters[request_id] = self.loop.create_future()

            # limit future wait time
            await asyncio.wait_for(self.waiters[request_id], 5)


            return self.waiters.pop(request_id).result()

        except asyncio.TimeoutError as e:
            _ = self.waiters.pop(request_id, None)
            return {"error": repr(e)}

        except Exception as e:
            _LOGGER.error(f"{self.name} => local | {repr(e)}")
            return {"error": repr(e)}

    async def reset_session(self):
        payload = {
            "command": "serverAction",
            "serverActionEventPayload": {
                "type": "server_action",
                "name": "on_reset_session",
            },
        }
        await self.send(payload)

    prev_msg = None

    def debug_msg(self, data: dict):
        data.pop("id")
        data.pop("sentTime")
        data["state"].pop("timeSinceLastVoiceActivity")
        if player := data["state"].get("playerState"):
            player.pop("progress")

        if data == self.prev_msg:
            return

        for k in sorted(data.keys()):
            if self.prev_msg and k in self.prev_msg and data[k] == self.prev_msg[k]:
                continue
            self.debug(f"{k}: {data[k]}")

        if vins := data.get("vinsResponse"):
            with open(f"{time.time()}.json", "w") as f:
                json.dump(vins, f, ensure_ascii=False, indent=2)

        self.prev_msg = data


class YandexIOListener:
    add_handler = None
    browser = None

    def __init__(self, add_handler: Callable):
        self.add_handler = add_handler

    def start(self, zeroconf: Zeroconf):
        self.browser = ServiceBrowser(
            zeroconf, "_yandexio._tcp.local.", handlers=[self._zeroconf_handler]
        )

    def stop(self, *args):
        self.browser.cancel()
        self.browser.zc.close()

    def _zeroconf_handler(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ):
        try:
            info = zeroconf.get_service_info(service_type, name)
            if not info:
                return

            # If device has multiple local addresses - this is may be bug:
            # https://github.com/AlexxIT/YandexStation/issues/568
            if len(info.addresses) != 1:
                return

            properties = {
                k.decode(): v.decode() if isinstance(v, bytes) else v
                for k, v in info.properties.items()
            }

            self.add_handler(
                {
                    "device_id": properties["deviceId"],
                    "platform": properties["platform"],
                    "host": str(ipaddress.ip_address(info.addresses[0])),
                    "port": info.port,
                }
            )

        except Exception as e:
            _LOGGER.debug("Can't get zeroconf info", exc_info=e)


def debug(data: bytes):
    data: dict = json.loads(data)
    if experiments := data.get("experiments"):
        data["experiments"] = len(experiments)
    if extra := data.get("extra"):
        data["extra"] = {k: len(v) for k, v in extra.items()}
    if features := data.get("supported_features"):
        data["supported_features"] = len(features)
    _LOGGER.debug(json.dumps(data, ensure_ascii=False))
