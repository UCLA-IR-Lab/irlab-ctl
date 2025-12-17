import asyncio
import logging
from pysnmp.hlapi.v1arch.asyncio import *

logger = logging.getLogger(__name__)

class PDU:
    OID_SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    OID_INPUT_VOLTAGE_BASE = "1.3.6.1.4.1.534.6.6.7.3.2.1.3" 
    OID_INPUT_CURRENT_BASE = "1.3.6.1.4.1.534.6.6.7.3.3.1.4"
    OID_INPUT_TOTAL_PF_BASE = "1.3.6.1.4.1.534.6.6.7.3.5.1.7"
    OID_OUTLET_NAME_BASE = "1.3.6.1.4.1.534.6.6.7.6.1.1.3"
    OID_OUTLET_CURRENT_BASE = "1.3.6.1.4.1.534.6.6.7.6.4.1.3"
    OID_OUTLET_PF_BASE = "1.3.6.1.4.1.534.6.6.7.6.5.1.6"
    OID_OUTLET_COUNT = "1.3.6.1.4.1.534.6.6.7.1.2.1.22.0"

    def __init__(self, address, community='public'):
        self.address = address
        self.community = community
        self.snmpDispatcher = SnmpDispatcher()
        self.semaphore = asyncio.Semaphore(5)

    def close(self):
        self.snmpDispatcher.transport_dispatcher.close_dispatcher()

    async def get_next(self, oid_start, milliscale=False):
        """
        Performs an SNMP GETNEXT operation. 
        This is robust: querying .0.0 will return .0.1 (or whatever the first index is).
        """
        async with self.semaphore:
            iterator = await next_cmd(
                self.snmpDispatcher,
                CommunityData(self.community, mpModel=0), 
                await UdpTransportTarget.create((self.address, 161), timeout=2, retries=2),
                (oid_start, None),
            )
            
            errorIndication, errorStatus, errorIndex, varBinds = iterator
            
            if errorIndication:
                return None
            elif errorStatus:
                return None
            else:
                val = varBinds[0][1].prettyPrint()
                if milliscale:
                    return self.decode_milliscale(val)
                return val

    async def get_scalar(self, oid):
        """Performs a simple GET for single values (like sysDescr)."""
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

    def decode_milliscale(self, value):
        """Converts milli-units (mA, mV) to standard units (A, V)."""
        try:
            value = float(value)
        except ValueError:
            return 0.0
        return round(value / 1000.0, 3)
    
    async def get_data(self):
        """
        Main method to fetch all PDU data. 
        Renamed from rack_test to standard get_data() for consistency.
        """
        pdu_data = {'pdu_data': {}}
        
        try:
            sys_descr = await self.get_scalar(self.OID_SYS_DESCR)
            if not sys_descr:
                return pdu_data
            
            count_val = await self.get_scalar(self.OID_OUTLET_COUNT)
            if count_val and str(count_val).isdigit():
                num_outlets = int(count_val)
            else:
                num_outlets = 8
            
            fut_iv = self.get_next(f"{self.OID_INPUT_VOLTAGE_BASE}.0.1.0", True)
            fut_ic = self.get_next(f"{self.OID_INPUT_CURRENT_BASE}.0.1.0", True)
            fut_ipf = self.get_next(f"{self.OID_INPUT_TOTAL_PF_BASE}.0.0.0", True)

            futs_name = []
            futs_curr = []
            futs_pf = []

            for i in range(num_outlets):
                prev_idx = f".0.{i}" 
                futs_name.append(self.get_next(self.OID_OUTLET_NAME_BASE + prev_idx))
                futs_curr.append(self.get_next(self.OID_OUTLET_CURRENT_BASE + prev_idx, True))
                futs_pf.append(self.get_next(self.OID_OUTLET_PF_BASE + prev_idx, True))

            results = await asyncio.gather(fut_iv, fut_ic, fut_ipf, *futs_name, *futs_curr, *futs_pf)
            
            input_volts = results[0] or 0.0
            input_amps = results[1] or 0.0
            
            start_name = 3
            end_name = start_name + num_outlets
            end_curr = end_name + num_outlets
            end_pf = end_curr + num_outlets

            names = results[start_name:end_name]
            currents = results[end_name:end_curr]
            pfs = results[end_curr:end_pf]

            input_power = round(input_volts * input_amps, 3)
            
            outlet_data_names = []
            outlet_data_curr = []
            outlet_data_power = []

            for i in range(num_outlets):
                n = names[i] or f"Outlet {i+1}"
                c = currents[i] or 0.0
                pf = pfs[i] or 0.0
                
                p = round(input_volts * c * abs(pf), 3)
                
                outlet_data_names.append(n)
                outlet_data_curr.append(c)
                outlet_data_power.append(p)

            pdu_data['pdu_data'] = {
                'input_voltage': input_volts,
                'input_current': input_amps,
                'input_power': input_power,
                'outlet_name': outlet_data_names,
                'outlet_current': outlet_data_curr,
                'outlet_power': outlet_data_power
            }

        except Exception as e:
            logger.error(f"PDU Fetch Error: {e}")
        finally:
            self.close()
            
        return pdu_data

# --- Wrapper for External Use ---
async def get_pdu_data(address):
    pdu = PDU(address)
    return await pdu.get_data()

if __name__ == "__main__":
    import time
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    async def test_connection(ip, community="public"):
        print(f"\n--- Testing Eaton ePDU to {ip} ---")
        pdu = PDU(ip, community)
        
        try:
            start_time = time.time()
            result = await pdu.get_data()
            duration = time.time() - start_time
            
            data = result.get('pdu_data')
            
            if not data:
                print("❌ Failed to contact device or retrieve data.")
                return

            print(f"✅ Success! (Took {duration:.3f}s)")
            
            print("\n🔌 Input Phase:")
            print(f"   Voltage: {data.get('input_voltage', 0):.2f} V")
            print(f"   Current: {data.get('input_current', 0):.2f} A")
            print(f"   Power:   {data.get('input_power', 0):.2f} W")

            names = data.get('outlet_name', [])
            currents = data.get('outlet_current', [])
            powers = data.get('outlet_power', [])
            
            if not names:
                print("\n⚠️  No outlet data found.")
                return

            print("\n📊 Outlet Status:")
            print("-" * 65)
            print(f"{'#':<4} | {'Name':<25} | {'Current (A)':<12} | {'Power (W)':<10}")
            print("-" * 65)
            
            for i, name in enumerate(names):
                curr = currents[i] if i < len(currents) else 0.0
                pwr = powers[i] if i < len(powers) else 0.0
                
                print(f"{i+1:<4} | {name:<25} | {curr:<12.3f} | {pwr:<10.3f}")
            print("-" * 65 + "\n")

        except Exception as e:
            print(f"Critical Error: {e}")

    pdu_address = ""
    pdu_community = "public"
    try:
        asyncio.run(test_connection(pdu_address, pdu_community))
    except KeyboardInterrupt:
        pass