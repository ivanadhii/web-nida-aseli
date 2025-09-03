#!/usr/bin/env python3
"""
Simple MQTT Worker - Fixed Version
"""

import time
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any
import os

# MQTT import
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    print("Error: paho-mqtt not available")
    MQTT_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'mqtt.gatevans.com')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
DB_PATH = os.environ.get('DB_PATH', '/app/data/sensor_monitoring.db')

MQTT_TOPICS = [
    "arjasari/raspi/sensor/+",
    "arjasari/raspi/resource/+", 
    "arjasari/raspi/all",
    "arjasari/rack/status",
    "arjasari/rack/lamp",
    "arjasari/rack/exhaust",
    "arjasari/rack/dht"
]

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.check_schema()
    
    def check_schema(self):
        """Check if database has measurement_point column"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(pzem_data)")
            columns = [col[1] for col in cursor.fetchall()]
            self.has_measurement_point = 'measurement_point' in columns
            conn.close()
            
            if self.has_measurement_point:
                logger.info("✅ Database supports battery monitoring")
            else:
                logger.warning("⚠️ Database needs migration for battery support")
                
        except Exception as e:
            logger.error(f"Schema check failed: {e}")
            self.has_measurement_point = False
    
    def insert_pzem_data(self, data: Dict[str, Any], measurement_point: str = None):
        """Insert PZEM data safely"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Parse data
            parsed_data = None
            if data.get('status') == 'success' and data.get('raw_registers'):
                try:
                    from pzem_parser import PZEMParser
                    if data.get('device_type') == 'PZEM-016_AC':
                        parsed_data = PZEMParser.parse_pzem016_ac(data['raw_registers'])
                    elif data.get('device_type') == 'PZEM-017_DC':
                        if measurement_point == 'battery_to_inverter':
                            parsed_data = PZEMParser.parse_pzem017_dc_battery(data['raw_registers'])
                        else:
                            parsed_data = PZEMParser.parse_pzem017_dc(data['raw_registers'])
                except Exception as e:
                    logger.error(f"Parse error: {e}")
            
            # Insert based on schema
            if self.has_measurement_point:
                cursor.execute('''
                    INSERT INTO pzem_data (
                        timestamp, device_type, device_path, slave_id,
                        raw_registers, register_count, status, error_message,
                        parsed_data, measurement_point
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data.get('timestamp'),
                    data.get('device_type'),
                    data.get('device_path'),
                    data.get('slave_id'),
                    json.dumps(data.get('raw_registers', [])),
                    data.get('register_count', 0),
                    data.get('status'),
                    data.get('error_message'),
                    json.dumps(parsed_data) if parsed_data else None,
                    measurement_point
                ))
            else:
                cursor.execute('''
                    INSERT INTO pzem_data (
                        timestamp, device_type, device_path, slave_id,
                        raw_registers, register_count, status, error_message,
                        parsed_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data.get('timestamp'),
                    data.get('device_type'),
                    data.get('device_path'),
                    data.get('slave_id'),
                    json.dumps(data.get('raw_registers', [])),
                    data.get('register_count', 0),
                    data.get('status'),
                    data.get('error_message'),
                    json.dumps(parsed_data) if parsed_data else None
                ))
            
            conn.commit()
            logger.info(f"Stored {data.get('device_type')} data: {data.get('status')}")
            
        except Exception as e:
            logger.error(f"Insert PZEM error: {e}")
        finally:
            conn.close()
    
    def insert_dht22_data(self, data: Dict[str, Any]):
        """Insert DHT22 data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO dht22_data (
                    timestamp, temperature, humidity, gpio_pin,
                    library, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('timestamp'),
                data.get('temperature'),
                data.get('humidity'),
                data.get('gpio_pin'),
                data.get('library'),
                data.get('status'),
                data.get('error_message')
            ))
            conn.commit()
            logger.info(f"Stored DHT22: {data.get('temperature')}°C, {data.get('humidity')}%")
        except Exception as e:
            logger.error(f"Insert DHT22 error: {e}")
        finally:
            conn.close()
    
    def insert_system_data(self, data: Dict[str, Any]):
        """Insert system data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO system_data (
                    timestamp, ram_usage_percent, storage_usage_percent,
                    cpu_usage_percent, cpu_temperature, storage_total_gb,
                    storage_used_gb, storage_free_gb, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('timestamp'),
                data.get('ram_usage_percent'),
                data.get('storage_usage_percent'),
                data.get('cpu_usage_percent'),
                data.get('cpu_temperature'),
                data.get('storage_total_gb'),
                data.get('storage_used_gb'),
                data.get('storage_free_gb'),
                data.get('status'),
                data.get('error_message')
            ))
            conn.commit()
            logger.info(f"Stored System: RAM {data.get('ram_usage_percent')}%")
        except Exception as e:
            logger.error(f"Insert System error: {e}")
        finally:
            conn.close()
    
    def insert_rack_data(self, data_type: str, payload: str):
        """Insert RACK data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            timestamp = datetime.now().isoformat()
            
            if data_type == 'dht':
                try:
                    dht_data = json.loads(payload)
                    cursor.execute('''
                        INSERT INTO rack_data (timestamp, data_type, temperature, humidity)
                        VALUES (?, ?, ?, ?)
                    ''', (timestamp, data_type, dht_data.get('temp_c'), dht_data.get('hum_pct')))
                except:
                    return
            else:
                cursor.execute('''
                    INSERT INTO rack_data (timestamp, data_type, status_value)
                    VALUES (?, ?, ?)
                ''', (timestamp, data_type, payload.strip()))
            
            conn.commit()
            logger.info(f"Stored RACK {data_type}: {payload[:50]}")
        except Exception as e:
            logger.error(f"Insert RACK error: {e}")
        finally:
            conn.close()
    
    def insert_raw_message(self, topic: str, payload: str):
        """Insert raw MQTT message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('INSERT INTO mqtt_messages (topic, payload) VALUES (?, ?)', (topic, payload))
            conn.commit()
        except Exception as e:
            logger.error(f"Insert raw message error: {e}")
        finally:
            conn.close()

