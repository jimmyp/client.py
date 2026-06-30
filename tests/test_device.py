from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import orjson
import pytest
from testfixtures import LogCapture

from deebot_client.command import Command, DeviceCommandResult
from deebot_client.commands.json.battery import GetBattery
from deebot_client.commands.json.map import GetMapSetV2
from deebot_client.commands.xml import GetBatteryInfo
from deebot_client.const import DataType
from deebot_client.device import (
    _STATE_REFRESH_INTERVAL_ACTIVE,
    _STATE_REFRESH_INTERVAL_IDLE,
    Device,
)
from deebot_client.events import AvailabilityEvent, StateEvent
from deebot_client.events.map import MapSetType, Position, PositionsEvent
from deebot_client.events.network import NetworkInfoEvent
from deebot_client.hardware import get_static_device_info
from deebot_client.messages.json import OnBattery
from deebot_client.messages.xml import BatteryInfo
from deebot_client.models import DeviceInfo, State, StaticDeviceInfo
from deebot_client.mqtt_client import MqttClient, SubscriberInfo
from deebot_client.rs.map import PositionType
from tests.helpers import mock_static_device_info
from tests.helpers.tasks import block_till_done

if TYPE_CHECKING:
    from deebot_client.authentication import Authenticator
    from deebot_client.event_bus import EventBus
    from deebot_client.message import Message
    from deebot_client.models import ApiDeviceInfo


def json_battery_message_payload(expected_version: str | None = "1.8.2") -> str:
    header = {
        "pri": 1,
        "tzm": 480,
        "ts": "1304637391896",
        "ver": "0.0.1",
        "hwVer": "0.1.1",
    }
    if expected_version:
        header.update({"fwVer": expected_version})
    data = {
        "header": header,
        "body": {"data": {"value": 100, "isLow": 0}},
    }
    return orjson.dumps(data).decode("utf-8")


def xml_battery_message_payload() -> str:
    return '<ctl ret="ok"><battery power="100" /></ctl>'


