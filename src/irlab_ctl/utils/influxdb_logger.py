import logging
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .. import config as cfg

class INFLUXDB:
    def __init__(self, url, token, org, bucket):
        self.url, self.token, self.org, self.bucket = url, token, org, bucket
        self.client, self.write_api = None, None

    def __enter__(self):
        self.client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.client: 
            self.client.close()

    def write_data(self, ls, ow, ups, pdu, vgc, test_name):
        """
        Writes collected device data to InfluxDB.
        Only processes devices that are explicitly enabled in config.
        """
        points = []
        
        def add_smart_fields(point, data_dict):
            """
            Iterates over a dictionary and adds valid fields to the Point.
            """
            for k, v in data_dict.items():
                if v is None: continue
                if isinstance(v, (list, dict)): continue
                
                if isinstance(v, (int, float)):
                    point.field(k, float(v))
                elif isinstance(v, str):
                    try:
                        point.field(k, float(v))
                    except ValueError:
                        point.field(k, v)

        # 1. Lakeshore 224
        if cfg.ENABLE_LS224:
            ls_data = ls.get('ls224_data', {})
            if ls_data:
                p = Point("ls224_data").tag("test_name", test_name)
                add_smart_fields(p, ls_data)
                points.append(p)
            
        # 2. Inficon VGC
        if cfg.ENABLE_INFICON:
            vgc_data = vgc.get('inficon_data', {})
            if vgc_data:
                p = Point("inficon_data").tag("test_name", test_name)
                add_smart_fields(p, vgc_data)
                points.append(p)
        
        # 3. UPS
        if cfg.ENABLE_UPS:
            ups_data = ups.get('ups_data', {})
            if ups_data:
                p = Point("ups_data").tag("test_name", test_name)
                add_smart_fields(p, ups_data)
                points.append(p)
        
        # 4. PDU
        if cfg.ENABLE_PDU:
            pdu_data = pdu.get('pdu_data', {})
            if pdu_data:
                p = Point("pdu_data").tag("test_name", test_name)
                if pdu_data.get('input_voltage') is not None:
                    p.field('input_voltage', float(pdu_data['input_voltage']))
                if pdu_data.get('input_power') is not None:
                    p.field('input_power', float(pdu_data['input_power']))
                if pdu_data.get('input_current') is not None:
                    p.field('input_current', float(pdu_data['input_current']))
                points.append(p)
                
                o_names = pdu_data.get('outlet_name', [])
                o_currs = pdu_data.get('outlet_current', [])
                o_pwrs = pdu_data.get('outlet_power', [])

                if o_names and o_currs and o_pwrs:
                    for name, curr, pwr in zip(o_names, o_currs, o_pwrs):
                        p_out = Point("pdu_data").tag("test_name", test_name)
                        p_out.tag("outlet_name", str(name))
                        
                        try:
                            p_out.field("outlet_current", float(curr))
                            p_out.field("outlet_power", float(pwr))
                            points.append(p_out)
                        except (ValueError, TypeError):
                            continue

        # 5. OneWire
        if cfg.ENABLE_OW:
            ow_list = ow.get('ow_data', [])
            if isinstance(ow_list, list):
                for sensor in ow_list:
                    if not isinstance(sensor, dict): continue
                    
                    p = Point("ow_data").tag("test_name", test_name)
                    rom_id = sensor.get('rom_id', 'unknown')
                    p.tag("rom_id", str(rom_id))
                    
                    for k, v in sensor.items():
                        if k == 'rom_id' or v is None: continue
                        if isinstance(v, (int, float)):
                            p.field(k, float(v))
                    
                    points.append(p)

        if points and self.write_api:
            self.write_api.write(bucket=self.bucket, org=self.org, record=points)