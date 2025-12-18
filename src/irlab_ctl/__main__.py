import asyncio
import datetime
import argparse
import sys
import logging
import json
from pathlib import Path
from tenacity import retry, stop_after_attempt, retry_any, retry_if_exception_type, wait_fixed, RetryCallState

from . import config as cfg
from .utils.csv_logger import CSVLogger
from .utils.influxdb_logger import INFLUXDB
from .utils.slack_alert import send_error_message
from .device_manager import collect_all_device_data, flatten_data_for_csv

def after_retry(retry_state: RetryCallState):
    if retry_state.attempt_number == 5:
        msg = f"Retry attempted 5 times. Details: {retry_state}"
        logging.error(msg)
        
        if not cfg.DRY_RUN and cfg.ENABLE_SLACK:
             send_error_message(
                 channel=cfg.SLACK_CHANNEL, 
                 token=cfg.SLACK_TOKEN, 
                 test_name=cfg.TEST_NAME, 
                 error_details=msg
             )

@retry(
    stop=stop_after_attempt(5),
    wait=wait_fixed(10),
    retry=retry_any(retry_if_exception_type(TimeoutError), retry_if_exception_type(IOError)),
    after=after_retry
)
async def cycle_task(current_time):
    """
    Performs one cycle of data collection, processing, and logging.
    """
    date_str = current_time.strftime("%Y%m%d")
    datetime_fmt = current_time.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Collect Data
    try:
        ls_data, ow_data, ups_data, pdu_data, vgc_data = await collect_all_device_data()
        
        logging.info(f"========== Device Data Snapshot [{datetime_fmt}] ==========")
        def log_section(name, data):
            if data:
                try:
                    pretty_str = json.dumps(data, indent=2, default=str)
                    formatted = "\n".join([f"  {line}" for line in pretty_str.splitlines()])
                    logging.info(f"{name}:\n{formatted}")
                except Exception:
                    logging.info(f"{name}: {data}")
            else:
                logging.info(f"{name}: [No Data / Disabled]")

        log_section("🌡️ Lakeshore 224", ls_data)
        log_section("🌡️ OneWire Sensors", ow_data)
        log_section("🔋 APC UPS", ups_data)
        log_section("🔌 Eaton PDU", pdu_data)
        log_section("🛑 Inficon VGC", vgc_data)
        logging.info("===========================================================")

    except Exception as e:
        logging.error(f"Device Polling Error: {e}")
        raise

    # 2. Save to CSV (If Enabled)
    if cfg.ENABLE_CSV:
        try:
            csv_row = flatten_data_for_csv(datetime_fmt, ls_data, ow_data, ups_data, pdu_data, vgc_data)
            with CSVLogger(cfg.CSV_LOG_PATH, date_str, cfg.CSV_BASE_FILENAME, cfg.CSV_HEADER) as csv_log:
                csv_log.save(csv_row)
            logging.info(f"✅ Logged CSV row.")
        except Exception as e:
            logging.error(f"CSV Write Error: {e}")
            raise

    # 3. Save to InfluxDB (If Enabled)
    if cfg.ENABLE_INFLUX:
        try:
            if cfg.DRY_RUN:
                logging.info("  [Dry Run] Skipping InfluxDB write.")
            else:
                with INFLUXDB(cfg.INFLUX_URL, cfg.INFLUX_TOKEN, cfg.INFLUX_ORG, cfg.INFLUX_BUCKET) as influx:
                    influx.write_data(ls_data, ow_data, ups_data, pdu_data, vgc_data, cfg.TEST_NAME)
                logging.info(f"✅ InfluxDB Write Success.")
        except Exception as e:
            logging.error(f"InfluxDB Error: {e}")
            raise

async def run_logging_loop():
    mode_str = "DRY RUN" if cfg.DRY_RUN else "LIVE"
    logging.info(f"Starting UCLA IR Lab Device Logger (Test: {cfg.TEST_NAME} | Mode: {mode_str})...")
    
    if not cfg.ENABLE_SLACK:
        logging.warning("⚠️ Slack Alerts are DISABLED.")
    if not cfg.ENABLE_INFLUX:
        logging.warning("⚠️ InfluxDB Logging is DISABLED.")
    if not cfg.ENABLE_CSV:
        logging.warning("⚠️ CSV Logging is DISABLED.")
    
    while True:
        try:
            await cycle_task(datetime.datetime.now())
            await asyncio.sleep(60)
        except Exception as err:
            logging.error(f"Main Loop Error: {err}")
            await asyncio.sleep(10)

def run_test_slack():
    if not cfg.ENABLE_SLACK:
        logging.error("Cannot run Slack test: Slack is disabled in config.")
        return

    logging.info(f"Sending test message to channel: {cfg.SLACK_CHANNEL}...")
    send_error_message(
        channel=cfg.SLACK_CHANNEL, 
        token=cfg.SLACK_TOKEN, 
        test_name=cfg.TEST_NAME, 
        error_details="Manual test via config operation mode"
    )
    logging.info("✅ Test message sent.")

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    config_dir = base_dir / "configs"
    default_config_path = config_dir / "config.toml"

    parser = argparse.ArgumentParser(description="UCLA IR Lab Device Controlling Software")
    parser.add_argument("-c", "--config", type=str, default=str(default_config_path), help=f"Path to TOML config. Default: {default_config_path}")
    parser.add_argument("-n", "--test-name", type=str, default=None, help="Override test name")
    parser.add_argument("--dry-run", action="store_true", help="Generate mock data, skip DB write")
    parser.add_argument("--test-slack", action="store_true", help="Send test Slack alert and exit")
    parser.add_argument("--logging", type=str, default="INFO", help="Set logging level")
    
    args = parser.parse_args()

    numeric_level = getattr(logging, args.logging.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"Invalid log level: {args.logging}")
        sys.exit(1)

    logging.basicConfig(level=numeric_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    resolved_config_path = Path(args.config)
    if not resolved_config_path.exists():
        logging.warning(f"Config file not found at: {resolved_config_path}")
        potential_relative = config_dir / args.config
        if potential_relative.exists():
            logging.info(f"Found config in default directory: {potential_relative}")
            resolved_config_path = potential_relative
        else:
            logging.error("Could not locate configuration file. Exiting.")
            sys.exit(1)

    cfg.load_config(config_path=str(resolved_config_path), test_name_override=args.test_name, dry_run_mode=args.dry_run)

    if args.test_slack:
        run_test_slack()
        sys.exit(0)

    if cfg.OPERATION_MODE == "logging":
        try:
            asyncio.run(run_logging_loop())
        except KeyboardInterrupt:
            logging.info("Stopping Logger...")
    elif cfg.OPERATION_MODE == "test_slack":
        run_test_slack()
    else:
        logging.error(f"Unknown operation mode: {cfg.OPERATION_MODE}")
        sys.exit(1)