class MQTTWorker:
    def __init__(self, broker: str, port: int = 1883):
        self.broker = broker
        self.port = port
        self.client = None
        self.connected = False
        self.db_manager = DatabaseManager()
        
        if not MQTT_AVAILABLE:
            logger.error("MQTT library not available")
            return
        
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
        except Exception as e:
            logger.error(f"MQTT client init failed: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker {self.broker}:{self.port}")
            for topic in MQTT_TOPICS:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            self.connected = False
            logger.error(f"MQTT connection failed, code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Handle MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Received from {topic}")
            self.db_manager.insert_raw_message(topic, payload)
            
            # Handle RACK topics
            if topic.startswith('arjasari/rack/'):
                data_type = topic.split('/')[-1]
                self.db_manager.insert_rack_data(data_type, payload)
                return
            
            # Parse JSON
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON from {topic}")
                return
            
            # Route sensor data
            if 'sensor/pzem016_ac' in topic:
                measurement_point = 'inverter_to_load' if self.db_manager.has_measurement_point else None
                self.db_manager.insert_pzem_data(data, measurement_point)
                
            elif 'sensor/pzem017_dc' in topic and 'batt' not in topic:
                measurement_point = 'solar_to_scc' if self.db_manager.has_measurement_point else None
                self.db_manager.insert_pzem_data(data, measurement_point)
                
            elif 'sensor/pzem017_dc_batt' in topic:
                measurement_point = 'battery_to_inverter' if self.db_manager.has_measurement_point else None
                self.db_manager.insert_pzem_data(data, measurement_point)
                
            elif 'sensor/dht22' in topic:
                self.db_manager.insert_dht22_data(data)
                
            elif 'resource/system' in topic:
                self.db_manager.insert_system_data(data)
                
            elif 'all' in topic:
                sensors = data.get('sensors', {})
                
                if 'pzem016_ac' in sensors and sensors['pzem016_ac']:
                    mp = 'inverter_to_load' if self.db_manager.has_measurement_point else None
                    self.db_manager.insert_pzem_data(sensors['pzem016_ac'], mp)
                
                if 'pzem017_dc' in sensors and sensors['pzem017_dc']:
                    mp = 'solar_to_scc' if self.db_manager.has_measurement_point else None
                    self.db_manager.insert_pzem_data(sensors['pzem017_dc'], mp)
                
                if 'pzem017_dc_batt' in sensors and sensors['pzem017_dc_batt']:
                    mp = 'battery_to_inverter' if self.db_manager.has_measurement_point else None
                    self.db_manager.insert_pzem_data(sensors['pzem017_dc_batt'], mp)
                
                if 'dht22' in sensors and sensors['dht22']:
                    self.db_manager.insert_dht22_data(sensors['dht22'])
                
                if 'system' in sensors and sensors['system']:
                    self.db_manager.insert_system_data(sensors['system'])
                
                logger.info("Stored complete sensor data")
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
    
    def connect(self) -> bool:
        if not self.client:
            return False
        
        try:
            logger.info(f"Connecting to {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            
            timeout = time.time() + 10
            while not self.connected and time.time() < timeout:
                time.sleep(0.1)
            
            return self.connected
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def start_monitoring(self):
        if not self.connect():
            logger.error("Failed to connect to MQTT broker")
            return
        
        logger.info("MQTT Worker started")
        
        if self.db_manager.has_measurement_point:
            logger.info("🔋 Battery monitoring enabled")
        else:
            logger.warning("⚠️ Battery monitoring requires database migration")
        
        try:
            while True:
                if not self.connected:
                    logger.warning("Connection lost, reconnecting...")
                    if not self.connect():
                        time.sleep(30)
                        continue
                
                time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("MQTT Worker stopped")
        finally:
            self.disconnect()

def main():
    print("=== Simple MQTT Worker ===")
    print(f"Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Database: {DB_PATH}")
    
    if not MQTT_AVAILABLE:
        print("❌ MQTT library not available")
        return
    
    worker = MQTTWorker(MQTT_BROKER, MQTT_PORT)
    
    try:
        worker.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Program terminated")

if __name__ == "__main__":
    main()  