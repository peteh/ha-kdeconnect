import logging
from PyQt5.QtDBus import QDBusInterface, QDBusConnection, QDBusReply
from PyQt5.QtCore import QObject, pyqtSlot
from typing import Callable
import json

class DBusWrapper(QObject):

    def __init__(self, service: str, path: str, interface_name: str = "") -> None:
        self._service = service
        self._path = path
        self._interface_name = interface_name
        
        self._session = QDBusConnection.sessionBus()
        self._interface = QDBusInterface(self._service, self._path, self._interface_name, self._session)
        self._properties = QDBusInterface(self._service, self._path, "org.freedesktop.DBus.Properties", self._session)

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
   
    def handle_signal(self, signal_name: str, handler):
        # Connect the signal to the handler
        self._session.connect(self._service, self._path, self._interface_name, signal_name, handler)

class KDEConnectDaemon(QObject):
    def __init__(self) -> None:
        super().__init__()
        self._dbus = DBusWrapper("org.kde.kdeconnect.daemon", "/modules/kdeconnect", "org.kde.kdeconnect.daemon")
        self._device_list_changed_handlers = []
        self._dbus.handle_signal("deviceListChanged", self._device_list_changed)

    def announced_name(self) -> str:
        return self._dbus.call("announcedName")
    
    def self_id(self) -> str:
        return self._dbus.call("selfId")

    def devices(self, only_reachable: bool = False, only_paired: bool = False) -> list[str]:
        return self._dbus.call("devices", only_reachable, only_paired)
    
    @pyqtSlot()
    def _device_list_changed(self):
        for handler in self._device_list_changed_handlers:
            handler()

    def notify_device_list_changed(self, handler: Callable[[], None]):
        self._device_list_changed_handlers.append(handler)

class KDEConnectPlugin(QObject):
    def __init__(self, device_id: str, plugin_name: str, plugin_interface: str) -> None:
        super().__init__()
        self._device_id = device_id
        self._plugin_name = plugin_name
        self._dbus = DBusWrapper("org.kde.kdeconnect.daemon", f"/modules/kdeconnect/devices/{self._device_id}/{self._plugin_name}", plugin_interface)
        #self._dbus._session.registerObject('/', self)

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
    """Plugin that handles state of charge and charging flag. 
    """

    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "battery", "org.kde.kdeconnect.device.battery")
        self._refresh_handlers = []

        # signal that is called when soc or charging changes
        self._dbus.handle_signal("refreshed", self._refreshed)

    @property
    def charge(self) -> int:
        """State of charge of the device in %

        Returns:
            int: state of charge in 0 to 100%
        """
        return self._dbus.property("charge")
    
    @property
    def is_charging(self) -> bool:
        """if the device is currently charging

        Returns:
            bool: True if charging, False if not
        """
        return self._dbus.property("isCharging")

    @pyqtSlot(bool, int)
    def _refreshed(self, is_charging: bool, charge: int):
        for handler in self._refresh_handlers:
            handler(is_charging, charge)

    def notify_refreshed(self, handler: Callable[[bool, int], None]):
        """Add a handler that is called when state of charge or if the device is 
        charging changes. 

        Args:
            handler (Callable[[bool, int], None]): Handler to be called
        """
        self._refresh_handlers.append(handler)

class KDEConnectPluginLockDevice(KDEConnectPlugin):
    """Plugin that can lock or unlock a device. 
    """

    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "lockdevice", "org.kde.kdeconnect.device.lockdevice")
        self._refresh_handlers = []
        # signal that is called when soc or charging changes
        self._dbus.handle_signal("lockedChanged", self._locked_changed)

    def set_locked(self, locked: bool):
        self._dbus.call("setLocked", locked)

    @property
    def is_locked(self) -> bool:
        """If the device is locked

        Returns:
            bool: True if it's locked, False if not
        """
        return self._dbus.property("isLocked")

    @pyqtSlot(bool, int)
    def _locked_changed(self, is_locked: bool):
        for handler in self._refresh_handlers:
            handler(is_locked)

    def notify_locked_changed(self, handler: Callable[[bool], None]):
        """Register a handler that will be called if the lock state of the device changes

        Args:
            handler (Callable[[bool], None]): Called with True if the device has been locked, 
            or False if it's unlocked
        """
        self._refresh_handlers.append(handler)

class KDEConnectPluginConnectivityReport(KDEConnectPlugin):
    """Plugin that reports connectivity and type of the network the device is connected to. 
    """
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "connectivity_report", "org.kde.kdeconnect.device.connectivity_report")
        self._refresh_handlers = []
        self._dbus.handle_signal("refreshed", self._refreshed)

    @property
    def cellular_network_type(self) -> str:
        """The network type the device is connected to, e.g. LTE

        Returns:
            str: the network type
        """
        return self._dbus.property("cellularNetworkType")

    @property
    def cellular_network_strength(self) -> int:
        """The network strength of the network. 

        Returns:
            int: the network strength
        """
        return self._dbus.property("cellularNetworkStrength")

    @pyqtSlot(str, int)
    def _refreshed(self, network_type: str, network_strength: int):
        for handler in self._refresh_handlers:
            handler(network_type, network_strength)

    def notify_refreshed(self, handler: Callable[[str, int], None]):
        """The handler that is called with network type and strength when the values change. 

        Args:
            handler (Callable[[str, int], None]): Handler to be called
        """
        self._refresh_handlers.append(handler)

