from ha_mqtt_discoverable import Settings
from ha_mqtt_discoverable.sensors import Button, ButtonInfo, DeviceInfo, BinarySensorInfo, BinarySensor, SensorInfo, Sensor, SwitchInfo, Switch
from paho.mqtt.client import Client, MQTTMessage

from konnect import KDEConnectDevice, KDEConnectPluginFindMyPhone
import logging

class AbstractMqttPlugin():
    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        self._mqtt_settings = mqtt_settings
        self._device_info = device_info
        self._konnect_device = konnect_device
    
    def _generate_unique_id(self, entity_id: str) -> str:
        return f"kdeconnect_{self._konnect_device.device_id}_{entity_id}"

class MqttPluginRingMyPhone(AbstractMqttPlugin):

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_find_my_phone()
        self._create_entities()

    def _create_entities(self):
        find_button_info = ButtonInfo(name="Find Device", device=self._device_info, unique_id=self._generate_unique_id("btn-finddevice"))

        find_button_settings = Settings(mqtt=self._mqtt_settings, entity=find_button_info)
        # Instantiate the button
        find_button = Button(find_button_settings, self._ring_button_callback)

        # Publish the button's discoverability message to let HA automatically notice it
        find_button.write_config()
    
    def _ring_button_callback(self, client: Client, user_data, message: MQTTMessage):
        self._plugin.ring()

class MqttPluginLockDevice(AbstractMqttPlugin):

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_lock_device()
        self._create_entities()
        self._plugin.notify_locked_changed(self.update_lock)

    def _create_entities(self):
        lock_switch_info = SwitchInfo(name="Lock Device", device=self._device_info, unique_id=self._generate_unique_id("swt-lockdevice"))

        lock_switch_settings = Settings(mqtt=self._mqtt_settings, entity=lock_switch_info)
        # Instantiate the button
        self._lock_switch = Switch(lock_switch_settings, self._lock_switch_callback)

        # Publish the button's discoverability message to let HA automatically notice it
        self._lock_switch.write_config()
        self.update_lock(self._plugin.is_locked)
    
    def update_lock(self, locked: bool):
        if locked:
            self._lock_switch.on()
        else:
            self._lock_switch.off()
    
    def _lock_switch_callback(self, client: Client, user_data, message: MQTTMessage):
        print(message.payload)
        payload = message.payload.decode()
        if payload == "ON":
            self._plugin.set_locked(True)
            # Let HA know that the switch was successfully activated
            self.update_lock(True)
        elif payload == "OFF":
            self._plugin.set_locked(False)
            # Let HA know that the switch was successfully deactivated
            self.update_lock(False)


class MqttPluginBattery(AbstractMqttPlugin):

    def __init__(self, mqtt_settings: Settings.MQTT, device_info: DeviceInfo, konnect_device: KDEConnectDevice) -> None:
        super().__init__(mqtt_settings, device_info, konnect_device)
        self._plugin = self._konnect_device.get_plugin_battery()
        self._create_entities()
        self._plugin.notify_refreshed(self.update_battery)

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
        self.update_battery(self._plugin.is_charging, self._plugin.charge)
    
    def update_battery(self, is_charging: bool, charge: int):
        logging.debug("Updating mqtt battery state")
        if is_charging:
            self._charging_sensor.on()
        else:
            self._charging_sensor.off()
        
        self._battery_sensor.set_state(charge)

class MqttDevice:
    def __init__(self, mqtt_settings: Settings.MQTT, konnect_device: KDEConnectDevice) -> None:
        self._mqtt_settings = mqtt_settings
        self._konnect_device = konnect_device

        self._device_info = DeviceInfo(name=f"KDE Connect {self._konnect_device.name}", identifiers=f"kdeconnect_{self._konnect_device.device_id}")

        self._plugins = []
        find_my_phone = self._konnect_device.get_plugin_find_my_phone()
        if find_my_phone is not None:
            print("adding findmyphone")
            plugin = MqttPluginRingMyPhone(self._mqtt_settings, self._device_info, self._konnect_device)
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