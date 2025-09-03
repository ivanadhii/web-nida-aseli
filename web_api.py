#!/usr/bin/env python3
"""
Flask Web API untuk Sensor Monitoring
Serve data dari SQLite database untuk web dashboard
Updated with Battery PZEM-017 DC support
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

from datetime import datetime, timedelta
from typing import Dict, Any, List
import sqlite3
import json

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Config ---
DB_PATH = os.environ.get("DB_PATH", "/app/data/sensor_monitoring.db")
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "5000"))

# --- Pastikan DB ada ---
if not os.path.exists(DB_PATH):
    try:
        import init_db
        logger.info("Database not found, running init_db...")
        init_db.init_database()
    except Exception as e:
        logger.error(f"Failed to init DB: {e}")

# --- Flask App ---
app = Flask(__name__)
CORS(app)


# --- SensorDataAPI class ---
class SensorDataAPI:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def get_latest_data(self, limit: int = 50) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()

        result = {
            "pzem_ac": [],
            "pzem_dc": [],
            "pzem_dc_batt": [],  # NEW: Battery PZEM data
            "dht22": [],
            "system": [],
            "rack": [],
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # PZEM-016 (AC)
            cursor.execute(
                """
                SELECT timestamp, device_type, raw_registers, register_count,
                       status, error_message, parsed_data, received_at, measurement_point
                FROM pzem_data
                WHERE device_type = 'PZEM-016_AC'
                ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            for row in cursor.fetchall():
                try:
                    raw_registers = json.loads(row[2]) if row[2] else []
                    parsed_data = json.loads(row[6]) if row[6] else None
                except Exception:
                    raw_registers, parsed_data = [], None

                result["pzem_ac"].append(
                    {
                        "timestamp": row[0],
                        "device_type": row[1],
                        "raw_registers": raw_registers,
                        "register_count": row[3],
                        "status": row[4],
                        "error_message": row[5],
                        "parsed_data": parsed_data,
                        "received_at": row[7],
                        "measurement_point": row[8],
                    }
                )

            # PZEM-017 (DC Solar)
            cursor.execute(
                """
                SELECT timestamp, device_type, raw_registers, register_count,
                       status, error_message, parsed_data, received_at, measurement_point
                FROM pzem_data
                WHERE device_type = 'PZEM-017_DC' AND 
                      (measurement_point = 'solar_to_scc' OR measurement_point IS NULL)
                ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            for row in cursor.fetchall():
                try:
                    raw_registers = json.loads(row[2]) if row[2] else []
                    parsed_data = json.loads(row[6]) if row[6] else None
                except Exception:
                    raw_registers, parsed_data = [], None

                result["pzem_dc"].append(
                    {
                        "timestamp": row[0],
                        "device_type": row[1],
                        "raw_registers": raw_registers,
                        "register_count": row[3],
                        "status": row[4],
                        "error_message": row[5],
                        "parsed_data": parsed_data,
                        "received_at": row[7],
                        "measurement_point": row[8] or 'solar_to_scc',
                    }
                )

            # PZEM-017 (DC Battery) - NEW
            cursor.execute(
                """
                SELECT timestamp, device_type, raw_registers, register_count,
                       status, error_message, parsed_data, received_at, measurement_point
                FROM pzem_data
                WHERE device_type = 'PZEM-017' AND measurement_point = 'battery_to_inverter'
                ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            for row in cursor.fetchall():
                try:
                    raw_registers = json.loads(row[2]) if row[2] else []
                    parsed_data = json.loads(row[6]) if row[6] else None
                except Exception:
                    raw_registers, parsed_data = [], None

                result["pzem_dc_batt"].append(
                    {
                        "timestamp": row[0],
                        "device_type": row[1],
                        "raw_registers": raw_registers,
                        "register_count": row[3],
                        "status": row[4],
                        "error_message": row[5],
                        "parsed_data": parsed_data,
                        "received_at": row[7],
                        "measurement_point": row[8],
                    }
                )

            # DHT22
            cursor.execute(
                """
                SELECT timestamp, temperature, humidity, gpio_pin, library,
                       status, error_message, received_at
                FROM dht22_data
                ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            for row in cursor.fetchall():
                result["dht22"].append(
                    {
                        "timestamp": row[0],
                        "temperature": row[1],
                        "humidity": row[2],
                        "gpio_pin": row[3],
                        "library": row[4],
                        "status": row[5],
                        "error_message": row[6],
                        "received_at": row[7],
                    }
                )

            # System
            cursor.execute(
                """
                SELECT timestamp, ram_usage_percent, storage_usage_percent,
                       cpu_usage_percent, cpu_temperature, storage_total_gb,
                       storage_used_gb, storage_free_gb, status, error_message, received_at
                FROM system_data
                ORDER BY timestamp DESC LIMIT ?
            """,
                (limit,),
            )
            for row in cursor.fetchall():
                result["system"].append(
                    {
                        "timestamp": row[0],
                        "ram_usage_percent": row[1],
                        "storage_usage_percent": row[2],
                        "cpu_usage_percent": row[3],
                        "cpu_temperature": row[4],
                        "storage_total_gb": row[5],
                        "storage_used_gb": row[6],
                        "storage_free_gb": row[7],
                        "status": row[8],
                        "error_message": row[9],
                        "received_at": row[10],
                    }
                )

            # RACK
            result["rack"] = self.get_latest_rack_status()

        except Exception as e:
            logger.error(f"Error get_latest_data: {e}")
        finally:
            conn.close()

        return result

    def get_latest_rack_status(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        rack_data = {
            "status": "OFFLINE",
            "lamp": "OFF",
            "exhaust": "OFF",
            "temperature": None,
            "humidity": None,
            "last_update": None,
        }

        try:
            cursor.execute(
                """
                SELECT status_value, timestamp FROM rack_data
                WHERE data_type = 'status' AND status_value IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """
            )
            r = cursor.fetchone()
            if r:
                rack_data["status"], rack_data["last_update"] = r[0], r[1]

            cursor.execute(
                """
                SELECT lamp_state FROM rack_data
                WHERE data_type = 'lamp' AND lamp_state IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """
            )
            r = cursor.fetchone()
            if r:
                rack_data["lamp"] = r[0]

            cursor.execute(
                """
                SELECT exhaust_state FROM rack_data
                WHERE data_type = 'exhaust' AND exhaust_state IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """
            )
            r = cursor.fetchone()
            if r:
                rack_data["exhaust"] = r[0]

            cursor.execute(
                """
                SELECT temperature, humidity, timestamp FROM rack_data
                WHERE data_type = 'dht' AND temperature IS NOT NULL AND humidity IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """
            )
            r = cursor.fetchone()
            if r:
                rack_data["temperature"], rack_data["humidity"] = r[0], r[1]
                if not rack_data["last_update"]:
                    rack_data["last_update"] = r[2]

        except Exception as e:
            logger.error(f"Error get_latest_rack_status: {e}")
        finally:
            conn.close()
        return rack_data

    def get_sensor_summary(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        summary = {"total_records": 0}
        try:
            cursor.execute("SELECT COUNT(*) FROM pzem_data")
            pzem_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM dht22_data")
            dht22_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM system_data")
            system_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM rack_data")
            rack_count = cursor.fetchone()[0]
            summary["total_records"] = pzem_count + dht22_count + system_count + rack_count
            
            # Additional summary for battery
            cursor.execute("""
                SELECT COUNT(*) FROM pzem_data 
                WHERE measurement_point = 'battery_to_inverter'
            """)
            battery_count = cursor.fetchone()[0]
            summary["battery_records"] = battery_count
            
            # Summary by device type
            cursor.execute("""
                SELECT device_type, measurement_point, COUNT(*) 
                FROM pzem_data 
                GROUP BY device_type, measurement_point
            """)
            device_summary = cursor.fetchall()
            summary["device_breakdown"] = {}
            for device_type, measurement_point, count in device_summary:
                key = f"{device_type}_{measurement_point}" if measurement_point else device_type
                summary["device_breakdown"][key] = count
            
        except Exception as e:
            logger.error(f"Error get_sensor_summary: {e}")
        finally:
            conn.close()
        return summary

    def get_time_series_data(self, sensor_type: str, hours: int = 24) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cursor = conn.cursor()
        since_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        result = []
        try:
            if sensor_type == "dht22":
                cursor.execute(
                    """
                    SELECT timestamp, temperature, humidity, status
                    FROM dht22_data WHERE timestamp > ?
                    ORDER BY timestamp ASC
                """,
                    (since_time,),
                )
                for r in cursor.fetchall():
                    result.append(
                        {
                            "timestamp": r[0],
                            "temperature": r[1],
                            "humidity": r[2],
                            "status": r[3],
                        }
                    )
            elif sensor_type == "system":
                cursor.execute(
                    """
                    SELECT timestamp, ram_usage_percent, storage_usage_percent,
                           cpu_usage_percent, cpu_temperature, status
                    FROM system_data WHERE timestamp > ?
                    ORDER BY timestamp ASC
                """,
                    (since_time,),
                )
                for r in cursor.fetchall():
                    result.append(
                        {
                            "timestamp": r[0],
                            "ram_usage_percent": r[1],
                            "storage_usage_percent": r[2],
                            "cpu_usage_percent": r[3],
                            "cpu_temperature": r[4],
                            "status": r[5],
                        }
                    )
            elif sensor_type == "rack":
                cursor.execute(
                    """
                    SELECT timestamp, temperature, humidity
                    FROM rack_data
                    WHERE data_type = 'dht' AND timestamp > ?
                    AND temperature IS NOT NULL AND humidity IS NOT NULL
                    ORDER BY timestamp ASC
                """,
                    (since_time,),
                )
                for r in cursor.fetchall():
                    result.append(
                        {
                            "timestamp": r[0],
                            "temperature": r[1],
                            "humidity": r[2],
                            "status": "success",
                        }
                    )
            elif sensor_type == "pzem_ac":
                cursor.execute(
                    """
                    SELECT timestamp, parsed_data
                    FROM pzem_data
                    WHERE device_type = 'PZEM-016_AC' AND timestamp > ?
                    AND status = 'success' AND parsed_data IS NOT NULL
                    ORDER BY timestamp ASC
                """,
                    (since_time,),
                )
                for r in cursor.fetchall():
                    try:
                        parsed = json.loads(r[1])
                        if parsed.get('status') == 'success':
                            result.append({
                                "timestamp": r[0],
                                "voltage_v": parsed.get('voltage_v', 0),
                                "current_a": parsed.get('current_a', 0),
                                "power_w": parsed.get('power_w', 0),
                                "energy_kwh": parsed.get('energy_kwh', 0),
                                "frequency_hz": parsed.get('frequency_hz', 0),
                                "power_factor": parsed.get('power_factor', 0),
                                "status": "success"
                            })
                    except:
                        pass
            elif sensor_type == "pzem_dc":
                cursor.execute(
                    """
                    SELECT timestamp, parsed_data
                    FROM pzem_data
                    WHERE device_type = 'PZEM-017_DC' AND 
                          (measurement_point = 'solar_to_scc' OR measurement_point IS NULL)
                    AND timestamp > ? AND status = 'success' AND parsed_data IS NOT NULL
                    ORDER BY timestamp ASC
                """,
                    (since_time,),
                )
                for r in cursor.fetchall():
                    try:
                        parsed = json.loads(r[1])
                        if parsed.get('status') == 'success':
                            result.append({
                                "timestamp": r[0],
                                "voltage_v": parsed.get('voltage_v', 0),
                                "current_a": parsed.get('current_a', 0),
                                "power_w": parsed.get('power_w', 0),
                                "energy_kwh": parsed.get('energy_kwh', 0),
                                "solar_status": parsed.get('solar_status', 'Unknown'),
                                "status": "success"
                            })
                    except:
                        pass
            elif sensor_type == "pzem_dc_batt":  # NEW: Battery timeseries
                cursor.execute(
                    """
                    SELECT timestamp, parsed_data
                    FROM pzem_data
                    WHERE device_type = 'PZEM-017_DC' AND measurement_point = 'battery_to_inverter' 
                    AND timestamp > ? AND status = 'success' AND parsed_data IS NOT NULL
                    ORDER BY timestamp ASC
                """,
                    (since_time,),
                )
                for r in cursor.fetchall():
                    try:
                        parsed = json.loads(r[1])
                        if parsed.get('status') == 'success':
                            result.append({
                                "timestamp": r[0],
                                "voltage_v": parsed.get('voltage_v', 0),
                                "current_a": parsed.get('current_a', 0),
                                "power_w": parsed.get('power_w', 0),
                                "energy_kwh": parsed.get('energy_kwh', 0),
                                "soc_estimate": parsed.get('soc_estimate', 0),
                                "battery_status": parsed.get('battery_status', 'Unknown'),
                                "flow_direction": parsed.get('flow_direction', 'Unknown'),
                                "flow_status": parsed.get('flow_status', 'Unknown'),
                                "status": "success"
                            })
                    except:
                        pass
        except Exception as e:
            logger.error(f"Error get_time_series_data: {e}")
        finally:
            conn.close()
        return result

    def get_power_flow_data(self) -> Dict[str, Any]:
        """Get latest power flow data for diagram"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        flow_data = {
            "solar_input": {"voltage_v": 0, "current_a": 0, "power_w": 0, "status": "Unknown"},
            "battery_input": {"voltage_v": 0, "current_a": 0, "power_w": 0, "soc_estimate": 0, 
                             "battery_status": "Unknown", "flow_direction": "Unknown"},
            "ac_output": {"voltage_v": 0, "current_a": 0, "power_w": 0, "frequency_hz": 0},
            "system_efficiency": 0,
            "power_balance": {"solar_w": 0, "battery_w": 0, "ac_load_w": 0, "net_w": 0},
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # Get latest solar data
            cursor.execute("""
                SELECT parsed_data FROM pzem_data
                WHERE device_type = 'PZEM-017_DC' AND 
                      (measurement_point = 'solar_to_scc' OR measurement_point IS NULL)
                AND status = 'success' AND parsed_data IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """)
            solar_row = cursor.fetchone()
            if solar_row:
                try:
                    solar_parsed = json.loads(solar_row[0])
                    if solar_parsed.get('status') == 'success':
                        flow_data["solar_input"] = {
                            "voltage_v": solar_parsed.get('voltage_v', 0),
                            "current_a": solar_parsed.get('current_a', 0),
                            "power_w": solar_parsed.get('power_w', 0),
                            "status": solar_parsed.get('solar_status', 'Unknown')
                        }
                except:
                    pass
            
            # Get latest battery data
            cursor.execute("""
                SELECT parsed_data FROM pzem_data
                WHERE device_type = 'PZEM-017_DC' AND measurement_point = 'battery_to_inverter'
                AND status = 'success' AND parsed_data IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """)
            battery_row = cursor.fetchone()
            if battery_row:
                try:
                    battery_parsed = json.loads(battery_row[0])
                    if battery_parsed.get('status') == 'success':
                        flow_data["battery_input"] = {
                            "voltage_v": battery_parsed.get('voltage_v', 0),
                            "current_a": battery_parsed.get('current_a', 0),
                            "power_w": battery_parsed.get('power_w', 0),
                            "soc_estimate": battery_parsed.get('soc_estimate', 0),
                            "battery_status": battery_parsed.get('battery_status', 'Unknown'),
                            "flow_direction": battery_parsed.get('flow_direction', 'Unknown'),
                            "flow_status": battery_parsed.get('flow_status', 'Unknown')
                        }
                except:
                    pass
            
            # Get latest AC data
            cursor.execute("""
                SELECT parsed_data FROM pzem_data
                WHERE device_type = 'PZEM-016_AC'
                AND status = 'success' AND parsed_data IS NOT NULL
                ORDER BY timestamp DESC LIMIT 1
            """)
            ac_row = cursor.fetchone()
            if ac_row:
                try:
                    ac_parsed = json.loads(ac_row[0])
                    if ac_parsed.get('status') == 'success':
                        flow_data["ac_output"] = {
                            "voltage_v": ac_parsed.get('voltage_v', 0),
                            "current_a": ac_parsed.get('current_a', 0),
                            "power_w": ac_parsed.get('power_w', 0),
                            "frequency_hz": ac_parsed.get('frequency_hz', 0),
                            "power_factor": ac_parsed.get('power_factor', 0)
                        }
                except:
                    pass
            
            # Calculate power balance and system efficiency
            solar_power = flow_data["solar_input"]["power_w"]
            battery_power = flow_data["battery_input"]["power_w"]
            ac_power = flow_data["ac_output"]["power_w"]
            
            # Power balance calculation
            flow_data["power_balance"] = {
                "solar_w": solar_power,
                "battery_w": battery_power,  # Positive = discharging, Negative = charging
                "ac_load_w": ac_power,
                "net_w": solar_power + battery_power - ac_power  # Net surplus/deficit
            }
            
            # System efficiency calculation
            total_input = solar_power
            if battery_power > 0:  # Only add if battery is discharging
                total_input += battery_power
                
            if total_input > 0:
                flow_data["system_efficiency"] = round((ac_power / total_input) * 100, 1)
            
            # Additional insights
            flow_data["insights"] = {
                "battery_charging": battery_power < 0,
                "battery_discharging": battery_power > 0,
                "solar_active": solar_power > 1,
                "load_active": ac_power > 5,
                "grid_tie_available": False  # Set to True if grid-tie inverter
            }
            
        except Exception as e:
            logger.error(f"Error get_power_flow_data: {e}")
        finally:
            conn.close()
        
        return flow_data

    def get_analysis_data(self) -> Dict[str, Any]:
        """Get system analysis data"""
        try:
            # Import analyzer
            from pzem_parser import EnhancedPZEMAnalyzer
            
            # Get latest data for analysis
            latest = self.get_latest_data(limit=1)
            
            analysis = {
                "timestamp": datetime.now().isoformat(),
                "alerts": [],
                "insights": [],
                "system_health": "Unknown"
            }
            
            health_score = 100  # Start with perfect score
            
            # Analyze AC power
            if latest["pzem_ac"] and latest["pzem_ac"][0].get("parsed_data"):
                ac_analysis = EnhancedPZEMAnalyzer.analyze_ac_power_flow(
                    latest["pzem_ac"][0]["parsed_data"]
                )
                analysis["ac_analysis"] = ac_analysis
                analysis["alerts"].extend(ac_analysis.get("alerts", []))
                analysis["insights"].extend(ac_analysis.get("insights", []))
                
                # Health score impact
                if "Low voltage" in str(ac_analysis.get("alerts", [])):
                    health_score -= 10
            
            # Analyze DC Solar
            if latest["pzem_dc"] and latest["pzem_dc"][0].get("parsed_data"):
                dc_analysis = EnhancedPZEMAnalyzer.analyze_solar_generation(
                    latest["pzem_dc"][0]["parsed_data"]
                )
                analysis["dc_analysis"] = dc_analysis
                analysis["alerts"].extend(dc_analysis.get("alerts", []))
                analysis["insights"].extend(dc_analysis.get("insights", []))
                
                # Health score impact
                if "alarm" in str(dc_analysis.get("alerts", [])).lower():
                    health_score -= 15
            
            # Analyze Battery - NEW
            if latest["pzem_dc_batt"] and latest["pzem_dc_batt"][0].get("parsed_data"):
                battery_analysis = EnhancedPZEMAnalyzer.analyze_battery_status(
                    latest["pzem_dc_batt"][0]["parsed_data"]
                )
                analysis["battery_analysis"] = battery_analysis
                analysis["alerts"].extend(battery_analysis.get("alerts", []))
                analysis["insights"].extend(battery_analysis.get("insights", []))
                
                # Health score impact
                battery_voltage = latest["pzem_dc_batt"][0]["parsed_data"].get("voltage_v", 12)
                if battery_voltage < 11.5:
                    health_score -= 25
                elif battery_voltage < 12.0:
                    health_score -= 10
            
            # System efficiency
            if (latest["pzem_ac"] and latest["pzem_dc"] and 
                latest["pzem_ac"][0].get("parsed_data") and 
                latest["pzem_dc"][0].get("parsed_data")):
                
                battery_data = None
                if latest["pzem_dc_batt"] and latest["pzem_dc_batt"][0].get("parsed_data"):
                    battery_data = latest["pzem_dc_batt"][0]["parsed_data"]
                
                efficiency_analysis = EnhancedPZEMAnalyzer.calculate_system_efficiency(
                    latest["pzem_ac"][0]["parsed_data"],
                    latest["pzem_dc"][0]["parsed_data"],
                    battery_data
                )
                analysis["system_efficiency"] = efficiency_analysis
                
                # Health score impact
                efficiency = efficiency_analysis.get("system_efficiency_percent", 0)
                if efficiency < 70:
                    health_score -= 20
                elif efficiency < 80:
                    health_score -= 10
            
            # Overall system health
            if health_score >= 90:
                analysis["system_health"] = "Excellent"
            elif health_score >= 80:
                analysis["system_health"] = "Good" 
            elif health_score >= 70:
                analysis["system_health"] = "Fair"
            elif health_score >= 50:
                analysis["system_health"] = "Poor"
            else:
                analysis["system_health"] = "Critical"
            
            analysis["health_score"] = health_score
            
            # Add summary statistics
            analysis["summary"] = {
                "total_alerts": len(analysis["alerts"]),
                "total_insights": len(analysis["insights"]),
                "battery_monitoring": len(latest["pzem_dc_batt"]) > 0,
                "solar_monitoring": len(latest["pzem_dc"]) > 0,
                "ac_monitoring": len(latest["pzem_ac"]) > 0
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error get_analysis_data: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "error": f"Analysis failed: {str(e)}",
                "alerts": [f"⚠️ Analysis system error: {str(e)}"],
                "insights": [],
                "system_health": "Unknown",
                "health_score": 0
            }

    def get_battery_health_report(self) -> Dict[str, Any]:
        """Get detailed battery health report - NEW endpoint"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Get last 24 hours of battery data
            since_time = (datetime.now() - timedelta(hours=24)).isoformat()
            
            cursor.execute("""
                SELECT timestamp, parsed_data FROM pzem_data
                WHERE device_type = 'PZEM-017_DC' AND measurement_point = 'battery_to_inverter'
                AND timestamp > ? AND status = 'success' AND parsed_data IS NOT NULL
                ORDER BY timestamp DESC
            """, (since_time,))
            
            battery_records = []
            for row in cursor.fetchall():
                try:
                    parsed = json.loads(row[1])
                    if parsed.get('status') == 'success':
                        battery_records.append({
                            "timestamp": row[0],
                            "voltage_v": parsed.get('voltage_v', 0),
                            "soc_estimate": parsed.get('soc_estimate', 0),
                            "power_w": parsed.get('power_w', 0),
                            "battery_status": parsed.get('battery_status', 'Unknown')
                        })
                except:
                    continue
            
            if not battery_records:
                return {"error": "No battery data available"}
            
            # Calculate statistics
            voltages = [r["voltage_v"] for r in battery_records]
            socs = [r["soc_estimate"] for r in battery_records]
            powers = [r["power_w"] for r in battery_records]
            
            report = {
                "timestamp": datetime.now().isoformat(),
                "data_points": len(battery_records),
                "time_range_hours": 24,
                "voltage_stats": {
                    "current": voltages[0] if voltages else 0,
                    "min": min(voltages) if voltages else 0,
                    "max": max(voltages) if voltages else 0,
                    "avg": round(sum(voltages) / len(voltages), 2) if voltages else 0
                },
                "soc_stats": {
                    "current": socs[0] if socs else 0,
                    "min": min(socs) if socs else 0,
                    "max": max(socs) if socs else 0,
                    "avg": round(sum(socs) / len(socs), 1) if socs else 0
                },
                "power_stats": {
                    "current": powers[0] if powers else 0,
                    "min": min(powers) if powers else 0,
                    "max": max(powers) if powers else 0,
                    "avg": round(sum(powers) / len(powers), 1) if powers else 0
                },
                "health_assessment": {
                    "voltage_trend": "stable",  # Could be "rising", "falling", "stable"
                    "discharge_cycles": 0,  # Count discharge events
                    "charge_cycles": 0,  # Count charge events
                    "time_at_low_soc": 0,  # Minutes below 20% SOC
                    "recommendations": []
                }
            }
            
            # Analyze trends and health
            if len(voltages) > 1:
                voltage_trend = voltages[0] - voltages[-1]
                if voltage_trend > 0.1:
                    report["health_assessment"]["voltage_trend"] = "rising"
                elif voltage_trend < -0.1:
                    report["health_assessment"]["voltage_trend"] = "falling"
            
            # Count cycles and low SOC time
            discharge_events = 0
            charge_events = 0
            low_soc_minutes = 0
            
            for i, record in enumerate(battery_records):
                if record["power_w"] > 5:  # Discharging
                    if i > 0 and battery_records[i-1]["power_w"] <= 5:
                        discharge_events += 1
                elif record["power_w"] < -5:  # Charging
                    if i > 0 and battery_records[i-1]["power_w"] >= -5:
                        charge_events += 1
                
                if record["soc_estimate"] < 20:
                    low_soc_minutes += 5  # Assuming 5-minute intervals
            
            report["health_assessment"]["discharge_cycles"] = discharge_events
            report["health_assessment"]["charge_cycles"] = charge_events
            report["health_assessment"]["time_at_low_soc"] = low_soc_minutes
            
            # Generate recommendations
            recommendations = []
            if report["voltage_stats"]["min"] < 11.5:
                recommendations.append("⚠️ Battery voltage dropped critically low - check charging system")
            if report["soc_stats"]["min"] < 10:
                recommendations.append("🔋 Battery SOC reached critical levels - risk of damage")
            if low_soc_minutes > 120:  # More than 2 hours at low SOC
                recommendations.append("⏰ Battery spent excessive time at low SOC - consider load management")
            if discharge_events > 10:
                recommendations.append("🔄 High discharge cycle count - monitor battery aging")
            if report["voltage_stats"]["avg"] < 12.2:
                recommendations.append("📊 Average voltage is low - battery may need maintenance")
            
            if not recommendations:
                recommendations.append("✅ Battery health appears normal")
            
            report["health_assessment"]["recommendations"] = recommendations
            
            return report
            
        except Exception as e:
            logger.error(f"Error get_battery_health_report: {e}")
            return {"error": f"Battery health report failed: {str(e)}"}
        finally:
            conn.close()


# --- Inisialisasi API class ---
api = SensorDataAPI(DB_PATH)


# --- Routes ---
@app.route("/api/health")
def health():
    """API Health check with battery support indicator"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check database connectivity
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        
        # Check for battery support
        cursor.execute("PRAGMA table_info(pzem_data)")
        columns = [col[1] for col in cursor.fetchall()]
        battery_support = 'measurement_point' in columns
        
        # Check for recent battery data
        cursor.execute("""
            SELECT COUNT(*) FROM pzem_data 
            WHERE measurement_point = 'battery_to_inverter'
            AND timestamp > datetime('now', '-1 hour')
        """)
        recent_battery_data = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            "status": "ok",
            "battery_support": battery_support,
            "database_tables": table_count,
            "recent_battery_readings": recent_battery_data,
            "endpoints": [
                "/api/latest",
                "/api/summary", 
                "/api/timeseries/<sensor>",
                "/api/power_flow",
                "/api/analysis",
                "/api/battery/health"
            ],
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "battery_support": False
        }), 500


