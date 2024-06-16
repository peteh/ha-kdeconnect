from ha_mqtt_discoverable import Settings
from ha_mqtt_discoverable.sensors import Button, ButtonInfo, DeviceInfo, BinarySensorInfo, BinarySensor, SensorInfo, Sensor, SwitchInfo, Switch, NumberInfo, Number
from paho.mqtt.client import Client, MQTTMessage

from konnect import KDEConnectDevice, KDEConnectDaemon
import logging
import time

class MqttDaemon():
    def __init__(self, mqtt_settings: Settings.MQTT) -> None:
        self._mqtt_settings = mqtt_settings
        self._daemon = KDEConnectDaemon()
        self._mqtt_devices = {}
        self.update_devices()
        self._daemon.notify_device_list_changed(self.update_devices)
    
    def update_devices(self):
        for device_id in self._daemon.devices(only_paired = True):
            if device_id not in self._mqtt_devices:
                device = KDEConnectDevice(self._daemon.self_id(), device_id)
                logging.debug(f"Device: {device.name} ({device.device_id})")
                mqtt_device = MqttDevice(self._mqtt_settings, self._daemon.announced_name(), device)
                self._mqtt_devices[device_id] = mqtt_device

class AbstractMqttPlugin():
    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        self._mqtt_settings = mqtt_settings
        self._device_info = device_info
        self._konnect_device = konnect_device

    def _generate_unique_id(self, entity_id: str) -> str:
        return f"kdeconnect_{self._konnect_device.host_device_id}_{self._konnect_device.device_id}_{entity_id}"

class MqttPluginFindDevice(AbstractMqttPlugin):

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_find_my_phone()
        self._create_entities()

    def _create_entities(self):
        find_button_info = ButtonInfo(name="Find Device", device=self._device_info, unique_id=self._generate_unique_id("btn-finddevice"))
        find_button_settings = Settings(mqtt=self._mqtt_settings, entity=find_button_info)
        find_button = Button(find_button_settings, self._ring_button_callback)
        find_button.write_config()
    
    def _ring_button_callback(self, client: Client, user_data, message: MQTTMessage):
        self._plugin.ring()

class MqttPluginLockDevice(AbstractMqttPlugin):

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_lock_device()
        self._create_entities()
        self._plugin.notify_locked_changed(self._update_lock)

    def _create_entities(self):
        lock_switch_info = SwitchInfo(name="Lock Device", device=self._device_info, unique_id=self._generate_unique_id("swt-lockdevice"))

        lock_switch_settings = Settings(mqtt=self._mqtt_settings, entity=lock_switch_info)
        # Instantiate the button
        self._lock_switch = Switch(lock_switch_settings, self._lock_switch_callback)

        # Publish the button's discoverability message to let HA automatically notice it
        self._lock_switch.write_config()
        self._update_lock(self._plugin.is_locked)
    
    def _update_lock(self, locked: bool):
        if locked:
            self._lock_switch.on()
        else:
            self._lock_switch.off()

    def _lock_switch_callback(self, client: Client, user_data, message: MQTTMessage):
        payload = message.payload.decode()
        if payload == "ON":
            self._plugin.set_locked(True)
            # Let HA know that the switch was successfully activated
            self._update_lock(True)
        elif payload == "OFF":
            self._plugin.set_locked(False)
            # Let HA know that the switch was successfully deactivated
            self._update_lock(False)


class MqttPluginBattery(AbstractMqttPlugin):
    """Plugin that shows Battery State and Charging State
    """

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_battery()
        self._create_entities()
        self._plugin.notify_refreshed(self._update_battery)

    def _create_entities(self):
        charging_sensor_info = BinarySensorInfo(name="Charging", device=self._device_info, unique_id=self._generate_unique_id("snsr-charging"), device_class="battery_charging")
        charging_sensor_settings = Settings(mqtt=self._mqtt_settings, entity=charging_sensor_info)
        self._charging_sensor = BinarySensor(charging_sensor_settings)
        self._charging_sensor.write_config()

        battery_sensor_info = SensorInfo(name="Battery", device=self._device_info, unique_id=self._generate_unique_id("snsr-battery"), device_class="battery", unit_of_measurement="%")
        battery_sensor_settings = Settings(mqtt=self._mqtt_settings, entity=battery_sensor_info)
        self._battery_sensor = Sensor(battery_sensor_settings)
        self._battery_sensor.write_config()

        # write initial state
        self._update_battery(self._plugin.is_charging, self._plugin.charge)

    def _update_battery(self, is_charging: bool, charge: int):
        if is_charging:
            self._charging_sensor.on()
        else:
            self._charging_sensor.off()
        self._battery_sensor.set_state(charge)

class MqttPluginConnectivity(AbstractMqttPlugin):
    """Plugin that shows Connectivity of the cellular network
    """

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_connectivity_report()
        self._create_entities()
        self._plugin.notify_refreshed(self._update_connectivity)

    def _create_entities(self):
        network_type_sensor_info = SensorInfo(name="Network Type", device=self._device_info, unique_id=self._generate_unique_id("snsr-networktype"), device_class="enum")
        network_type_sensor_settings = Settings(mqtt=self._mqtt_settings, entity=network_type_sensor_info)
        self._network_type_sensor = Sensor(network_type_sensor_settings)
        self._network_type_sensor.write_config()

        network_strength_sensor_info = SensorInfo(name="Network Signal Strength", device=self._device_info, unique_id=self._generate_unique_id("snsr-networkstrength"), device_class="signal_strength")
        network_strength_sensor_settings = Settings(mqtt=self._mqtt_settings, entity=network_strength_sensor_info)
        self._network_strength_sensor = Sensor(network_strength_sensor_settings)
        self._network_strength_sensor.write_config()

        # write initial state
        self._update_connectivity(self._plugin.cellular_network_type, self._plugin.cellular_network_strength)

    def _update_connectivity(self, network_type: str, network_strength: int):
        self._network_type_sensor.set_state(network_type)
        self._network_strength_sensor.set_state(network_strength)

