"""
MCP Transport Layer — stdio and TCP transports for JSON-RPC 2.0 messages.

Transport interface:
    async send(message: MCPMessage) -> None
    async recv() -> MCPMessage
    async close() -> None

Implementations:
    StdioTransport:  Line-delimited JSON over stdin/stdout (subprocess MCP servers)
    TCPTransport:    Line-delimited JSON over TCP socket (network MCP servers)
    MemoryTransport: In-memory paired transport for testing

All transports use newline-delimited JSON (one JSON-RPC message per line).
No third-party dependencies — pure asyncio.
"""

from __future__ import annotations

import asyncio
import sys
from abc import ABC, abstractmethod
from typing import Optional

from .protocol import MCPMessage


# ═══════════════════════════════════════════════════════════════
#  Abstract Transport Interface
# ═══════════════════════════════════════════════════════════════


class Transport(ABC):
    """Abstract transport interface for MCP messages.

    All transports exchange :class:`MCPMessage` objects, handling
    serialization/deserialization internally.

    The protocol is line-delimited JSON: each message is a single
    JSON object terminated by a newline character.
    """

    @abstractmethod
    async def send(self, message: MCPMessage) -> None:
        """Send an MCP message."""
        ...

    @abstractmethod
    async def recv(self) -> MCPMessage:
        """Receive an MCP message. Blocks until a message is available."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the transport and release resources."""
        ...

    async def __aenter__(self) -> "Transport":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


# ═══════════════════════════════════════════════════════════════
#  Stdio Transport
# ═══════════════════════════════════════════════════════════════


class StdioTransport(Transport):
    """Standard input/output transport.

    Reads line-delimited JSON from stdin, writes to stdout.
    Typically used for subprocess-based MCP servers (e.g., ``mcp-server``
    spawned as a child process).

    For testing, inject ``reader`` and ``writer`` as asyncio streams.
    """

    def __init__(
        self,
        reader: Optional[asyncio.StreamReader] = None,
        writer: Optional[asyncio.StreamWriter] = None,
    ):
        self._reader = reader
        self._writer = writer
        self._closed = False

    async def _ensure_reader(self) -> asyncio.StreamReader:
        """Lazily create the reader from stdin if not injected."""
        if self._reader is None:
            loop = asyncio.get_event_loop()
            self._reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        return self._reader

    async def _ensure_writer(self) -> asyncio.StreamWriter:
        """Lazily create the writer to stdout if not injected."""
        if self._writer is None:
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, sys.stdout
            )
            self._writer = asyncio.StreamWriter(
                transport, protocol, None, loop
            )
        return self._writer

    async def send(self, message: MCPMessage) -> None:
        """Send a message as a line of JSON to stdout."""
        if self._closed:
            raise RuntimeError("Transport is closed")
        writer = await self._ensure_writer()
        data = message.to_json() + "\n"
        writer.write(data.encode("utf-8"))
        await writer.drain()

    async def recv(self) -> MCPMessage:
        """Receive a message by reading a line from stdin."""
        if self._closed:
            raise RuntimeError("Transport is closed")
        reader = await self._ensure_reader()
        line = await reader.readline()
        if not line:
            raise EOFError("stdin closed")
        return MCPMessage.from_json(line.decode("utf-8").strip())

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
#  TCP Transport
# ═══════════════════════════════════════════════════════════════


class TCPTransport(Transport):
    """TCP socket transport.

    Connects to a remote MCP server over TCP. Messages are exchanged
    as line-delimited JSON.

    Usage::

        transport = TCPTransport(host="localhost", port=8080)
        await transport.connect()
        client = MCPClient(transport)
        await client.connect()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 0,
        reader: Optional[asyncio.StreamReader] = None,
        writer: Optional[asyncio.StreamWriter] = None,
    ):
        self._host = host
        self._port = port
        self._reader = reader
        self._writer = writer
        self._closed = False

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def connect(self) -> None:
        """Establish the TCP connection if not already connected."""
        if self._reader is not None and self._writer is not None:
            return
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )

    async def send(self, message: MCPMessage) -> None:
        """Send a message as a line of JSON over TCP."""
        if self._closed:
            raise RuntimeError("Transport is closed")
        if self._writer is None:
            await self.connect()
        assert self._writer is not None
        data = message.to_json() + "\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()

    async def recv(self) -> MCPMessage:
        """Receive a message by reading a line from TCP."""
        if self._closed:
            raise RuntimeError("Transport is closed")
        if self._reader is None:
            await self.connect()
        assert self._reader is not None
        line = await self._reader.readline()
        if not line:
            raise EOFError("Connection closed")
        return MCPMessage.from_json(line.decode("utf-8").strip())

    async def close(self) -> None:
        """Close the TCP connection."""
        self._closed = True
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
#  Memory Transport (for testing)
# ═══════════════════════════════════════════════════════════════


class MemoryTransport(Transport):
    """In-memory transport for testing.

    Messages sent on one transport are received on its paired counterpart.
    Create a connected pair with :meth:`create_pair`.

    Usage::

        client_transport, server_transport = MemoryTransport.create_pair()
        # client_transport.send() → server_transport.recv()
        # server_transport.send() → client_transport.recv()
    """

    def __init__(
        self,
        incoming: "asyncio.Queue[MCPMessage]",
        outgoing: "asyncio.Queue[MCPMessage]",
    ):
        self._incoming = incoming
        self._outgoing = outgoing
        self._closed = False

    async def send(self, message: MCPMessage) -> None:
        """Send a message to the paired transport's incoming queue."""
        if self._closed:
            raise RuntimeError("Transport is closed")
        await self._outgoing.put(message)

    async def recv(self) -> MCPMessage:
        """Receive a message from this transport's incoming queue."""
        if self._closed:
            raise RuntimeError("Transport is closed")
        return await self._incoming.get()

    async def close(self) -> None:
        """Close the transport."""
        self._closed = True

    @staticmethod
    def create_pair() -> tuple["MemoryTransport", "MemoryTransport"]:
        """Create a pair of connected memory transports.

        Returns:
            (client_transport, server_transport) — messages sent on
            one are received on the other.
        """
        queue_a: "asyncio.Queue[MCPMessage]" = asyncio.Queue()
        queue_b: "asyncio.Queue[MCPMessage]" = asyncio.Queue()
        return MemoryTransport(queue_a, queue_b), MemoryTransport(queue_b, queue_a)
