import time
import logging
from konnect import *
from mqttkonnect import *
from ha_mqtt_discoverable import Settings
from PyQt5.QtWidgets import QApplication
import sys

logging.basicConfig(level=logging.DEBUG)

def main():
    if not QDBusConnection.sessionBus().isConnected():
        print("Failed to connect")
    app = QApplication(sys.argv)
    # Configure the required parameters for the MQTT broker
    mqtt_settings = Settings.MQTT(host="homeassistant.home")
    
    mqtt_devices = []
    daemon = KDEConnectDaemon()
    for device_id in daemon.devices(only_paired = True):
        device = KDEConnectDevice(device_id)
        logging.debug(f"Device: {device.name} ({device.device_id})")
        mqtt_device = MqttDevice(mqtt_settings, device)
        mqtt_devices.append(mqtt_device)
        ping = device.get_plugin_ping()
        if ping is not None and False:
            ping.send_ping()
        battery = device.get_plugin_battery()
        if battery is not None:
            logging.debug(f"Battery: {battery.charge}%")
            logging.debug(f"Charging: {battery.is_charging}")
            #battery.notify_refresh(None)
        
        connectivity = device.get_plugin_connectivity_report()
        if connectivity is not None:
            logging.debug(f"Network Type: {connectivity.cellular_network_type}")
            logging.debug(f"Network Strength: {connectivity.cellular_network_strength}")
        
        mpris = device.get_plugin_mpris_remote()
        if mpris is not None:
            #mpris.notify_properties_changed(None)
            pass
        
    
    sys.exit(app.exec_())

main()