class MqttPluginRemoteSystemVolume(AbstractMqttPlugin):
    """Plugin to view and control system volume. 
    """
    MAX_UINT16 = 0xFFFF

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._active_sink = ""
        self._plugin = self._konnect_device.get_plugin_remote_system_volume()
        self._create_entities()
        self._plugin.notify_muted_changed(self._update_muted)
        self._plugin.notify_volume_changed(self._update_volume)
        self._plugin.notify_sinks_changed(self._update_sinks)

    def _create_entities(self):
        mute_switch_info = SwitchInfo(name="Mute Device", device=self._device_info, unique_id=self._generate_unique_id("swt-mutedevice"))
        mute_switch_settings = Settings(mqtt=self._mqtt_settings, entity=mute_switch_info)
        self._mute_switch = Switch(mute_switch_settings, self._mute_switch_callback)
        self._mute_switch.write_config()

        volume_info = NumberInfo(name="Volume", device=self._device_info, unique_id=self._generate_unique_id("num-volume"), min=0, max=100, unit_of_measurement="%")
        volume_settings = Settings(mqtt=self._mqtt_settings, entity=volume_info)
        self._volume = Number(volume_settings, self._volume_callback)
        self._volume.write_config()

        self._update_active_sink()
    
    def _get_active_sink(self):
        for sink in self._plugin.sinks:
            sink_enabled = sink.get("enabled")
            if sink_enabled:
                return sink
        return None

    def _update_muted(self, sink: str, muted: bool):
        logging.debug(f"Active Sink: {self._active_sink}")
        logging.debug(f"Sink: {sink}, muted: {muted}")
        if sink.strip() != self._active_sink.strip():
            logging.debug(f"Received mute update for {sink}, but not active device")
            return
        if muted:
            self._mute_switch.on()
        else:
            self._mute_switch.off()
    
    def _update_volume(self, sink: str, volume: int):
        logging.debug(f"Active Sink: {self._active_sink}")
        logging.debug(f"Sink: {sink}, volume: {volume}")
        if sink != self._active_sink:
            logging.debug(f"Received mute update for {sink}, but not active device")
            return
        # cap to 0-100
        volume_percent = min(100, int(volume / self.MAX_UINT16 * 100))
        self._volume.set_value(volume_percent)
    
    def _update_sinks(self):
        self._update_active_sink()

    def _update_active_sink(self):
        sink = self._get_active_sink()
        if sink is None:
            logging.error("Could not find active sink")
            return
        sink_hw_id = sink.get("name")
        self._active_sink = sink_hw_id
        logging.debug(f"Setting active device: {self._active_sink}")
        muted = sink.get("muted")
        volume = sink.get("volume")
        self._update_muted(sink_hw_id, muted)
        self._update_volume(sink_hw_id, volume)
        


    def _mute_switch_callback(self, client: Client, user_data, message: MQTTMessage):
        payload = message.payload.decode()        
        if payload == "ON":
            self._plugin.send_muted(self._active_sink, True)
            self._update_muted(self._active_sink, True)
        elif payload == "OFF":
            self._plugin.send_muted(self._active_sink, False)
            self._update_muted(self._active_sink, False)
    
    def _volume_callback(self, client: Client, user_data, message: MQTTMessage):
        volume_percent = int(message.payload.decode())
        volume = int(volume_percent/100.*self.MAX_UINT16)
        self._plugin.send_volume(self._active_sink, volume)
        self._update_volume(self._active_sink, volume)


class MqttDevice:
    def __init__(self, mqtt_settings: Settings.MQTT, host_device_name: str, konnect_device: KDEConnectDevice) -> None:
        self._mqtt_settings = mqtt_settings
        self._konnect_device = konnect_device

        self._device_info = DeviceInfo(name=f"KDE Connect {self._konnect_device.name}", identifiers=f"kdeconnect_{self._konnect_device.host_device_id}_{self._konnect_device.device_id}", manufacturer="maker_pt", model=f"KDE Connect {host_device_name}")
        self._update_plugins()
        
    def _update_plugins(self):
        self._plugins = []
        find_my_phone = self._konnect_device.get_plugin_find_my_phone()
        if find_my_phone is not None:
            print("adding findmyphone")
            plugin = MqttPluginFindDevice(self._mqtt_settings, self._device_info, self._konnect_device)
            self._plugins.append(plugin)

        battery = self._konnect_device.get_plugin_battery()
        if battery is not None:
            print("adding battery")
            plugin = MqttPluginBattery(self._mqtt_settings, self._device_info, self._konnect_device)
            self._plugins.append(plugin)

        lock_device = self._konnect_device.get_plugin_lock_device()
        if lock_device is not None:
            print("adding lock device")
            plugin = MqttPluginLockDevice(self._mqtt_settings, self._device_info, self._konnect_device)
            self._plugins.append(plugin)
        
        connectivity = self._konnect_device.get_plugin_connectivity_report()
        if connectivity is not None:
            print("adding lock device")
            plugin = MqttPluginConnectivity(self._mqtt_settings, self._device_info, self._konnect_device)
            self._plugins.append(plugin)
        
        systemvolume = self._konnect_device.get_plugin_remote_system_volume()
        if systemvolume is not None:
            print("adding system volume")
            plugin = MqttPluginRemoteSystemVolume(self._mqtt_settings, self._device_info, self._konnect_device)
            self._plugins.append(plugin)
        
        