@pytest.mark.parametrize(
    ("data_type", "get_battery_command", "battery_message", "battery_message_payload"),
    [
        (DataType.JSON, GetBattery, OnBattery, json_battery_message_payload()),
        (DataType.XML, GetBatteryInfo, BatteryInfo, xml_battery_message_payload()),
    ],
    ids=["json_bot", "xml_bot"],
)
@patch("deebot_client.device._AVAILABLE_CHECK_INTERVAL", 2)  # reduce interval
async def test_available_check_and_teardown(
    data_type: DataType,
    get_battery_command: Command,
    battery_message: Message,
    battery_message_payload: str,
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """Test the available check including if the status Event is fired correctly."""
    received_statuses: asyncio.Queue[AvailabilityEvent] = asyncio.Queue()

    async def on_status(event: AvailabilityEvent) -> None:
        received_statuses.put_nowait(event)

    async def assert_received_status(*, expected: bool) -> None:
        await asyncio.sleep(0)
        assert received_statuses.get_nowait().available is expected

    # prepare mocks
    battery_mock = Mock(spec_set=get_battery_command)

    device_info = DeviceInfo(
        api_device_info,
        mock_static_device_info({AvailabilityEvent: [battery_mock]}, data_type),
    )
    execute_mock = battery_mock.execute

    # prepare bot and mock mqtt
    bot = Device(device_info, authenticator)
    mqtt_client = Mock(spec=MqttClient)
    unsubscribe_mock = Mock(spec=Callable[[], None])
    mqtt_client.subscribe.return_value = unsubscribe_mock
    await bot.initialize(mqtt_client)

    bot.events.subscribe(AvailabilityEvent, on_status)
    await asyncio.sleep(0)  # let refresh task of event bus be processed
    execute_mock.assert_awaited_once()
    execute_mock.reset_mock()
    await assert_received_status(expected=True)

    # verify mqtt was subscribed and available task was started
    mqtt_client.subscribe.assert_called_once()
    sub_info: SubscriberInfo = mqtt_client.subscribe.call_args.args[0]
    assert bot._available_task is not None
    assert not bot._available_task.done()
    # As task was started now, no check should be performed
    execute_mock.assert_not_called()

    # Simulate bot not reached by returning False
    execute_mock.return_value = DeviceCommandResult(device_reached=False)

    # Wait longer than the interval to be sure task will be executed
    await asyncio.sleep(2.1)
    # Verify command call for available check
    execute_mock.assert_awaited_once()
    await assert_received_status(expected=False)

    # Simulate bot reached by returning True
    execute_mock.return_value = DeviceCommandResult(device_reached=True)

    await asyncio.sleep(2)
    execute_mock.await_count = 2
    await assert_received_status(expected=True)

    # reset mock for easier handling
    battery_mock.reset_mock()

    # Simulate message over mqtt and therefore available is not needed
    await asyncio.sleep(0.8)

    sub_info.callback(battery_message.NAME, battery_message_payload)
    await asyncio.sleep(1)

    # As the last message is not more than (interval-1) old, we skip the available check
    execute_mock.assert_not_called()
    assert received_statuses.empty()

    # teardown bot and verify that bot was unsubscribed from mqtt and available task was canceled.
    await bot.teardown()
    await asyncio.sleep(0)

    unsubscribe_mock.assert_called()
    assert bot._available_task.done()
    await bot.teardown()


async def test_mac_address(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """Test that the mac address is change on NetworkInfoEvent."""
    device_info = DeviceInfo(
        api_device_info,
        mock_static_device_info({AvailabilityEvent: []}, DataType.JSON),
    )
    device = Device(device_info, authenticator)

    assert device.mac is None

    mac = "AA:BB:CC:DD:EE:FF"

    device.events.notify(
        NetworkInfoEvent(ip="192.168.1.100", ssid="WLAN", rssi=-61, mac=mac)
    )

    await block_till_done(device.events._tasks)

    assert device.mac == mac
    await device.teardown()


def static_device_info_no_map() -> StaticDeviceInfo:
    """Return a StaticDeviceInfo without map capability."""
    info = asyncio.run(get_static_device_info("2ap5uq"))
    assert info is not None
    assert info.capabilities.map is None
    return info


@pytest.mark.parametrize(
    "static_device_info",
    [
        static_device_info_no_map(),
    ],
)
async def test_behaviour_with_no_map_capability(
    authenticator: Authenticator, device_info: DeviceInfo
) -> None:
    device = Device(device_info, authenticator)

    assert device.map is None

    await device.teardown()


@pytest.mark.parametrize(
    (
        "data_type",
        "get_battery_command",
        "battery_message",
        "battery_message_payload",
        "expected_version",
    ),
    [
        (
            DataType.JSON,
            GetBattery,
            OnBattery,
            json_battery_message_payload("1.8.2"),
            "1.8.2",
        ),
        (
            DataType.JSON,
            GetBattery,
            OnBattery,
            json_battery_message_payload(None),
            None,
        ),
        (DataType.JSON, GetBattery, OnBattery, "{corrupted}", None),
        (DataType.JSON, GetBattery, OnBattery, '["not an object"]', None),
        (
            DataType.XML,
            GetBatteryInfo,
            BatteryInfo,
            xml_battery_message_payload(),
            None,
        ),
    ],
    ids=[
        "json_bot",
        "json_bot_no_version",
        "json_bot_corrupted_json",
        "json_bot_not_a_dict_json",
        "xml_bot",
    ],
)
@patch("deebot_client.device._AVAILABLE_CHECK_INTERVAL", 2)  # reduce interval
async def test_device_handle_message_behaviour(
    data_type: DataType,
    get_battery_command: Command,
    battery_message: Message,
    battery_message_payload: str,
    expected_version: str | None,
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """Test the available check including if the status Event is fired correctly."""
    received_statuses: asyncio.Queue[AvailabilityEvent] = asyncio.Queue()

    async def on_status(event: AvailabilityEvent) -> None:
        received_statuses.put_nowait(event)

    # prepare mocks
    battery_mock = Mock(spec_set=get_battery_command)

    device_info = DeviceInfo(
        api_device_info,
        mock_static_device_info({AvailabilityEvent: [battery_mock]}, data_type),
    )

    # prepare bot and mock mqtt
    bot = Device(device_info, authenticator)
    mqtt_client = Mock(spec=MqttClient)
    unsubscribe_mock = Mock(spec=Callable[[], None])
    mqtt_client.subscribe.return_value = unsubscribe_mock
    await bot.initialize(mqtt_client)

    bot.events.subscribe(AvailabilityEvent, on_status)

    # verify mqtt was subscribed and available task was started
    mqtt_client.subscribe.assert_called_once()
    sub_info: SubscriberInfo = mqtt_client.subscribe.call_args.args[0]
    sub_info.callback(battery_message.NAME, battery_message_payload)
    await asyncio.sleep(1)

    assert bot.fw_version == expected_version

    # teardown bot
    await bot.teardown()


@pytest.mark.parametrize(
    ("pos_event", "expected_call"),
    [
        (PositionsEvent([]), False),
        (PositionsEvent([Position(PositionType.CHARGER, 0, 0, 0)]), False),
        (PositionsEvent([Position(PositionType.DEEBOT, 0, 0, 0)]), False),
        (
            PositionsEvent(
                [
                    Position(PositionType.DEEBOT, 0, 0, 0),
                    Position(PositionType.CHARGER, 0, 0, 0),
                ]
            ),
            True,
        ),
        (
            PositionsEvent(
                [
                    Position(PositionType.CHARGER, 0, 0, 0),
                    Position(PositionType.DEEBOT, 0, 0, 0),
                ]
            ),
            True,
        ),
        (
            PositionsEvent(
                [
                    Position(PositionType.CHARGER, 1, 0, 0),
                    Position(PositionType.DEEBOT, 0, 0, 0),
                ]
            ),
            False,
        ),
        (
            PositionsEvent(
                [
                    Position(PositionType.DEEBOT, 0, 0, 0),
                    Position(PositionType.CHARGER, 1, 0, 0),
                ]
            ),
            False,
        ),
        (
            PositionsEvent(
                [
                    Position(PositionType.DEEBOT, 0, 0, 0),
                    Position(PositionType.CHARGER, 1, 0, 0),
                    Position(PositionType.CHARGER, 0, 0, 0),
                ]
            ),
            True,
        ),
    ],
)
async def test_onPos_device_handling(
    authenticator: Authenticator,
    device_info: DeviceInfo,
    event_bus_mock: Mock,
    event_bus: EventBus,
    pos_event: PositionsEvent,
    expected_call: bool,
) -> None:
    """Test the available check including if the status Event is fired correctly."""
    with patch("deebot_client.device.EventBus", return_value=event_bus_mock):
        bot = Device(device_info, authenticator)
        mqtt_client = Mock(spec=MqttClient)
        unsubscribe_mock = Mock(spec=Callable[[], None])
        mqtt_client.subscribe.return_value = unsubscribe_mock
        await bot.initialize(mqtt_client)

    bot.events.notify(pos_event)
    await block_till_done(event_bus._tasks)

    if expected_call:
        event_bus_mock.request_refresh.assert_called_once_with(StateEvent)
    else:
        event_bus_mock.request_refresh.assert_not_called()

    # teardown bot
    await bot.teardown()


@pytest.mark.parametrize("device_class", ["kr0277"])
@pytest.mark.parametrize(
    "set_type",
    [
        MapSetType.ROOMS,
        MapSetType.NO_MOP_ZONES,
        MapSetType.VIRTUAL_WALLS,
    ],
)
async def test_message_requested_commands(
    authenticator: Authenticator,
    device_info: DeviceInfo,
    event_bus_mock: Mock,
    set_type: MapSetType,
) -> None:
    """Test that commands requested by messages are executed."""
    execute_command_mock = AsyncMock()

    with (
        patch("deebot_client.device.EventBus", return_value=event_bus_mock),
        patch.object(Device, "_execute_command", execute_command_mock),
    ):
        bot = Device(device_info, authenticator)
        mqtt_client = Mock(spec=MqttClient)
        unsubscribe_mock = Mock(spec=Callable[[], None])
        mqtt_client.subscribe.return_value = unsubscribe_mock
        await bot.initialize(mqtt_client)
        mqtt_client.subscribe.assert_called_once()
        sub_info: SubscriberInfo = mqtt_client.subscribe.call_args.args[0]

        message_data = {
            "header": {
                "pri": 1,
                "tzm": 480,
                "ts": "1304637391896",
                "ver": "0.0.1",
                "fwVer": "1.8.2",
                "hwVer": "0.1.1",
            },
            "body": {"data": {"mid": "199390082", "type": set_type.value}},
        }
        message_payload = orjson.dumps(message_data).decode("utf-8")
        with LogCapture() as log:
            sub_info.callback("onMapSet_V2", message_payload)
            await asyncio.sleep(0)  # let tasks be processed

        log.check_present(
            (
                "deebot_client.device",
                "DEBUG",
                (
                    "Message onMapSet_V2 requested commands: "
                    f"[<GetMapSetV2 args={{'mid': '199390082', 'type': '{set_type.value}'}}>]"
                ),
            )
        )
        execute_command_mock.assert_called_once_with(GetMapSetV2("199390082", set_type))

    # teardown bot
    await bot.teardown()


def _state_refresh_device(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
    state_mock: Command,
    *,
    state_refresh: bool,
) -> Device:
    """Build a device whose StateEvent refresh command is ``state_mock``."""
    device_info = DeviceInfo(
        api_device_info,
        mock_static_device_info({StateEvent: [state_mock]}),
    )
    return Device(device_info, authenticator, state_refresh=state_refresh)


@pytest.mark.parametrize(
    ("state", "expected_interval"),
    [
        (State.CLEANING, _STATE_REFRESH_INTERVAL_ACTIVE),
        (State.RETURNING, _STATE_REFRESH_INTERVAL_ACTIVE),
        (State.PAUSED, _STATE_REFRESH_INTERVAL_ACTIVE),
        (State.IDLE, _STATE_REFRESH_INTERVAL_IDLE),
        (State.DOCKED, _STATE_REFRESH_INTERVAL_IDLE),
        (State.ERROR, _STATE_REFRESH_INTERVAL_IDLE),
        (None, _STATE_REFRESH_INTERVAL_IDLE),
    ],
    ids=[
        "cleaning",
        "returning",
        "paused",
        "idle",
        "docked",
        "error",
        "unknown",
    ],
)
async def test_state_refresh_interval_selection(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
    state: State | None,
    expected_interval: float,
) -> None:
    """The refresh interval is fast while active and slow otherwise (pure, no timing)."""
    bot = _state_refresh_device(
        authenticator, api_device_info, Mock(spec_set=Command), state_refresh=True
    )
    if state is not None:
        bot.events.notify(StateEvent(state))
        await asyncio.sleep(0)

    assert bot._state_refresh_interval() == expected_interval

    await bot.teardown()


@patch("deebot_client.device._STATE_REFRESH_INTERVAL_ACTIVE", 0.1)
@patch("deebot_client.device._STATE_REFRESH_INTERVAL_IDLE", 0.5)
async def test_state_refresh_polls_faster_while_active(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """While CLEANING the state command is polled at the (short) active interval."""
    state_mock = Mock(spec_set=Command)
    state_mock.execute = AsyncMock(
        return_value=DeviceCommandResult(device_reached=True)
    )
    bot = _state_refresh_device(
        authenticator, api_device_info, state_mock, state_refresh=True
    )
    mqtt_client = Mock(spec=MqttClient)
    mqtt_client.subscribe.return_value = Mock(spec=Callable[[], None])
    await bot.initialize(mqtt_client)

    # the state-refresh task should have been started by initialize
    assert bot._state_refresh_task is not None
    assert not bot._state_refresh_task.done()

    bot.events.notify(StateEvent(State.CLEANING))
    await asyncio.sleep(0)
    state_mock.execute.reset_mock()

    # within ~3 active intervals we expect multiple polls
    await asyncio.sleep(0.35)
    active_polls = state_mock.execute.await_count
    assert active_polls >= 2, f"expected >=2 active polls, got {active_polls}"

    # dock the bot -> next poll should fall back to the slow interval
    bot.events.notify(StateEvent(State.DOCKED))
    await asyncio.sleep(0)
    state_mock.execute.reset_mock()

    # over the same window, far fewer (slow-interval) polls
    await asyncio.sleep(0.35)
    idle_polls = state_mock.execute.await_count
    assert idle_polls < active_polls, (
        f"expected fewer idle polls than active ({idle_polls} !< {active_polls})"
    )

    await bot.teardown()


@patch("deebot_client.device._STATE_REFRESH_INTERVAL_ACTIVE", 0.1)
@patch("deebot_client.device._STATE_REFRESH_INTERVAL_IDLE", 0.5)
async def test_state_refresh_uses_generic_refresh_command(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """The loop executes whatever get_refresh_commands(StateEvent) returns."""
    state_mock = Mock(spec_set=Command)
    state_mock.execute = AsyncMock(
        return_value=DeviceCommandResult(device_reached=True)
    )
    bot = _state_refresh_device(
        authenticator, api_device_info, state_mock, state_refresh=True
    )
    mqtt_client = Mock(spec=MqttClient)
    mqtt_client.subscribe.return_value = Mock(spec=Callable[[], None])
    await bot.initialize(mqtt_client)

    bot.events.notify(StateEvent(State.CLEANING))
    await asyncio.sleep(0.25)

    # the exact mock from get_refresh_commands(StateEvent) was executed
    state_mock.execute.assert_awaited()
    await bot.teardown()


@patch("deebot_client.device._STATE_REFRESH_INTERVAL_ACTIVE", 0.1)
async def test_state_refresh_disabled_by_default(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """Without the opt-in, no state-refresh loop runs (legacy behaviour unchanged)."""
    state_mock = Mock(spec_set=Command)
    state_mock.execute = AsyncMock(
        return_value=DeviceCommandResult(device_reached=True)
    )
    bot = _state_refresh_device(
        authenticator, api_device_info, state_mock, state_refresh=False
    )
    mqtt_client = Mock(spec=MqttClient)
    mqtt_client.subscribe.return_value = Mock(spec=Callable[[], None])
    await bot.initialize(mqtt_client)

    # The opt-in is off, so no state-refresh loop is started.
    assert bot._state_refresh_task is None

    # Any execute calls so far come from the event bus' own one-shot refresh,
    # not from a polling loop. Let the active interval elapse several times and
    # confirm there is no repeated (loop-driven) polling.
    bot.events.notify(StateEvent(State.CLEANING))
    await asyncio.sleep(0)
    state_mock.execute.reset_mock()

    await asyncio.sleep(0.35)
    state_mock.execute.assert_not_called()
    await bot.teardown()


@patch("deebot_client.device._STATE_REFRESH_INTERVAL_ACTIVE", 0.1)
@patch("deebot_client.device._STATE_REFRESH_INTERVAL_IDLE", 0.5)
async def test_state_refresh_backs_off_when_unavailable(
    authenticator: Authenticator,
    api_device_info: ApiDeviceInfo,
) -> None:
    """When the device is unreachable, the loop backs off to the slow interval."""
    state_mock = Mock(spec_set=Command)
    state_mock.execute = AsyncMock(
        return_value=DeviceCommandResult(device_reached=False)
    )
    bot = _state_refresh_device(
        authenticator, api_device_info, state_mock, state_refresh=True
    )
    mqtt_client = Mock(spec=MqttClient)
    mqtt_client.subscribe.return_value = Mock(spec=Callable[[], None])
    await bot.initialize(mqtt_client)

    # even though state is "active", an unreachable device must back off
    bot.events.notify(StateEvent(State.CLEANING))
    await asyncio.sleep(0)
    state_mock.execute.reset_mock()

    await asyncio.sleep(0.35)
    polls = state_mock.execute.await_count
    # backed off to the slow interval: not hammering at the active rate
    assert polls <= 1, f"expected back-off (<=1 poll), got {polls}"

    await bot.teardown()
