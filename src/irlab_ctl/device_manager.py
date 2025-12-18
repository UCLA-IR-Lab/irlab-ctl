import asyncio
import random
import logging

from . import config as cfg
from .devices import onewire, lakeshore, ups, pdu, inficon

logger = logging.getLogger(__name__)

# --- Mock Data Generation (For Dry Run) ---
def generate_mock_data():
    # Matches structure of LakeShore Data
    ls224_data = {
        'model': 'MOCK-LS224',
        'temp_a': 300.0 + random.uniform(-0.5, 0.5),
        'temp_b': 4.2 + random.uniform(-0.1, 0.1),
        'temp_c1': 295.0,
        'temp_d1': 77.0
    }
    
    # Matches structure of Inficon Data
    vgc_data = {'inficon_data': {
        'device': 'MOCK-INFICON',
        'ch1_pressure': 1.2e-4, 'ch1_status_code': 0,
        'ch2_pressure': 5.6e-7, 'ch2_status_code': 0,
        'ch3_pressure': None, 'ch3_status_code': 5
    }}
    
    # Matches structure of OneWire
    ow_list = []
    for i in range(cfg.OW_SENSOR_CNT):
        sensor = {
            'rom_id': f'MOCK-OW-{i}',
            'temperature': 22.5 + (i * 0.1),
            'humidity': 45.0,
            'dew_point': 10.0,
            'humidex': 23.0,
            'heat_index': 23.0
        }
        if i >= cfg.OW_SENSOR_CNT - 3:
            sensor.update({'pressure_mb': 1013.25, 'illuminance': 250})
        ow_list.append(sensor)
    ow_data = {'ow_data': ow_list}
    
    # Matches structure of UPS Data
    ups_data = {'ups_data': {
        'status': 'On Line', 
        'battery_temp_c': 27.5, 
        'battery_capacity_pct': 100.0,
        'input_voltage': 120.0,
        'output_load_pct': 15.0
    }}

    # Matches structure of PDU Data
    pdu_data = {'pdu_data': {
        'input_voltage': 208.0, 
        'input_power': 1500.0, 
        'input_current': 7.2, 
        'outlet_name': [f"Outlet {j+1}" for j in range(8)], 
        'outlet_current': [0.5]*8, 
        'outlet_power': [100.0]*8
    }}
    
    return ls224_data, ow_data, ups_data, pdu_data, vgc_data

async def collect_all_device_data():
    """
    Orchestrates the parallel collection of data from all enabled devices.
    Returns dictionaries for each device (empty if disabled or error).
    """
    if cfg.DRY_RUN:
        return generate_mock_data()

    async def no_op(): return {}

    # 1. Create Coroutines
    task_ls = lakeshore.get_ls_data(cfg.LS224_ADDRESS) if cfg.ENABLE_LS224 else no_op()
    task_ow = onewire.get_ow_data(cfg.OW_ADDRESS) if cfg.ENABLE_OW else no_op()
    task_ups = ups.get_ups_data(cfg.UPS_ADDRESS) if cfg.ENABLE_UPS else no_op()
    task_pdu = pdu.get_pdu_data(cfg.PDU_ADDRESS) if cfg.ENABLE_PDU else no_op()
    task_vgc = inficon.get_vgc_data(cfg.INFICON_ADDRESS) if cfg.ENABLE_INFICON else no_op()

    # 2. Run in Parallel
    results = await asyncio.gather(
        task_ls, 
        task_ow, 
        task_ups, 
        task_pdu, 
        task_vgc, 
        return_exceptions=True
    )

    # 3. Unpack and Handle Errors
    clean_results = []
    device_names = ['Lakeshore', 'OneWire', 'UPS', 'PDU', 'Inficon']
    
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            logger.error(f"Error fetching {device_names[i]}: {res}")
            clean_results.append({}) 
        else:
            clean_results.append(res)

    ls224_data, ow_raw, ups_data, pdu_data, vgc_data = clean_results

    # 4. Standardize Data Structures
    if isinstance(ow_raw, list):
        ow_data = {'ow_data': ow_raw}
    else:
        ow_data = ow_raw if ow_raw else {}

    return ls224_data, ow_data, ups_data, pdu_data, vgc_data

def flatten_data_for_csv(datetime_str, ls224_data, ow_data, ups_data, pdu_data, vgc_data):
    """
    Flattens complex device dictionaries into a single depth dictionary.
    """
    csv_row = {'datetime': datetime_str}
    
    # --- Lakeshore 224 ---
    ls = ls224_data.get('ls224_data', ls224_data) 
    csv_row['ls224_temp_a']  = ls.get('temp_a')
    csv_row['ls224_temp_b']  = ls.get('temp_b')
    csv_row['ls224_temp_c1'] = ls.get('temp_c1')
    csv_row['ls224_temp_d1'] = ls.get('temp_d1')
    
    # --- Inficon VGC ---
    vgc = vgc_data.get('inficon_data', {})
    for i in range(1, 4):
        csv_row[f'vgc_pres_{i}'] = vgc.get(f'ch{i}_pressure')
        csv_row[f'vgc_stat_{i}'] = vgc.get(f'ch{i}_status_code')

    # --- OneWire ---
    od = ow_data.get('ow_data', [])
    
    for i in range(cfg.OW_SENSOR_CNT):
        idx = i + 1
        s = od[i] if i < len(od) else {}
        
        for f in ['temperature', 'humidity', 'dew_point', 'humidex', 'heat_index']:
            key_name = f'ow_{f.replace("_","")}_{idx}'
            csv_row[key_name] = s.get(f)
            
        csv_row[f'ow_rom_{idx}'] = s.get('rom_id')
    
    total = len(od)
    if total > 7:
        csv_row['ow_pressure_1'] = od[7].get('pressure_mb')
        csv_row['ow_light_1'] = od[7].get('illuminance')
    if total > 8:
        csv_row['ow_pressure_2'] = od[8].get('pressure_mb')
        csv_row['ow_light_2'] = od[8].get('illuminance')
    if total > 9:
        csv_row['ow_pressure_3'] = od[9].get('pressure_mb')
        csv_row['ow_light_3'] = od[9].get('illuminance')

    # --- UPS ---
    ups_inner = ups_data.get('ups_data', {})
    csv_row['ups_temp'] = ups_inner.get('battery_temp_c') or ups_inner.get('battery_temp')

    # --- PDU ---
    pdu = pdu_data.get('pdu_data', {})
    csv_row['pdu_in_vol'] = pdu.get('input_voltage')
    csv_row['pdu_in_cur'] = pdu.get('input_current')
    csv_row['pdu_in_pwr'] = pdu.get('input_power')
    
    out_names = pdu.get('outlet_name', [])
    out_currs = pdu.get('outlet_current', [])
    out_pwrs = pdu.get('outlet_power', [])
    
    if len(out_names) > 6:
        csv_row['pdu_a7_name'] = out_names[6]
        csv_row['pdu_a7_cur']  = out_currs[6]
        csv_row['pdu_a7_pwr']  = out_pwrs[6]

    return csv_row