@app.route("/api/latest")
def latest():
    """Get latest sensor data including battery"""
    try:
        limit = int(request.args.get("limit", 20))
        data = api.get_latest_data(limit=limit)
        
        # Add metadata
        metadata = {
            "request_limit": limit,
            "actual_counts": {
                "pzem_ac": len(data.get("pzem_ac", [])),
                "pzem_dc": len(data.get("pzem_dc", [])),
                "pzem_dc_batt": len(data.get("pzem_dc_batt", [])),
                "dht22": len(data.get("dht22", [])),
                "system": len(data.get("system", [])),
                "rack": 1 if data.get("rack") else 0
            }
        }
        
        return jsonify({
            "success": True, 
            "data": data,
            "metadata": metadata
        })
        
    except Exception as e:
        logger.error(f"Error in /api/latest: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/summary")
def summary():
    """Get data summary with battery statistics"""
    try:
        data = api.get_sensor_summary()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Error in /api/summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/timeseries/<sensor>")
def timeseries(sensor):
    """Get time series data for specific sensor"""
    try:
        hours = int(request.args.get("hours", 6))
        
        # Validate sensor type
        valid_sensors = ["dht22", "system", "rack", "pzem_ac", "pzem_dc", "pzem_dc_batt"]
        if sensor not in valid_sensors:
            return jsonify({
                "success": False,
                "error": f"Invalid sensor type. Valid types: {valid_sensors}"
            }), 400
        
        data = api.get_time_series_data(sensor, hours=hours)
        
        return jsonify({
            "success": True, 
            "data": data,
            "metadata": {
                "sensor_type": sensor,
                "hours_requested": hours,
                "data_points": len(data),
                "time_range": f"Last {hours} hours"
            }
        })
        
    except Exception as e:
        logger.error(f"Error in /api/timeseries/{sensor}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/power_flow")
