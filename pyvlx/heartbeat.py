"""Module for sending get state requests to API in regular periods."""
import asyncio

from .api import GetState
from .api.status_request import StatusRequest
from .exception import PyVLXException
from .opening_device import Blind


class Heartbeat:
    """Class for sending heartbeats to API."""

    def __init__(self, pyvlx, timeout_in_seconds=60):
        """Initialize Heartbeat object."""
        self.pyvlx = pyvlx
        self.timeout_in_seconds = timeout_in_seconds
        self.loop_event = asyncio.Event()
        self.stopped = False
        self.run_task = None
        self.timeout_handle = None
        self.stopped_event = asyncio.Event()

    def __del__(self):
        """Cleanup heartbeat."""
        self.cancel_loop_timeout()

    def start(self):
        """Create loop task."""
        self.stopped = False
        self.stopped_event.clear()
        self.run_task = self.pyvlx.loop.create_task(self.loop())

    async def stop(self):
        """Stop heartbeat."""
        self.stopped = True
        self.loop_event.set()
        # Waiting for shutdown of loop()
        await self.stopped_event.wait()

    async def loop(self):
        """Pulse every timeout seconds until stopped."""
        while not self.stopped:
            self.timeout_handle = self.pyvlx.connection.loop.call_later(
                self.timeout_in_seconds, self.loop_timeout
            )
            await self.loop_event.wait()
            if not self.stopped:
                self.loop_event.clear()
                try:
                    await self.pulse()
                except PyVLXException:
                    pass
        self.cancel_loop_timeout()
        self.stopped_event.set()

    def loop_timeout(self):
        """Handle loop timeout."""
        self.loop_event.set()

    def cancel_loop_timeout(self):
        """Cancel loop timeout."""
        if self.timeout_handle is not None:
            self.timeout_handle.cancel()
            self.timeout_handle = None

    async def pulse(self):
        """Send get state request to API to keep the connection alive."""
        get_state = GetState(pyvlx=self.pyvlx)
        await get_state.do_api_call()
        if not get_state.success:
            raise PyVLXException("Unable to send get state.")

        # If nodes contain Blind device, refresh orientation because House Monitoring
        # delivers wrong values for FP3 parameter
        for node in self.pyvlx.nodes:
            if isinstance(node, Blind):
                status_request = StatusRequest(self.pyvlx, node.node_id)
                await status_request.do_api_call()
