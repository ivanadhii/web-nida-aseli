#!/usr/bin/env python3
"""
PZEM Data Parser
Konversi raw register data menjadi nilai yang readable berdasarkan mapping yang benar

PZEM-016 AC (Inverter ke Load AC):
- Index 0: Voltage (V) ÷ 10
- Index 1-2: Current (A) 32-bit ÷ 1000  
- Index 3-4: Power (W) 32-bit ÷ 10
- Index 5-6: Energy (Wh) 32-bit direct
- Index 7: Frequency (Hz) ÷ 10
- Index 8: Power Factor ÷ 100
- Index 9: Alarm status

PZEM-017 DC (Solar ke SCC):
- Index 0: Voltage (V) × 0.01
- Index 1: Current (A) × 0.01
- Index 2-3: Power (W) 32-bit × 0.1
- Index 4-5: Energy (Wh) 32-bit × 1
- Index 6: Over-voltage alarm
- Index 7: Under-voltage alarm
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class PZEMParser:
    """Parser untuk konversi raw PZEM data menjadi readable values"""
    
    @staticmethod
    def combine_32bit(low: int, high: int) -> int:
        """Combine 2 x 16-bit registers menjadi 32-bit value"""
        return (high << 16) + low
    
    @staticmethod
    def parse_pzem016_ac(raw_registers: List[int]) -> Dict[str, Any]:
        """
        Parse PZEM-016 AC data (Inverter ke Load AC)
        Raw example: [2204, 52, 0, 69, 0, 3763, 0, 500, 60, 0]
        """
        if not raw_registers or len(raw_registers) < 6:
            return {
                'error': 'Insufficient data',
                'raw_registers': raw_registers,
                'register_count': len(raw_registers) if raw_registers else 0,
                'status': 'error'
            }
        
        try:
            result = {
                'device_type': 'PZEM-016_AC',
                'measurement_point': 'Inverter to Load AC',
                'raw_registers': raw_registers,
                'register_count': len(raw_registers)
            }
            
            # Index 0: Voltage (V) ÷ 10
            voltage = raw_registers[0] / 10.0
            result['voltage_v'] = round(voltage, 1)
            
            # Index 1-2: Current (A) 32-bit ÷ 1000
            if len(raw_registers) >= 3:
                current_32bit = PZEMParser.combine_32bit(raw_registers[1], raw_registers[2])
                current = current_32bit / 1000.0
            else:
                current = raw_registers[1] / 1000.0
            result['current_a'] = round(current, 3)
            
            # Index 3-4: Power (W) 32-bit ÷ 10
            if len(raw_registers) >= 5:
                power_32bit = PZEMParser.combine_32bit(raw_registers[3], raw_registers[4])
                power = power_32bit / 10.0
            else:
                power = raw_registers[3] / 10.0 if len(raw_registers) > 3 else 0
            result['power_w'] = round(power, 1)
            
            # Index 5-6: Energy (Wh) 32-bit direct
            if len(raw_registers) >= 7:
                energy_32bit = PZEMParser.combine_32bit(raw_registers[5], raw_registers[6])
                energy_wh = energy_32bit
            else:
                energy_wh = raw_registers[5] if len(raw_registers) > 5 else 0
            result['energy_wh'] = energy_wh
            result['energy_kwh'] = round(energy_wh / 1000.0, 3)
            
            # Index 7: Frequency (Hz) ÷ 10
            if len(raw_registers) > 7:
                frequency = raw_registers[7] / 10.0
                result['frequency_hz'] = round(frequency, 1)
            
            # Index 8: Power Factor ÷ 100
            if len(raw_registers) > 8:
                power_factor = raw_registers[8] / 100.0
                result['power_factor'] = round(power_factor, 2)
            
            # Index 9: Alarm status
            if len(raw_registers) > 9:
                alarm_raw = raw_registers[9]
                result['alarm_status'] = 'ON' if alarm_raw != 0 else 'OFF'
                result['alarm_raw'] = alarm_raw
            
            # Calculated values
            result['apparent_power_va'] = round(voltage * current, 1)
            if len(raw_registers) > 8 and result['power_factor'] > 0:
                result['reactive_power_var'] = round(
                    result['apparent_power_va'] * (1 - result['power_factor']**2)**0.5, 1
                )
            
            result['status'] = 'success'
            result['parsed_at'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing PZEM-016 data: {e}")
            return {
                'error': f'Parse error: {str(e)}',
                'raw_registers': raw_registers,
                'device_type': 'PZEM-016_AC',
                'status': 'error'
            }
    
    @staticmethod
    def parse_pzem017_dc(raw_registers: List[int]) -> Dict[str, Any]:
        """
        Parse PZEM-017 DC data (Solar ke SCC)
        Raw example: [9, 0, 0, 0, 5606, 0, 0, 65535]
        """
        if not raw_registers or len(raw_registers) < 6:
            return {
                'error': 'Insufficient data',
                'raw_registers': raw_registers,
                'register_count': len(raw_registers) if raw_registers else 0,
                'status': 'error'
            }
        
        try:
            result = {
                'device_type': 'PZEM-017_DC',
                'measurement_point': 'Solar to SCC (Solar Charge Controller)',
                'raw_registers': raw_registers,
                'register_count': len(raw_registers)
            }
            
            # Index 0: Voltage (V) × 0.01
            voltage = raw_registers[0] * 0.01
            result['voltage_v'] = round(voltage, 2)
            
            # Index 1: Current (A) × 0.01
            current = raw_registers[1] * 0.01
            result['current_a'] = round(current, 3)
            
            # Index 2-3: Power (W) 32-bit × 0.1
            if len(raw_registers) >= 4:
                power_32bit = PZEMParser.combine_32bit(raw_registers[2], raw_registers[3])
                power = power_32bit * 0.1
            else:
                power = raw_registers[2] * 0.1 if len(raw_registers) > 2 else 0
            result['power_w'] = round(power, 1)
            
            # Index 4-5: Energy (Wh) 32-bit × 1
            if len(raw_registers) >= 6:
                energy_32bit = PZEMParser.combine_32bit(raw_registers[4], raw_registers[5])
                energy_wh = energy_32bit
            else:
                energy_wh = raw_registers[4] if len(raw_registers) > 4 else 0
            result['energy_wh'] = energy_wh
            result['energy_kwh'] = round(energy_wh / 1000.0, 3)
            
            # Index 6: Over-voltage alarm
            if len(raw_registers) > 6:
                ov_alarm_raw = raw_registers[6]
                result['over_voltage_alarm'] = 'ON' if ov_alarm_raw != 0 else 'OFF'
                result['over_voltage_alarm_raw'] = ov_alarm_raw
            
            # Index 7: Under-voltage alarm  
            if len(raw_registers) > 7:
                uv_alarm_raw = raw_registers[7]
                result['under_voltage_alarm'] = 'ON' if uv_alarm_raw == 65535 else 'OFF'
                result['under_voltage_alarm_raw'] = uv_alarm_raw
            
            # Status assessment untuk solar panel
            if voltage < 0.5:
                result['solar_status'] = 'No sunlight / Night'
            elif voltage < 5.0:
                result['solar_status'] = 'Very low sunlight'
            elif voltage < 12.0:
                result['solar_status'] = 'Low sunlight'
            elif voltage < 18.0:
                result['solar_status'] = 'Good sunlight'
            else:
                result['solar_status'] = 'Excellent sunlight'
            
            result['status'] = 'success'
            result['parsed_at'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing PZEM-017 data: {e}")
            return {
                'error': f'Parse error: {str(e)}',
                'raw_registers': raw_registers,
                'device_type': 'PZEM-017_DC',
                'status': 'error'
            }

class EnhancedPZEMAnalyzer:
    """Enhanced analyzer untuk PZEM data dengan insights dan alerts"""
    
    @staticmethod
    def analyze_ac_power_flow(ac_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze AC power flow dari inverter ke load"""
        if ac_data.get('status') != 'success':
            return {'analysis': 'No valid AC data'}
        
        voltage = ac_data.get('voltage_v', 0)
        current = ac_data.get('current_a', 0)
        power = ac_data.get('power_w', 0)
        power_factor = ac_data.get('power_factor', 0)
        
        analysis = {
            'load_status': 'Unknown',
            'voltage_status': 'Unknown',
            'power_factor_status': 'Unknown',
            'alerts': [],
            'insights': []
        }
        
        # Load analysis
        if power < 10:
            analysis['load_status'] = 'Very light load'
        elif power < 50:
            analysis['load_status'] = 'Light load'
        elif power < 200:
            analysis['load_status'] = 'Medium load'
        elif power < 500:
            analysis['load_status'] = 'Heavy load'
        else:
            analysis['load_status'] = 'Very heavy load'
        
        # Voltage analysis
        if voltage < 200:
            analysis['voltage_status'] = 'Low voltage'
            analysis['alerts'].append('⚠️ Low AC voltage detected')
        elif voltage > 240:
            analysis['voltage_status'] = 'High voltage'
            analysis['alerts'].append('⚠️ High AC voltage detected')
        else:
            analysis['voltage_status'] = 'Normal voltage'
        
        # Power factor analysis
        if power_factor < 0.7:
            analysis['power_factor_status'] = 'Poor (inductive load)'
            analysis['insights'].append('💡 Consider power factor correction')
        elif power_factor < 0.9:
            analysis['power_factor_status'] = 'Fair'
        else:
            analysis['power_factor_status'] = 'Good'
        
        # Efficiency insights
        if current > 0:
            efficiency = (power / (voltage * current)) * 100
            analysis['inverter_efficiency'] = round(efficiency, 1)
            
            if efficiency < 80:
                analysis['insights'].append('🔧 Inverter efficiency seems low')
        
        return analysis
    
    @staticmethod
    def analyze_solar_generation(dc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze solar generation dari panel ke SCC"""
        if dc_data.get('status') != 'success':
            return {'analysis': 'No valid DC data'}
        
        voltage = dc_data.get('voltage_v', 0)
        current = dc_data.get('current_a', 0)
        power = dc_data.get('power_w', 0)
        
        analysis = {
            'generation_status': 'Unknown',
            'panel_condition': 'Unknown',
            'alerts': [],
            'insights': []
        }
        
        # Generation analysis
        if power < 1:
            analysis['generation_status'] = 'No generation (night/cloudy)'
        elif power < 10:
            analysis['generation_status'] = 'Very low generation'
        elif power < 50:
            analysis['generation_status'] = 'Low generation'
        elif power < 150:
            analysis['generation_status'] = 'Good generation'
        else:
            analysis['generation_status'] = 'Excellent generation'
        
        # Panel condition analysis
        if voltage > 0.5 and current == 0:
            analysis['panel_condition'] = 'Open circuit (no load)'
        elif voltage < 0.5 and current == 0:
            analysis['panel_condition'] = 'No sunlight'
        elif voltage > 0.5 and current > 0:
            analysis['panel_condition'] = 'Generating power'
        
        # Voltage alerts
        if voltage > 25:
            analysis['alerts'].append('⚠️ High DC voltage - check panel connections')
        
        # Under-voltage alarm check
        if dc_data.get('under_voltage_alarm') == 'ON':
            analysis['alerts'].append('🚨 Under-voltage alarm active')
        
        # Over-voltage alarm check
        if dc_data.get('over_voltage_alarm') == 'ON':
            analysis['alerts'].append('🚨 Over-voltage alarm active')
        
        return analysis
    
    @staticmethod
    def calculate_system_efficiency(ac_data: Dict[str, Any], dc_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall system efficiency"""
        if (ac_data.get('status') != 'success' or 
            dc_data.get('status') != 'success'):
            return {'efficiency': 'Cannot calculate - insufficient data'}
        
        dc_power = dc_data.get('power_w', 0)
        ac_power = ac_data.get('power_w', 0)
        
        if dc_power <= 0:
            return {
                'system_efficiency_percent': 0,
                'status': 'No DC input power',
                'note': 'System not generating'
            }
        
        efficiency = (ac_power / dc_power) * 100
        
        result = {
            'system_efficiency_percent': round(efficiency, 1),
            'dc_input_w': dc_power,
            'ac_output_w': ac_power,
            'power_loss_w': round(dc_power - ac_power, 1)
        }
        
        if efficiency > 90:
            result['efficiency_status'] = 'Excellent'
        elif efficiency > 80:
            result['efficiency_status'] = 'Good'
        elif efficiency > 70:
            result['efficiency_status'] = 'Fair'
        else:
            result['efficiency_status'] = 'Poor'
            result['recommendation'] = 'Check system components for issues'
        
        return result

# Test functions
def test_parser():
    """Test parser dengan data contoh"""
    print("=== Testing PZEM Parser ===")
    
    # Test PZEM-016 AC data
    print("\n1. Testing PZEM-016 AC (Inverter to Load):")
    ac_raw = [2204, 52, 0, 69, 0, 3763, 0, 500, 60, 0]
    ac_parsed = PZEMParser.parse_pzem016_ac(ac_raw)
    print(json.dumps(ac_parsed, indent=2))
    
    # Test PZEM-017 DC data
    print("\n2. Testing PZEM-017 DC (Solar to SCC):")
    dc_raw = [9, 0, 0, 0, 5606, 0, 0, 65535]
    dc_parsed = PZEMParser.parse_pzem017_dc(dc_raw)
    print(json.dumps(dc_parsed, indent=2))
    
    # Test analysis
    print("\n3. Testing Enhanced Analysis:")
    ac_analysis = EnhancedPZEMAnalyzer.analyze_ac_power_flow(ac_parsed)
    dc_analysis = EnhancedPZEMAnalyzer.analyze_solar_generation(dc_parsed)
    system_efficiency = EnhancedPZEMAnalyzer.calculate_system_efficiency(ac_parsed, dc_parsed)
    
    print("\nAC Analysis:", json.dumps(ac_analysis, indent=2))
    print("\nDC Analysis:", json.dumps(dc_analysis, indent=2))
    print("\nSystem Efficiency:", json.dumps(system_efficiency, indent=2))

if __name__ == "__main__":
    test_parser()