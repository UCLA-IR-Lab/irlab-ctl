import asyncio
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class WrongCommandError(Exception):
    """Raised when the device returns a NAK (0x15)."""
    pass

class UnknownResponse(Exception):
    """Raised when the device returns something unexpected."""
    pass

@dataclass
class GaugeChannel:
    channel: int
    status_code: int
    status_message: str
    pressure: Optional[float] = None

@dataclass
class InficonData:
    device_info: Optional[str] = None
    channels: List[GaugeChannel] = field(default_factory=list)

class INFICON_VGC:
    STATUS_MAP = {
        0: "Measurement data okay",
        1: "Underrange",
        2: "Overrange",
        3: "Sensor error",
        4: "Sensor off (PEG, MAG)",
        5: "No sensor",
        6: "Identification error",
        7: "Error BPG, HPG, BCG",
    }

    def __init__(self, host, port=8000, timeout=5):
        self.host = host
        self.port = int(port)
        self.timeout = timeout

    async def _send_command(self, command):
        """
        Handles the specific ACK/ENQ Handshake protocol (Section 5.1/5.2).
        1. Host -> Command + CR LF
        2. Device -> ACK (0x06)
        3. Host -> ENQ (0x05)
        4. Device -> Data String
        """
        full_cmd = f"{command}\r\n".encode('ascii')
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), 
                timeout=self.timeout
            )
            
            # 1. Send Command
            writer.write(full_cmd)
            await writer.drain()
            
            # 2. Read ACK
            res = await asyncio.wait_for(reader.readuntil(b'\r\n'), timeout=self.timeout)
            ack = res.strip()
            
            # 3. Check Response
            if ack.startswith(b'\x06'): # ACK
                # 4. Send Enquiry (ENQ) to request the actual data
                writer.write(b'\x05')
                await writer.drain()
                
                # 5. Read Data
                res = await asyncio.wait_for(reader.readuntil(b'\r\n'), timeout=self.timeout)
                writer.close()
                await writer.wait_closed()
                
                return res.strip().decode('ascii')
                
            elif ack.startswith(b'\x15'): # NAK
                writer.close()
                await writer.wait_closed()
                raise WrongCommandError(f"Device returned NAK for command '{command}'")
                
            else:
                writer.close()
                await writer.wait_closed()
                raise UnknownResponse(f"Unknown response: {ack}")

        except (asyncio.TimeoutError, OSError) as e:
            logger.error(f"Inficon Connection Error ({self.host}): {e}")
            raise IOError(f"Failed to connect to Inficon at {self.host}") from e

    async def get_device_info(self):
        """
        Sends the AYT (Are You There) command to retrieve device identification.
        """
        return await self._send_command("AYT")

    async def get_pressures(self):
        """
        Sends PRX and parses the CSV response.
        """
        resp = await self._send_command("PRX")
        if not resp:
            raise IOError("Failed to retrieve pressure data")
            
        parts = [p.strip() for p in resp.split(',')]
        channels = []
        num_channels = len(parts) // 2
        
        for i in range(num_channels):
            status_idx = i * 2
            pressure_idx = status_idx + 1
            try:
                status = int(parts[status_idx])
                pressure = float(parts[pressure_idx]) if status == 0 else None
                
                channels.append(GaugeChannel(
                    channel=i + 1, 
                    status_code=status, 
                    status_message=self.STATUS_MAP.get(status, "Unknown"), 
                    pressure=pressure
                ))
            except (ValueError, IndexError):
                pass
        return channels

    async def get_data(self):
        """
        Standard polling method used by device_manager.
        """
        data = InficonData()
        try:
            # data.device_info = await self.get_device_info()
            data.channels = await self.get_pressures()
        except IOError:
            raise
        
        output = {
            'device_info': data.device_info
        }
        
        for ch in data.channels:
            prefix = f"ch{ch.channel}"
            output[f"{prefix}_pressure"] = ch.pressure
            output[f"{prefix}_status_code"] = ch.status_code
            
        return {'inficon_data': output}

# --- Wrapper for External Use ---
async def get_vgc_data(address):
    device = INFICON_VGC(address)
    return await device.get_data()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    async def test_connection(ip):
        print(f"--- Testing Inficon VGC Connection to {ip} ---")
        device = INFICON_VGC(ip)
        
        try:
            print("Sending AYT & PRX commands...")
            result = await device.get_data()
            
            print("\n✅ Success! Received Data:")
            data = result.get('inficon_data', {})
            
            sorted_keys = sorted(data.keys())
            for key in sorted_keys:
                val = data[key]
                print(f"  {key:<20}: {val}")
                
        except Exception as e:
            print(f"\n❌ Failed: {e}")

    inficon_address = ""
    asyncio.run(test_connection(inficon_address))