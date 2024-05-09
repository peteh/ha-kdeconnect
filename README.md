# KDE Connect for Homeassistant

This project aims to connect a KDE Connect instance with homeassistant.

The app talks to a kdeconnect daemon instance using dbus.

It's currently still work in progress.

It will share all connected devices as Devices in Homeassistant and will create entities matching the plugins.

## Supported Plugins

* Find my Device
* Remote System Volume (incl. Mute)
* Battery Report
* Network Report

## How to set up

This service must run on a PC with KDE Connect installed. It will expose all KDE Connect connected devices to Homeassistant with the configuration for this particular PC.

Example Setup:

* Homeassistant running as docker container on a Kubuntu Machine
* KDE Connect running on Kubuntu and connected to other devices in the network
