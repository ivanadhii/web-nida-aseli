#!/usr/bin/env python3
"""
Flask Web API untuk Sensor Monitoring
Serve data dari SQLite database untuk web dashboard
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
                       status, error_message, parsed_data, received_at
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
                    }
                )

            # PZEM-017 (DC)
            cursor.execute(
                """
                SELECT timestamp, device_type, raw_registers, register_count,
                       status, error_message, parsed_data, received_at
                FROM pzem_data
                WHERE device_type = 'PZEM-017_DC'
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
        except Exception as e:
            logger.error(f"Error get_time_series_data: {e}")
        finally:
            conn.close()
        return result


# --- Inisialisasi API class ---
api = SensorDataAPI(DB_PATH)


# --- Routes ---
@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/latest")
def latest():
    data = api.get_latest_data(limit=int(request.args.get("limit", 20)))
    return jsonify({"success": True, "data": data})


@app.route("/api/summary")
def summary():
    data = api.get_sensor_summary()
    return jsonify({"success": True, "data": data})


@app.route("/api/timeseries/<sensor>")
def timeseries(sensor):
    data = api.get_time_series_data(sensor, hours=int(request.args.get("hours", 6)))
    return jsonify({"success": True, "data": data})


# --- Main ---
if __name__ == "__main__":
    app.run(host=API_HOST, port=API_PORT)
