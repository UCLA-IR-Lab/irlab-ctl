import asyncio
import logging
import xml.etree.ElementTree as ET
import aiohttp
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

logger = logging.getLogger(__name__)

@dataclass
class SensorData:
    """
    Unified class for sensor data. 
    Holds fields for EDS0065 (Temp/Humdity) and EDS0068 (Temp/Humdity/Pressure/Light).
    """
    rom_id: Optional[str] = None
    device_type: Optional[str] = None
    health: Optional[int] = None
    channel: Optional[int] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    dew_point: Optional[float] = None
    humidex: Optional[float] = None
    heat_index: Optional[float] = None
    pressure_mb: Optional[float] = None
    pressure_hg: Optional[float] = None
    illuminance: Optional[int] = None

@dataclass
class ONEWIREDATA:
    """Class to hold aggregation of data from OneWire Server"""
    poll_count: Optional[int] = None
    devices_connected: Optional[int] = None
    loop_time: Optional[float] = None
    device_name: Optional[str] = None
    host_name: Optional[str] = None
    mac_address: Optional[str] = None
    sensors: List[SensorData] = field(default_factory=list)

    def read_sensors(self):
        """Returns a list of dictionaries for all sensors."""
        return [asdict(s) for s in self.sensors]

class ONEWIRE_SERVER:
    """Class for interfacing with OneWire Server via HTTP XML"""
    def __init__(self, host, timeout=10):
        self.host = host
        self.timeout = timeout
        self.url = f"http://{self.host}/details.xml"
        self.ow_data = ONEWIREDATA()

    async def _get_xml_data(self):
        """Fetches the details.xml file asynchronously using aiohttp."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.url, timeout=self.timeout) as response:
                    if response.status != 200:
                        logger.error(f"OW-Server at {self.host} returned status {response.status}")
                        return None
                    return await response.text()
            except Exception as e:
                logger.error(f"Error fetching data from OW-Server at {self.host}: {e}")
                raise

    def _parse_float(self, text):
        """Helper to parse float from string, handling units like '29.5 C'."""
        if not text:
            return None
        try:
            return float(text.strip().split()[0])
        except (ValueError, IndexError):
            return None

    def _parse_int(self, text):
        """Helper to parse int from string."""
        if not text:
            return None
        try:
            return int(text.strip().split()[0])
        except (ValueError, IndexError):
            return None
            
    def _strip_namespace(self, xml_content):
        return xml_content

    def _parse_xml(self, xml_content):
        """Parses the XML content and populates ONEWIREDATA."""
        try:
            root = ET.fromstring(xml_content)
            
            def find_text(element, tag_name):
                for child in element:
                    clean_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if clean_tag == tag_name:
                        return child.text
                return None

            self.ow_data.poll_count = self._parse_int(find_text(root, 'PollCount'))
            self.ow_data.devices_connected = self._parse_int(find_text(root, 'DevicesConnected'))
            self.ow_data.loop_time = self._parse_float(find_text(root, 'LoopTime'))
            self.ow_data.device_name = find_text(root, 'DeviceName')
            self.ow_data.host_name = find_text(root, 'HostName')
            self.ow_data.mac_address = find_text(root, 'MACAddress')
            
            self.ow_data.sensors = []
            
            for child in root:
                tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                if tag.startswith("owd_"):
                    sensor = SensorData()
                    
                    sensor.rom_id = find_text(child, 'ROMId')
                    sensor.device_type = find_text(child, 'Name')
                    sensor.health = self._parse_int(find_text(child, 'Health'))
                    sensor.channel = self._parse_int(find_text(child, 'Channel'))
                    
                    sensor.temperature = self._parse_float(find_text(child, 'Temperature'))
                    sensor.humidity = self._parse_float(find_text(child, 'Humidity'))
                    sensor.dew_point = self._parse_float(find_text(child, 'DewPoint'))
                    sensor.humidex = self._parse_float(find_text(child, 'Humidex'))
                    sensor.heat_index = self._parse_float(find_text(child, 'HeatIndex'))
                    
                    sensor.pressure_mb = self._parse_float(find_text(child, 'BarometricPressureMb'))
                    sensor.pressure_hg = self._parse_float(find_text(child, 'BarometricPressureHg'))
                    
                    sensor.illuminance = self._parse_int(find_text(child, 'Light'))

                    self.ow_data.sensors.append(sensor)
                    
        except ET.ParseError as e:
            logger.error(f"XML Parse Error: {e}")
            raise ValueError("Invalid XML received from OW-Server")

    async def get_data(self):
        """Main method to fetch and parse data."""
        xml_content = await self._get_xml_data()
        if xml_content:
            self._parse_xml(xml_content)
        return self.ow_data

# --- Wrapper for External Use ---
async def get_ow_data(address):
    """
    Connects to the device, retrieves data, and formats it as a list of dicts.
    """
    server = ONEWIRE_SERVER(address)
    data_obj = await server.get_data()
    return data_obj.read_sensors()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def test_connection(ip):
        print(f"\n--- Testing OneWire Connection to {ip} ---")
        
        try:
            start_time = time.time()
            sensors = await get_ow_data(ip)
            duration = time.time() - start_time
            
            print(f"✅ Success! (Took {duration:.3f}s)")
            
            if not sensors:
                print("⚠️  No sensors found or empty response.")
                return

            print(f"📡 Sensors Detected: {len(sensors)}")
            
            columns = [
                ("ROM ID", 18, "rom_id"),
                ("Temp (°C)", 10, "temperature"),
                ("Hum (%)", 8, "humidity"),
                ("Press (mb)", 11, "pressure_mb"),
                ("Press (Hg)", 11, "pressure_hg"),
                ("Light (lx)", 10, "illuminance")
            ]
            
            print("-" * 80)
            header_row = "".join([f"{col[0]:<{col[1]}}" for col in columns])
            print(header_row)
            print("-" * 80)
            
            for s in sensors:
                row_str = ""
                for name, width, key in columns:
                    val = s.get(key)
                    
                    if val is None:
                        val_str = "-"
                    elif isinstance(val, float):
                        if key in ['pressure_mb', 'pressure_hg', 'illuminance']:
                             val_str = f"{val:.2f}"
                        else:
                             val_str = f"{val:.2f}"
                    else:
                        val_str = str(val)
                        
                    row_str += f"{val_str:<{width}}"
                print(row_str)
            print("-" * 80 + "\n")

        except Exception as e:
            print(f"\n❌ Failed: {e}\n")

    ow_address = ""
    asyncio.run(test_connection(ow_address))