# UCLA IR Lab (Infrared Laboratory) Device Controlling Software

An asynchronous Python controller for monitoring and logging data from various devices (Lakeshore, APC UPS, Eaton PDU, OneWire Sensors, Inficon VGC) used in the UCLA IR Lab.

## 🚀 Features

* **Asynchronous Polling:** Uses `asyncio` for efficient, parallel data collection from all devices.
* **Multi-Device Support:**
    * **Lakeshore 224** (Temperature Monitor via TCP/IP)
    * **OneWire** (Temperature/Humidity/Pressure Sensors via HTTP)
    * **APC UPS** (Battery Status, Load, Runtime via SNMP)
    * **Eaton PDU** (Input Voltage/Power and Individual Outlet Monitoring via SNMP)
    * **Inficon VGC** (Vacuum Gauge Controller via TCP/IP)
* **Flexible Logging:**
    * **CSV:** Local file logging with daily rotation.
    * **InfluxDB:** Time-series database integration for Grafana dashboards.
    * **Slack:** Error notifications and alerts.
* **Resilience:** Built-in retry logic using `tenacity` for robust network operations.
* **Dry Run Mode:** Simulates device data for testing without hardware.

## 📂 Project Structure

```text
src/
└── irlab_ctl/
    ├── __main__.py          # Entry point (Main Loop)
    ├── config.py            # Configuration loader
    ├── device_manager.py    # Orchestrates data collection
    ├── configs/
    │   └── config.toml      # User configuration file
    ├── devices/             # Device Drivers
    │   ├── lakeshore.py     # TCP Driver for Model 224
    │   ├── onewire.py       # HTTP Driver for OW-Server
    │   ├── ups.py           # SNMP Driver for APC UPS
    │   ├── pdu.py           # SNMP Driver for Eaton PDU
    │   └── inficon.py       # TCP Driver for Inficon VGC
    └── utils/
        ├── csv_logger.py       # CSV handling
        ├── influxdb_logger.py  # InfluxDB Write Logic
        └── slack_alert.py      # Slack Notification Logic