import asyncio
import logging
from pysnmp.hlapi.v1arch.asyncio import *

logger = logging.getLogger(__name__)

class UPS:
    OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    OID_MODEL_NAME = "1.3.6.1.4.1.318.1.1.1.1.1.1.0"
    OID_BATT_CAPACITY = "1.3.6.1.4.1.318.1.1.1.2.2.1.0"
    OID_BATT_TEMP = "1.3.6.1.4.1.318.1.1.1.2.2.2.0"
    OID_BATT_RUNTIME = "1.3.6.1.4.1.318.1.1.1.2.2.3.0"
    OID_BATT_REPLACE = "1.3.6.1.4.1.318.1.1.1.2.2.4.0"
    OID_INPUT_VOLTAGE = "1.3.6.1.4.1.318.1.1.1.3.2.1.0"
    OID_INPUT_FREQ = "1.3.6.1.4.1.318.1.1.1.3.2.4.0"
    OID_OUTPUT_VOLTAGE = "1.3.6.1.4.1.318.1.1.1.4.2.1.0"
    OID_OUTPUT_LOAD = "1.3.6.1.4.1.318.1.1.1.4.2.3.0"
    OID_OUTPUT_STATUS = "1.3.6.1.4.1.318.1.1.1.4.1.1.0"

    def __init__(self, address, community='public'):
        self.address = address
        self.community = community
        self.snmpDispatcher = SnmpDispatcher()
        self.semaphore = asyncio.Semaphore(5)

    def close(self):
        self.snmpDispatcher.transport_dispatcher.close_dispatcher()

    async def get_scalar(self, oid):
        """Performs a simple SNMP GET for single values."""
        async with self.semaphore:
            iterator = await get_cmd(
                self.snmpDispatcher,
                CommunityData(self.community, mpModel=0),
                await UdpTransportTarget.create((self.address, 161), timeout=2, retries=2),
                (oid, None),
            )
            errorIndication, errorStatus, _, varBinds = iterator
            
            if errorIndication or errorStatus:
                return None
            return varBinds[0][1].prettyPrint()

    async def get_data(self):
        """Fetches all relevant UPS data."""
        ups_data = {'ups_data': {}}
        
        try:
            model = await self.get_scalar(self.OID_MODEL_NAME)
            if not model:
                model = await self.get_scalar(self.OID_SYS_DESCR)
                if not model:
                    return ups_data
            
            results = await asyncio.gather(
                self.get_scalar(self.OID_BATT_CAPACITY),
                self.get_scalar(self.OID_BATT_TEMP),
                self.get_scalar(self.OID_BATT_RUNTIME),
                self.get_scalar(self.OID_INPUT_VOLTAGE),
                self.get_scalar(self.OID_INPUT_FREQ),
                self.get_scalar(self.OID_OUTPUT_VOLTAGE),
                self.get_scalar(self.OID_OUTPUT_LOAD),
                self.get_scalar(self.OID_OUTPUT_STATUS)
            )

            batt_cap = float(results[0] or 0)
            batt_temp = float(results[1] or 0)
            
            raw_runtime = results[2]
            runtime_min = 0.0
            if raw_runtime:
                try:
                    ticks = float(raw_runtime)
                    runtime_min = round(ticks / 6000.0, 1)
                except ValueError:
                    pass

            input_v = float(results[3] or 0)
            input_hz = float(results[4] or 0)
            output_v = float(results[5] or 0)
            output_load = float(results[6] or 0)
            
            status_code = int(results[7] or 0)
            status_map = {
                2: "On Line",
                3: "On Battery",
                4: "Smart Boost",
                5: "Sleeping",
                6: "Bypass",
                7: "Off",
                8: "Rebooting"
            }
            status_str = status_map.get(status_code, "Unknown")

            ups_data['ups_data'] = {
                'model': model,
                'status': status_str,
                'battery_capacity_pct': batt_cap,
                'battery_temp': batt_temp,
                'battery_runtime_min': runtime_min,
                'input_voltage': input_v,
                'input_freq': input_hz,
                'output_voltage': output_v,
                'output_load_pct': output_load
            }

        except Exception as e:
            logger.error(f"UPS Fetch Error: {e}")
        finally:
            self.close()
            
        return ups_data

# --- Wrapper for External Use ---
async def get_ups_data(address):
    ups = UPS(address)
    return await ups.get_data()

if __name__ == "__main__":
    import time
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    async def test_connection(ip):
        print(f"\n--- Testing APC UPS at {ip} ---")
        ups = UPS(ip)
        
        try:
            start = time.time()
            res = await ups.get_data()
            dur = time.time() - start
            
            data = res.get('ups_data')
            
            if not data:
                print("❌ Failed to contact UPS. Check IP and Community String.")
                return

            print(f"✅ Success! (Took {dur:.3f}s)")
            print(f"📦 Model: {data.get('model')}")
            
            # Status Icon
            stat = data.get('status')
            icon = "🟢" if stat == "On Line" else "🟠" if stat == "On Battery" else "🔴"
            
            print("\n🔋 UPS Status:")
            print("-" * 50)
            print(f"   System State:     {icon} {stat}")
            print(f"   Battery Charge:   {data.get('battery_capacity_pct')}%")
            print(f"   Runtime Remain:   {data.get('battery_runtime_min')} min")
            print(f"   Internal Temp:    {data.get('battery_temp_c')} °C")
            print("-" * 50)
            
            print("\n⚡ Power Readings:")
            print("-" * 50)
            print(f"   Input:            {data.get('input_voltage')} V  ({data.get('input_freq')} Hz)")
            print(f"   Output:           {data.get('output_voltage')} V")
            print(f"   Load:             {data.get('output_load_pct')}%")
            print("-" * 50 + "\n")

        except Exception as e:
            print(f"Error: {e}")

    ups_address = ""
    try:
        asyncio.run(test_connection(ups_address))
    except KeyboardInterrupt:
        pass