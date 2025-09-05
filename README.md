# 🏠 Home Assistant OPC-UA Discovery Integration

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

<img src="https://github.com/guanaco0403/Home-Assistant-Opcua-Discovery/blob/main/repo_logo.png" width="600" />

## 🔌 Overview

**Home-Assistant-Opcua-Discovery** is a custom [Home Assistant](https://www.home-assistant.io) integration that enables automatic discovery of OPC UA variable nodes from an OPC UA server (e.g., Siemens, B&R, etc.) and exposes them as `sensor` or `switch` entities in Home Assistant.

This integration supports **local polling** using the `asyncua` library and is ideal for industrial or automation environments where OPC UA is the communication protocol standard.

---

## ✨ Features

- 📡 Connects to any OPC UA compatible server (e.g., Siemens, B&R, etc.)
- 🔍 Auto-discovers variables (nodes) under a defined root node
- 🧠 Smart handling of data types (e.g., booleans become switches)
- 🔄 Periodic polling with configurable scan interval
- 🧪 Graceful reconnection logic on connection loss
- 📥 Set opc-ua nodes values via Home Assistant services (`opcua.set_value`)
- 🤝 Supports multiple simultaneous OPC-UA clients

---

## Warning
- This integration is only compatible with nodes of those types (int, float, string, bool, byte), others will get ignored and won't appear in home assistant entities!
- The entity unique id is generated using the hub name and the opc-ua node name under that format (opcua_<hub_name>_<node_name>), if you change the node name on the opc-ua server, a new entity will be created in home assistant. **THIS ALSO MEANS THAT EVERY NODES NAMES MUST BE UNIQUE !!!**
- When a node gets removed from the opc-ua server, its associated entity will display "this entity is no longer being provided by the integration" once the hub/integration is reloaded, this is normal, you need to manually delete it from home assistant.
- When a node gets added on the opc-ua server, the entity will automatically get added to home assistant once the hub/integration is reloaded.
- More you have exposed opc-ua nodes, more it will take time to load the integration
---

## 📦 Installation

### Option 1: HACS (Recommended for Users)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=Home-Assistant-Opcua-Discovery&owner=guanaco0403&category=integration)

1. Go to **HACS > Integrations > Custom repositories**
2. Add this repo URL: https://github.com/guanaco0403/Home-Assistant-Opcua-Discovery
3. Select category: **Integration**
4. Click **Add**
5. Install the `Home Assistant OPC-UA Discovery` integration
6. Restart Home Assistant

### Option 2: Manual

1. Download the latest release `ha_opcua_discovery.zip`
2. Extract and copy the `ha_opcua_discovery` folder into: /config/custom_components/
3. Restart Home Assistant

---

## ⚙️ Configuration

### Setup via Home Assistant UI

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **OPC-UA Discovery**
3. Enter the required connection info:
- **Server URL** (e.g., `opc.tcp://192.168.0.10:4840`)
- **Username** (optional)
- **Password** (optional)
- **Root Node ID** (e.g., `ns=2;i=85`)
- **Scan Interval** in seconds

---

## 🛠 Service: `opcua.set_value`

You can manually set the value of a writable OPC UA node.

### Example:

```yaml
service: opcua_discovery.set_value
data:
   node_hub: "My OPC UA Server"
   node_id: "ns=2;s=Pump1/Enable"
   value: true
```

## 🧪 Requirements

- Home Assistant 2025.1 or newer
- Python 3.13+
- asyncua==1.0.2 (automatically installed)

## 🏷 Supported Platforms

- sensor –> for read-only variables
- switch –> for writable boolean variables

## 📁 File Structure

```
custom_components/
└── ha_opcua_discovery/
    ├── __init__.py
    ├── manifest.json
    ├── sensor.py
    ├── switch.py
    ├── config_flow.py
    └── ... (more coming)
```

## 📌 Integration Type & Quality

- Integration Type: hub
- Quality Scale: bronze
- IoT Class: local_polling

## 🧑‍💻 Code Owner

- @guanaco0403

## 🪪 License

This project is licensed under the MIT License.

## 📢 Contribute

Pull requests are welcome! If you want to improve auto-discovery, error handling, or add support for more OPC UA types — contributions are appreciated.
