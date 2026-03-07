"""Integration tests for BasicAMI — require a running Asterisk instance.

These tests are skipped by default. Run with:
    AMI_HOST=asterisk AMI_USER=admin AMI_SECRET=secret pytest tests/test_ami.py
"""

import asyncio
import os

import pytest

from basicami import BasicAMI

AMI_HOST = os.environ.get("AMI_HOST")
AMI_PORT = int(os.environ.get("AMI_PORT", "5038"))
AMI_USER = os.environ.get("AMI_USER", "node-agent")
AMI_SECRET = os.environ.get("AMI_SECRET", "ami-demo-secret")

needs_ami = pytest.mark.skipif(
    not AMI_HOST, reason="AMI_HOST not set — skipping AMI integration tests"
)


@needs_ami
@pytest.mark.asyncio
async def test_connect_and_close():
    ami = await BasicAMI.connect(AMI_HOST, AMI_PORT, AMI_USER, AMI_SECRET)
    assert ami._connected
    await ami.close()


@needs_ami
@pytest.mark.asyncio
async def test_send_action_ping():
    ami = await BasicAMI.connect(AMI_HOST, AMI_PORT, AMI_USER, AMI_SECRET)
    try:
        resp = await ami.send_action({"Action": "Ping"})
        assert resp.get("Response") == "Success"
        assert resp.get("Ping") == "Pong"
    finally:
        await ami.close()


@needs_ami
@pytest.mark.asyncio
async def test_originate_local():
    ami = await BasicAMI.connect(AMI_HOST, AMI_PORT, AMI_USER, AMI_SECRET)
    try:
        resp = await ami.originate(
            channel="Local/s@default",
            application="Wait",
            data="1",
            caller_id="Test <15550099999>",
            timeout=10,
            async_=True,
        )
        assert resp.get("Response") == "Success"
        # Wait a moment for events
        await asyncio.sleep(1)
        events = await ami.get_events(timeout=0.5)
        # We should get at least some events (Newchannel, etc.)
        assert isinstance(events, list)
    finally:
        await ami.close()
