from PyQt5.QtDBus import QDBusInterface, QDBusConnection, QDBusReply


class DBusWrapper():

    def __init__(self, service: str, path: str, interface: str = "") -> None:
        self._interface_name = interface
        self._interface = QDBusInterface(service, path, interface, QDBusConnection.sessionBus())
        self._properties = QDBusInterface(service, path, "org.freedesktop.DBus.Properties", QDBusConnection.sessionBus())

    def call(self, method_name, *args):
        # Check if the interface is valid
        if self._interface.isValid():
            # Call the method to get the list of connected devices
            # onlyReachable, onlyPaired
            msg = self._interface.call(method_name, *args)
            reply = QDBusReply(msg)
            # Check if the call was successful
            if reply.isValid():
                # Process the reply
                return reply.value()
            else:
                # Handle errors
                print("Method call failed:", reply.error().message())
        else:
            # Handle errors
            print("Invalid D-Bus interface")

    def property(self, property_name):
        # Check if the interface is valid
        if self._properties.isValid():
            # Call the method to get the list of connected devices
            # onlyReachable, onlyPaired
            msg = self._properties.call("Get", self._interface_name, property_name)
            reply = QDBusReply(msg)
            # Check if the call was successful
            if reply.isValid():
                # Process the reply
                return reply.value()
            else:
                # Handle errors
                print("Method call failed:", reply.error().message())
        else:
            # Handle errors
            print("Invalid D-Bus interface")

class KDEConnectDaemon():
    def __init__(self) -> None:
        self._dbus = DBusWrapper("org.kde.kdeconnect.daemon", "/modules/kdeconnect", "org.kde.kdeconnect.daemon")

    def announcedName(self) -> str:
        return self._dbus.call("announcedName")

    def devices(self, only_reachable: bool = False, only_paired: bool = False) -> list[str]:
        return self._dbus.call("devices", only_reachable, only_paired)

class KDEConnectPlugin():
    def __init__(self, device_id: str, plugin_name: str, plugin_interface: str) -> None:
        self._device_id = device_id
        self._plugin_name = plugin_name
        self._dbus = DBusWrapper("org.kde.kdeconnect.daemon", f"/modules/kdeconnect/devices/{self._device_id}/{self._plugin_name}", plugin_interface)

class KDEConnectPluginPing(KDEConnectPlugin):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "ping", "org.kde.kdeconnect.device.ping")

    def send_ping(self, custom_message = None):
        if custom_message is None:
            return self._dbus.call("sendPing")
        return self._dbus.call("sendPing", custom_message)


class KDEConnectPluginFindMyPhone(KDEConnectPlugin):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "findmyphone", "org.kde.kdeconnect.device.findmyphone")

    def ring(self):
        return self._dbus.call("ring")

class KDEConnectPluginBattery(KDEConnectPlugin):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "battery", "org.kde.kdeconnect.device.battery")

    @property
    def charge(self) -> int:
        return self._dbus.property("charge")
    
    @property
    def is_charging(self) -> bool:
        return self._dbus.property("isCharging")
    
class KDEConnectPluginConnectivityReport(KDEConnectPlugin):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "connectivity_report", "org.kde.kdeconnect.device.connectivity_report")

    @property
    def cellular_network_type(self) -> str:
        return self._dbus.property("cellularNetworkType")
    
    @property
    def cellular_network_strength(self) -> int:
        return self._dbus.property("cellularNetworkStrength")

class KDEConnectDevice():

    def __init__(self, device_id: str) -> None:
        self._device_id = device_id
        self._dbus = DBusWrapper("org.kde.kdeconnect.daemon", f"/modules/kdeconnect/devices/{self._device_id}", "org.kde.kdeconnect.device")
        self._plugins = {}
        self._load_plugins()
    def is_paired(self) -> bool:
        return self._dbus.call("isPaired")

    @property
    def name(self) -> str:
        return self._dbus.property("name")

    def loaded_plugins(self) -> list[str]:
        return self._dbus.call("loadedPlugins")
    
    def has_plugin(self, name: str) -> bool:
        return self._dbus.call("hasPlugin", name)
    
    def is_plugin_enabled(self, name: str) -> bool:
        return self._dbus.call("isPluginEnabled", name)
    
    def _load_plugins(self):
        plugin_map = {
            "kdeconnect_ping": KDEConnectPluginPing,
            "kdeconnect_battery": KDEConnectPluginBattery,
            "kdeconnect_connectivity_report": KDEConnectPluginConnectivityReport
        }
        
        for plugin, cls in plugin_map.items():
            if self.has_plugin(plugin) and self.is_plugin_enabled(plugin):
                print(f"adding Plugin {plugin}")
                self._plugins[plugin] = cls(self._device_id)

    def get_plugin_ping(self) -> KDEConnectPluginPing:
        return self._plugins.get("kdeconnect_ping", None)
    
    def get_plugin_battery(self) -> KDEConnectPluginBattery:
        return self._plugins.get("kdeconnect_battery", None)
    
    def get_plugin_connectivity_report(self) -> KDEConnectPluginConnectivityReport:
        return self._plugins.get("kdeconnect_connectivity_report", None)