def power_flow():
    """Get power flow data including battery"""
    try:
        data = api.get_power_flow_data()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Error in /api/power_flow: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analysis")
def analysis():
    """Get system analysis including battery health"""
    try:
        data = api.get_analysis_data()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        logger.error(f"Error in /api/analysis: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/battery/health")
def battery_health():
    """Get detailed battery health report - NEW endpoint"""
    try:
        hours = int(request.args.get("hours", 24))  # Default 24 hours
        data = api.get_battery_health_report()
        
        if "error" in data:
            return jsonify({"success": False, "error": data["error"]}), 404
            
        return jsonify({
            "success": True, 
            "data": data,
            "metadata": {
                "report_type": "battery_health",
                "time_range_hours": hours
            }
        })
        
    except Exception as e:
        logger.error(f"Error in /api/battery/health: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/devices")
def devices():
    """Get device status overview - NEW endpoint"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get device status
        devices = {}
        
        # PZEM devices
        cursor.execute("""
            SELECT device_type, measurement_point, COUNT(*) as total_records,
                   MAX(timestamp) as last_reading,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
            FROM pzem_data
            GROUP BY device_type, measurement_point
        """)
        
        for row in cursor.fetchall():
            device_type, measurement_point, total, last_reading, success = row
            key = f"{device_type}_{measurement_point}" if measurement_point else device_type
            
            devices[key] = {
                "device_type": device_type,
                "measurement_point": measurement_point,
                "total_records": total,
                "success_records": success,
                "success_rate": round((success / total) * 100, 1) if total > 0 else 0,
                "last_reading": last_reading,
                "status": "active" if last_reading else "inactive"
            }
        
        # DHT22
        cursor.execute("""
            SELECT COUNT(*) as total, MAX(timestamp) as last_reading,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
            FROM dht22_data
        """)
        row = cursor.fetchone()
        if row and row[0] > 0:
            devices["DHT22"] = {
                "device_type": "DHT22",
                "measurement_point": "environment",
                "total_records": row[0],
                "success_records": row[2],
                "success_rate": round((row[2] / row[0]) * 100, 1),
                "last_reading": row[1],
                "status": "active" if row[1] else "inactive"
            }
        
        # System monitoring
        cursor.execute("""
            SELECT COUNT(*) as total, MAX(timestamp) as last_reading,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success
            FROM system_data
        """)
        row = cursor.fetchone()
        if row and row[0] > 0:
            devices["System"] = {
                "device_type": "System",
                "measurement_point": "resources",
                "total_records": row[0],
                "success_records": row[2],
                "success_rate": round((row[2] / row[0]) * 100, 1),
                "last_reading": row[1],
                "status": "active" if row[1] else "inactive"
            }
        
        conn.close()
        
        return jsonify({
            "success": True,
            "data": {
                "devices": devices,
                "summary": {
                    "total_devices": len(devices),
                    "active_devices": len([d for d in devices.values() if d["status"] == "active"]),
                    "battery_monitoring": "PZEM-017_DC_battery_to_inverter" in devices
                }
            }
        })
        
    except Exception as e:
        logger.error(f"Error in /api/devices: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/export/<data_type>")
def export_data(data_type):
    """Export data in CSV format - NEW endpoint"""
    try:
        hours = int(request.args.get("hours", 24))
        format_type = request.args.get("format", "json")  # json or csv
        
        if data_type not in ["pzem_ac", "pzem_dc", "pzem_dc_batt", "dht22", "system", "rack"]:
            return jsonify({"success": False, "error": "Invalid data type"}), 400
        
        data = api.get_time_series_data(data_type, hours=hours)
        
        if format_type == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if data:
                writer = csv.DictWriter(output, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
            
            csv_content = output.getvalue()
            output.close()
            
            response = app.response_class(
                csv_content,
                mimetype='text/csv',
                headers={"Content-disposition": f"attachment; filename={data_type}_{hours}h.csv"}
            )
            return response
        else:
            return jsonify({
                "success": True,
                "data": data,
                "metadata": {
                    "data_type": data_type,
                    "hours": hours,
                    "record_count": len(data),
                    "format": "json"
                }
            })
        
    except Exception as e:
        logger.error(f"Error in /api/export/{data_type}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# --- Error Handlers ---
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "success": False,
        "error": "Endpoint not found",
        "available_endpoints": [
            "/api/health",
            "/api/latest",
            "/api/summary",
            "/api/timeseries/<sensor>",
            "/api/power_flow",
            "/api/analysis",
            "/api/battery/health",
            "/api/devices",
            "/api/export/<data_type>"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "success": False,
        "error": "Internal server error",
        "message": "Please check server logs for details"
    }), 500


# --- Main ---
if __name__ == "__main__":
    print("🔋 Starting Web API with Battery Support")
    print(f"📊 Database: {DB_PATH}")
    print(f"🌐 Server: {API_HOST}:{API_PORT}")
    print("🔌 Endpoints available:")
    print("   - /api/health (Battery support status)")
    print("   - /api/latest (All sensor data including battery)")
    print("   - /api/timeseries/pzem_dc_batt (Battery time series)")
    print("   - /api/power_flow (Enhanced with battery)")
    print("   - /api/battery/health (Battery health report)")
    print("   - /api/devices (Device status overview)")
    print("   - /api/export/<type> (Data export)")
    
    app.run(host=API_HOST, port=API_PORT, debug=False)