class KDEConnectPluginRemoteSystemVolume(KDEConnectPlugin, QObject):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "remotesystemvolume", "org.kde.kdeconnect.device.remotesystemvolume")
        
        self._sinks_changed_handlers = []
        self._dbus.handle_signal("sinksChanged", self._sinks_changed)
        
        self._volume_changed_handlers = []
        self._dbus.handle_signal("volumeChanged", self._volume_changed)
        
        self._muted_changed_handlers = []
        self._dbus.handle_signal("mutedChanged", self._muted_changed)

    @property
    def sinks(self) -> list[dict]:
        sinks_bytes = self._dbus.property("sinks")
        return json.loads(str(sinks_bytes, "utf-8"))

    @property
    def is_charging(self) -> bool:
        return self._dbus.property("isCharging")
    
    def send_muted(self, sink: str, muted: bool) -> None:
        self._dbus.call("sendMuted", sink, muted)
    
    def send_volume(self, sink: str, volume: int) -> None:
        self._dbus.call("sendVolume", sink, volume)

    @pyqtSlot()
    def _sinks_changed(self):
        for handler in self._sinks_changed_handlers:
            handler()
    
    def notify_sinks_changed(self, handler: Callable[[], None]):
        self._sinks_changed_handlers.append(handler)
    
    @pyqtSlot(str, int)
    def _volume_changed(self, sink: str, volume: int):
        for handler in self._volume_changed_handlers:
            handler(sink, volume)

    def notify_volume_changed(self, handler: Callable[[str, int], None]):
        self._volume_changed_handlers.append(handler)
    
    @pyqtSlot(str, bool)
    def _muted_changed(self, sink: str, muted: bool):
        for handler in self._muted_changed_handlers:
            handler(sink, muted)

    def notify_muted_changed(self, handler: Callable[[str, bool], None]):
        self._muted_changed_handlers.append(handler)

class KDEConnectPluginMPRISRemote(KDEConnectPlugin, QObject):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "mprisremote", "org.kde.kdeconnect.device.mprisremote")
        
        self._changed_handlers = []
        self._dbus.handle_signal("propertiesChanged", self._properties_changed)

    @property
    def album(self) -> str:
        return self._dbus.property("album")
    
    @property
    def artist(self) -> str:
        return self._dbus.property("artist")
    
    @property
    def can_seek(self) -> str:
        return self._dbus.property("canSeek")
    
    @property
    def is_playing(self) -> bool:
        return self._dbus.property("isPlaying")
    
    @property
    def player(self) -> int:
        return self._dbus.property("player")
    
    @property
    def player_list(self) -> list[str]:
        return self._dbus.property("playerList")
    
    def request_player_list(self):
        """Request the player list from the remote device. 
        """
        self._dbus.call("requestPlayerList")

    @pyqtSlot()
    def _properties_changed(self):
        logging.debug("Properties changed in MPRISRemote plugin")
        logging.debug(f"Playing: {self.is_playing}")
        logging.debug(f"Player: {self.player}")
        logging.debug(f"Album: {self.album}")
        logging.debug(f"Artist: {self.artist}") 
        logging.debug(f"Can seek: {self.can_seek}") 
        # player list
        logging.debug(f"Player list: {self.player_list}")
        
        for handler in self._changed_handlers:
            handler()

    def notify_properties_changed(self, handler: Callable[[], None]):
        self._changed_handlers.append(handler)

class KDEConnectDevice():

    def __init__(self, host_device_id: str, device_id: str) -> None:
        self._device_id = device_id
        self._host_device_id = host_device_id
        self._dbus = DBusWrapper("org.kde.kdeconnect.daemon", f"/modules/kdeconnect/devices/{self._device_id}", "org.kde.kdeconnect.device")
        self._plugins = {}
        self._load_plugins()
        
        # TODO: handle changed plugins

    def is_paired(self) -> bool:
        return self._dbus.call("isPaired")

    @property
    def host_device_id(self) -> str:
        return self._host_device_id
    
    @property
    def device_id(self) -> str:
        return self._device_id
    
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
            "kdeconnect_connectivity_report": KDEConnectPluginConnectivityReport,
            "kdeconnect_findmyphone": KDEConnectPluginFindMyPhone,
            "kdeconnect_mprisremote": KDEConnectPluginMPRISRemote,
            "kdeconnect_lockdevice": KDEConnectPluginLockDevice,
            "kdeconnect_remotesystemvolume": KDEConnectPluginRemoteSystemVolume
        }

        for plugin, cls in plugin_map.items():
            if self.has_plugin(plugin) and self.is_plugin_enabled(plugin) and plugin not in self._plugins:
                print(f"adding Plugin {plugin}")
                self._plugins[plugin] = cls(self._device_id)

    def get_plugin_ping(self) -> KDEConnectPluginPing:
        return self._plugins.get("kdeconnect_ping", None)

    def get_plugin_battery(self) -> KDEConnectPluginBattery:
        return self._plugins.get("kdeconnect_battery", None)

    def get_plugin_connectivity_report(self) -> KDEConnectPluginConnectivityReport:
        return self._plugins.get("kdeconnect_connectivity_report", None)
    
    def get_plugin_find_my_phone(self) -> KDEConnectPluginFindMyPhone:
        return self._plugins.get("kdeconnect_findmyphone", None)

    def get_plugin_mpris_remote(self) -> KDEConnectPluginMPRISRemote:
        return self._plugins.get("kdeconnect_mprisremote", None)
    
    def get_plugin_lock_device(self) -> KDEConnectPluginLockDevice:
        return self._plugins.get("kdeconnect_lockdevice", None)
    
    def get_plugin_remote_system_volume(self) -> KDEConnectPluginRemoteSystemVolume:
        return self._plugins.get("kdeconnect_remotesystemvolume", None)