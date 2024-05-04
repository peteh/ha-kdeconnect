from konnect import *

def main():
    if not QDBusConnection.sessionBus().isConnected():
        print("Failed to connect")
    
    daemon = KDEConnectDaemon()
    for device_id in daemon.devices(only_paired = True):
        device = KDEConnectDevice(device_id)
        ping = device.get_plugin_ping()
        if ping is not None and False:
            ping.send_ping()
        battery = device.get_plugin_battery()
        if battery is not None:
            print(f"Battery: {battery.charge}%")
            print(f"Charging: {battery.is_charging}")
        
        connectivity = device.get_plugin_connectivity_report()
        if connectivity is not None:
            print(f"Network Type: {connectivity.cellular_network_type}")
            print(f"Network Strength: {connectivity.cellular_network_strength}")
        print(device.name)

main()