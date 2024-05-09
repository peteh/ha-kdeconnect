import time
import logging
from konnect import KDEConnectDevice, KDEConnectDaemon
from mqttkonnect import MqttDevice, MqttDaemon
from ha_mqtt_discoverable import Settings
from PyQt5.QtWidgets import QApplication
import sys

logging.basicConfig(level=logging.DEBUG)


    

def main():
    #if not QDBusConnection.sessionBus().isConnected():
    #    print("Failed to connect")
    app = QApplication(sys.argv)
    # Configure the required parameters for the MQTT broker
    mqtt_settings = Settings.MQTT(host="homeassistant.home")
    mqtt_daemon = MqttDaemon(mqtt_settings)
    mqtt_daemon.update_devices()
    sys.exit(app.exec_())

main()