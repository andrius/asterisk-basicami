"""AsyncIO-based Asterisk Manager Interface (AMI) client.

Follows the patterns of basicagi but for AMI over TCP.
"""

import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


class AMIError(Exception):
    """AMI protocol error."""


class BasicAMI:
    """AsyncIO AMI client.

    Usage::

        ami = await BasicAMI.connect("localhost", 5038, "admin", "secret")
        resp = await ami.originate(
            channel="Local/100@from_sbc-173",
            application="Wait",
            data="30",
        )
        events = await ami.get_events(timeout=1.0)
        await ami.close()
    """

    def __init__(self):
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._event_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._pending: dict[str, asyncio.Future[dict[str, str]]] = {}
        self._read_task: asyncio.Task | None = None
        self._connected = False

    @classmethod
    async def connect(
        cls,
        host: str,
        port: int,
        username: str,
        secret: str,
        timeout: float = 15.0,
    ) -> "BasicAMI":
        """Connect to AMI, login, and start the background reader."""
        ami = cls()
        ami._reader, ami._writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )

        # Read AMI greeting line
        greeting = await asyncio.wait_for(ami._reader.readline(), timeout=timeout)
        logger.debug("AMI greeting: %s", greeting.decode().strip())

        # Start background reader before login so we can receive the response
        ami._read_task = asyncio.create_task(ami._read_loop())
        ami._connected = True

        # Login
        resp = await ami.send_action(
            {"Action": "Login", "Username": username, "Secret": secret}
        )
        if resp.get("Response") != "Success":
            await ami.close()
            raise AMIError(f"Login failed: {resp.get('Message', 'unknown')}")

        logger.info("AMI connected and logged in to %s:%d", host, port)
        return ami

    async def send_action(
        self, action: dict[str, str], timeout: float = 10.0
    ) -> dict[str, str]:
        """Send an AMI action and wait for the response."""
        action_id = action.get("ActionID", str(uuid.uuid4()))
        action["ActionID"] = action_id

        # Create a future for the response
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, str]] = loop.create_future()
        self._pending[action_id] = future

        # Serialize and send
        lines = [f"{k}: {v}" for k, v in action.items()]
        payload = "\r\n".join(lines) + "\r\n\r\n"
        self._writer.write(payload.encode())
        await self._writer.drain()

        logger.debug("Sent action: %s", action.get("Action"))

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(action_id, None)

    async def originate(
        self,
        channel: str,
        context: str | None = None,
        exten: str | None = None,
        priority: str | None = None,
        application: str | None = None,
        data: str | None = None,
        caller_id: str | None = None,
        timeout: int | None = None,
        variables: dict[str, str] | None = None,
        async_: bool = True,
    ) -> dict[str, str]:
        """Send an Originate action."""
        action: dict[str, str] = {
            "Action": "Originate",
            "Channel": channel,
        }
        if context:
            action["Context"] = context
        if exten:
            action["Exten"] = exten
        if priority:
            action["Priority"] = priority
        if application:
            action["Application"] = application
        if data:
            action["Data"] = data
        if caller_id:
            action["CallerID"] = caller_id
        if timeout:
            action["Timeout"] = str(timeout * 1000)  # seconds to ms
        if async_:
            action["Async"] = "true"
        if variables:
            action["Variable"] = ",".join(f"{k}={v}" for k, v in variables.items())

        return await self.send_action(action)

    async def get_events(
        self, timeout: float = 0.1, max_events: int = 1000
    ) -> list[dict[str, str]]:
        """Drain buffered events, waiting briefly for new ones."""
        events: list[dict[str, str]] = []

        # Drain already-queued events
        while not self._event_queue.empty() and len(events) < max_events:
            events.append(self._event_queue.get_nowait())

        # Wait briefly for more
        try:
            event = await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
            events.append(event)
            # Drain any more that arrived
            while not self._event_queue.empty() and len(events) < max_events:
                events.append(self._event_queue.get_nowait())
        except asyncio.TimeoutError:
            pass

        return events

    async def close(self):
        """Disconnect from AMI."""
        self._connected = False
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        logger.debug("AMI connection closed")

    async def _read_loop(self):
        """Background task: read AMI packets and dispatch."""
        buf = b""
        try:
            while self._connected:
                data = await self._reader.read(4096)
                if not data:
                    logger.warning("AMI connection closed by server")
                    break
                buf += data

                # Split on double CRLF (AMI packet delimiter)
                while b"\r\n\r\n" in buf:
                    packet, buf = buf.split(b"\r\n\r\n", 1)
                    self._dispatch_packet(packet.decode("utf-8", errors="replace"))

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("AMI read loop error: %s", e)
        finally:
            # Cancel any pending futures
            for action_id, future in self._pending.items():
                if not future.done():
                    future.set_exception(
                        AMIError("Connection closed while waiting for response")
                    )

    def _dispatch_packet(self, raw: str):
        """Parse an AMI packet and route to response future or event queue."""
        fields: dict[str, str] = {}
        for line in raw.split("\r\n"):
            if ":" in line:
                key, _, value = line.partition(":")
                fields[key.strip()] = value.strip()

        if not fields:
            return

        # Check if this is a response to a pending action
        action_id = fields.get("ActionID", "")
        if action_id in self._pending:
            future = self._pending[action_id]
            if not future.done():
                future.set_result(fields)
            return

        # Otherwise it's an event — queue it
        if "Event" in fields:
            try:
                self._event_queue.put_nowait(fields)
            except asyncio.QueueFull:
                logger.warning(
                    "Event queue full, dropping event: %s",
                    fields.get("Event"),
                )
