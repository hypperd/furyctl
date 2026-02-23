# pyright: reportUnknownMemberType=false, reportAttributeAccessIssue=false
from typing import Callable, final

from dbus_fast.aio import MessageBus, ProxyInterface

DBUS_LOGIND_PATH = "/org/freedesktop/login1"
DBUS_LOGIND_NAME = "org.freedesktop.login1"
DBUS_LOGIND_MANAGER_INTERFACE = "org.freedesktop.login1.Manager"


@final
class LogindService:
    def __init__(self, interface: ProxyInterface, bus: MessageBus) -> None:
        self._bus = bus
        self._interface = interface

    @classmethod
    async def connect(cls, bus: MessageBus):
        instropection = await bus.introspect(DBUS_LOGIND_NAME, DBUS_LOGIND_PATH)
        proxy = bus.get_proxy_object(DBUS_LOGIND_NAME, DBUS_LOGIND_PATH, instropection)
        interface = proxy.get_interface(DBUS_LOGIND_MANAGER_INTERFACE)
        return cls(interface, bus)

    def on_prepare_for_sleep(self, callback: Callable[[bool], None]) -> None:
        self._interface.on_prepare_for_sleep(callback)
