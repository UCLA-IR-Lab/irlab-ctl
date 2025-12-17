import os
import sys
import logging
import tomllib


# Operation Settings
OPERATION_MODE = "logging"
TEST_NAME = "Default_Test"
DRY_RUN = False

# Device Enable Flags
ENABLE_LS224 = True
ENABLE_OW = True
ENABLE_UPS = True
ENABLE_PDU = True
ENABLE_INFICON = True

# Logging/Alert Enable Flags
ENABLE_INFLUX = True
ENABLE_SLACK = True
ENABLE_CSV = True

# Device Addresses & Metadata
OW_ADDRESS = None
OW_SENSOR_CNT = 10
PDU_ADDRESS = None
UPS_ADDRESS = None
LS224_ADDRESS = None
INFICON_ADDRESS = None

# CSV Logging
CSV_LOG_PATH = None
CSV_BASE_FILENAME = None
CSV_HEADER = []

# InfluxDB Credentials
INFLUX_URL = None
INFLUX_TOKEN = None
INFLUX_ORG = None
INFLUX_BUCKET = None

# Slack Credentials
SLACK_CHANNEL = None
SLACK_TOKEN = None

def load_config(config_path=None, test_name_override=None, dry_run_mode=False):
    """
    Loads configuration from a TOML file and sets global variables.
    """
    global OPERATION_MODE, TEST_NAME, DRY_RUN
    global ENABLE_LS224, ENABLE_OW, ENABLE_UPS, ENABLE_PDU, ENABLE_INFICON
    global ENABLE_INFLUX, ENABLE_SLACK, ENABLE_CSV
    global OW_ADDRESS, PDU_ADDRESS, UPS_ADDRESS, LS224_ADDRESS, INFICON_ADDRESS, OW_SENSOR_CNT
    global CSV_LOG_PATH, CSV_BASE_FILENAME, CSV_HEADER
    global INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET
    global SLACK_CHANNEL, SLACK_TOKEN

    DRY_RUN = dry_run_mode

    if config_path is None:
        base_dir = os.path.dirname(__file__)
        config_path = os.path.join(base_dir, "configs", "config.toml")

    try:
        with open(config_path, "rb") as f:
            _cfg = tomllib.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {config_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing config file: {e}")
        sys.exit(1)

    # 1. Operation Section [operation]
    _op = _cfg.get("operation", {})
    OPERATION_MODE = _op.get("mode", "logging")
    TEST_NAME = test_name_override if test_name_override else _op.get("test_name", "unknown_test")

    # 2. Enabled Devices Section [enabled.devices]
    _enabled = _cfg.get("enabled", {})
    _en_dev = _enabled.get("devices", {})
    ENABLE_LS224 = _en_dev.get("lakeshore", True)
    ENABLE_OW = _en_dev.get("onewire", True)
    ENABLE_UPS = _en_dev.get("ups", True)
    ENABLE_PDU = _en_dev.get("pdu", True)
    ENABLE_INFICON = _en_dev.get("inficon", True)
    
    # 3. Enabled Logging Section [enabled.logging]
    _en_log = _enabled.get("logging", {})
    ENABLE_INFLUX = _en_log.get("influxdb", True)
    ENABLE_SLACK = _en_log.get("slack", True)
    ENABLE_CSV = _en_log.get("csv", True)

    # 4. Device Addresses [devices]
    _devs = _cfg.get("devices", {})
    OW_ADDRESS = _devs.get("ow_address")
    PDU_ADDRESS = _devs.get("pdu_address")
    UPS_ADDRESS = _devs.get("ups_address")
    LS224_ADDRESS = _devs.get("ls224_address")
    INFICON_ADDRESS = _devs.get("inficon_address")
    
    # OneWire Specifics [devices.ow]
    _devs_ow = _devs.get("ow", {})
    OW_SENSOR_CNT = _devs_ow.get("sensor_count", 10)

    # 5. Logging Configuration (Top Level [logging])
    _log_cfg = _cfg.get("logging", {})

    # CSV Logging [logging.csv]
    _log_csv = _log_cfg.get("csv", {})
    CSV_LOG_PATH = _log_csv.get("directory", "./data/logs")
    CSV_BASE_FILENAME = _log_csv.get("filename", "sensor_log")

    # InfluxDB [logging.influxdb]
    _log_inf = _log_cfg.get("influxdb", {})
    INFLUX_URL = _log_inf.get("url")
    INFLUX_TOKEN = _log_inf.get("token")
    INFLUX_ORG = _log_inf.get("org")
    INFLUX_BUCKET = _log_inf.get("bucket")

    # Slack [logging.slack]
    _log_slack = _log_cfg.get("slack", {})
    SLACK_CHANNEL = _log_slack.get("channel")
    SLACK_TOKEN = _log_slack.get("token")

    # 6. Generate CSV Header based on enabled devices
    if ENABLE_CSV:
        CSV_HEADER.clear()
        CSV_HEADER.append("datetime")
        
        if ENABLE_LS224: 
            CSV_HEADER.extend(["ls224_temp_a", "ls224_temp_b", "ls224_temp_c1", "ls224_temp_d1"])
        
        if ENABLE_INFICON: 
            CSV_HEADER.extend(["vgc_pres_1", "vgc_pres_2", "vgc_pres_3", "vgc_stat_1", "vgc_stat_2", "vgc_stat_3"])
        
        if ENABLE_OW:
            for i in range(1, OW_SENSOR_CNT + 1):
                CSV_HEADER.extend([
                    f"ow_temp_{i}", 
                    f"ow_humidity_{i}", 
                    f"ow_dewpoint_{i}", 
                    f"ow_humidex_{i}", 
                    f"ow_heatindex_{i}"
                ])
            CSV_HEADER.extend(["ow_pressure_1", "ow_pressure_2", "ow_pressure_3", "ow_light_1", "ow_light_2", "ow_light_3"])
            for i in range(1, OW_SENSOR_CNT + 1): 
                CSV_HEADER.append(f"ow_rom_{i}")
        
        if ENABLE_UPS: 
            CSV_HEADER.append("ups_temp")
        
        if ENABLE_PDU: 
            CSV_HEADER.extend(["pdu_in_vol", "pdu_in_cur", "pdu_in_pwr", "pdu_a7_name", "pdu_a7_cur", "pdu_a7_pwr"])
    
    logging.info(f"Configuration loaded from {config_path}")
    logging.info(f"Test Name: {TEST_NAME}")