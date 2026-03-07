# basicami

AsyncIO-based Asterisk Manager Interface (AMI) client for Python.

Companion to [basicagi](https://github.com/andrius/asterisk-basicagi).

## Install

```bash
pip install basicami
```

## Usage

```python
import asyncio
from basicami import BasicAMI

async def main():
    ami = await BasicAMI.connect("localhost", 5038, "admin", "secret")

    # Send any AMI action
    resp = await ami.send_action({"Action": "Ping"})
    print(resp)

    # Originate a call
    resp = await ami.originate(
        channel="Local/100@from-internal",
        application="Wait",
        data="30",
        caller_id="Test <15550099999>",
        timeout=30,
    )

    # Collect events
    events = await ami.get_events(timeout=2.0)
    for event in events:
        print(event)

    await ami.close()

asyncio.run(main())
```

## Marker Parsing

Includes a marker parser for Asterisk Verbose/Log markers used in PBX testing:

```python
from basicami import parse_marker, MarkerTrace

marker = parse_marker("SBC_ENTER: 001D tenant=001D-dev-testing")
print(marker.name)     # "SBC_ENTER"
print(marker.context)  # "001D"
print(marker.kv)       # {"tenant": "001D-dev-testing"}
```

## License

MIT
