import asyncio
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict

logger = logging.getLogger(__name__)

@dataclass
class LakeshoreData:
    model: str = "Unknown"
    temp_a: Optional[float] = None
    temp_b: Optional[float] = None
    temp_c1: Optional[float] = None
    temp_d1: Optional[float] = None
    
class Lakeshore224:
    """
    Driver for Lakeshore Model 224 Temperature Monitor via TCP/IP.
    """
    def __init__(self, host, port=7777, timeout=5):
        if isinstance(host, dict):
            self.host = host.get('address') or host.get('ls224_address') or str(host)
        else:
            self.host = str(host).strip()
            
        self.port = int(port)
        self.timeout = timeout

    async def _send_command(self, cmd: str) -> str:
        """
        Connects, sends a command, reads one line of response, and closes.
        """
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout
            )
            
            command = f"{cmd}\r\n"
            writer.write(command.encode('ascii'))
            await writer.drain()
            
            response = await asyncio.wait_for(reader.readline(), timeout=self.timeout)
            response_str = response.decode('ascii').strip()
            
            return response_str

        except (asyncio.TimeoutError, OSError) as e:
            raise IOError(f"Failed to connect to Lakeshore at {self.host}") from e
        
        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

    async def get_data(self) -> Dict:
        """
        Fetches temperature data from the device.
        Parses 12 comma-separated values (A, B, C1-C5, D1-D5).
        """
        data = LakeshoreData()
        
        data.model = "LS224"
        
        try:
            krdg = await self._send_command("KRDG? 0")
            
            if krdg:
                temps = krdg.split(',')
                
                if len(temps) > 0: 
                    data.temp_a = float(temps[0])
                
                if len(temps) > 1: 
                    data.temp_b = float(temps[1])
                
                if len(temps) > 2: 
                    data.temp_c1 = float(temps[2])
                
                if len(temps) > 7: 
                    data.temp_d1 = float(temps[7])

        except Exception as e:
            logger.error(f"Lakeshore Data Fetch Failed ({self.host}): {e}")
            raise
            
        return asdict(data)

# --- Wrapper for External Use ---
async def get_ls_data(address):
    if isinstance(address, dict):
        address = address.get('address') or address.get('ls224_address')
        
    ls = Lakeshore224(address)
    
    return {'ls224_data': await ls.get_data()}

if __name__ == "__main__":
    import time
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    async def test_connection(ip):
        print(f"\n--- Testing Lakeshore 224 at {ip} ---")
        
        try:
            start = time.time()
            result = await get_ls_data(ip)
            dur = time.time() - start
            
            data = result.get('ls224_data', {})
            
            print(f"✅ Success (Took {dur:.3f}s)")
            print(f"Wrapper Key Present: {'ls224_data' in result}")
            print("-" * 30)
            print(f"Input A  (Index 0): {data.get('temp_a')} K")
            print(f"Input B  (Index 1): {data.get('temp_b')} K")
            print(f"Input C1 (Index 2): {data.get('temp_c1')} K")
            print(f"Input D1 (Index 7): {data.get('temp_d1')} K")
            print("-" * 30 + "\n")
            
        except Exception as e:
            print(f"❌ Error: {e}")

    ls_address = ""
    try:
        asyncio.run(test_connection(ls_address))
    except KeyboardInterrupt:
        pass