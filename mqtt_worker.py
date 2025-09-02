#!/usr/bin/env python3
"""
MQTT Worker untuk Subscribe Data Sensor dan Simpan ke Database
Subscribe dari: mqtt.gatevans.com:1883
Topics: arjasari/raspi/sensor/*, arjasari/raspi/resource/*, arjasari/raspi/all, arjasari/rack/*

Updated untuk Docker dengan PZEM parsing dan RACK monitoring
"""

import time
import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import os

# Import untuk MQTT
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    print("Error: paho-mqtt tidak tersedia. Install dengan: pip install paho-mqtt")
    MQTT_AVAILABLE = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'mqtt.gatevans.com')
MQTT_PORT = int(os.environ.get('MQTT_PORT', '1883'))
MQTT_KEEPALIVE = int(os.environ.get('MQTT_KEEPALIVE', '60'))
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
    """Manager untuk SQLite database operations"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table untuk PZEM data (AC & DC) with parsed values
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pzem_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                device_type TEXT NOT NULL,
                device_path TEXT,
                slave_id INTEGER,
                raw_registers TEXT,
                register_count INTEGER,
                status TEXT,
                error_message TEXT,
                parsed_data TEXT,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table untuk DHT22 data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dht22_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                gpio_pin INTEGER,
                library TEXT,
                status TEXT,
                error_message TEXT,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table untuk System Resources
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ram_usage_percent REAL,
                storage_usage_percent REAL,
                cpu_usage_percent REAL,
                cpu_temperature REAL,
                storage_total_gb REAL,
                storage_used_gb REAL,
                storage_free_gb REAL,
                status TEXT,
                error_message TEXT,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # NEW: Table untuk RACK data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rack_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                data_type TEXT NOT NULL,
                status_value TEXT,
                lamp_state TEXT,
                exhaust_state TEXT,
                temperature REAL,
                humidity REAL,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table untuk raw MQTT messages (backup)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mqtt_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Indexes untuk performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pzem_timestamp ON pzem_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dht22_timestamp ON dht22_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rack_timestamp ON rack_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rack_type ON rack_data(data_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mqtt_timestamp ON mqtt_messages(received_at)')
        
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    
    def insert_pzem_data(self, data: Dict[str, Any]):
        """Insert PZEM data ke database with parsed values"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Parse raw data jika ada
        parsed_data = None
        if data.get('status') == 'success' and data.get('raw_registers'):
            try:
                from pzem_parser import PZEMParser
                
                if data.get('device_type') == 'PZEM-016_AC':
                    parsed_data = PZEMParser.parse_pzem016_ac(data['raw_registers'])
                elif data.get('device_type') == 'PZEM-017_DC':
                    parsed_data = PZEMParser.parse_pzem017_dc(data['raw_registers'])
            except Exception as e:
                logger.error(f"Error parsing PZEM data: {e}")
        
        try:
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
            
            if parsed_data and parsed_data.get('status') == 'success':
                device_type = data.get('device_type', 'Unknown')
                if device_type == 'PZEM-016_AC':
                    voltage = parsed_data.get('voltage_v', 0)
                    power = parsed_data.get('power_w', 0)
                    logger.info(f"PZEM-016 AC: {voltage}V, {power}W (Inverter→Load)")
                elif device_type == 'PZEM-017_DC':
                    voltage = parsed_data.get('voltage_v', 0)
                    power = parsed_data.get('power_w', 0)
                    status = parsed_data.get('solar_status', 'Unknown')
                    logger.info(f"PZEM-017 DC: {voltage}V, {power}W ({status})")
            else:
                logger.debug(f"Inserted PZEM data: {data.get('device_type')}")
                
        except Exception as e:
            logger.error(f"Error inserting PZEM data: {e}")
        finally:
            conn.close()
    
    def insert_dht22_data(self, data: Dict[str, Any]):
        """Insert DHT22 data ke database"""
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
            logger.debug(f"Inserted DHT22 data: {data.get('temperature')}°C, {data.get('humidity')}%")
        except Exception as e:
            logger.error(f"Error inserting DHT22 data: {e}")
        finally:
            conn.close()
    
    def insert_system_data(self, data: Dict[str, Any]):
        """Insert System Resources data ke database"""
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
            logger.debug(f"Inserted System data: RAM {data.get('ram_usage_percent')}%")
        except Exception as e:
            logger.error(f"Error inserting System data: {e}")
        finally:
            conn.close()
    
    def insert_rack_data(self, data_type: str, payload: str):
        """Insert RACK data ke database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            timestamp = datetime.now().isoformat()
            
            # Parse berdasarkan data type
            if data_type == 'status':
                # Status: ONLINE/OFFLINE
                cursor.execute('''
                    INSERT INTO rack_data (timestamp, data_type, status_value)
                    VALUES (?, ?, ?)
                ''', (timestamp, data_type, payload.strip()))
                logger.info(f"RACK Status: {payload.strip()}")
                
            elif data_type == 'lamp':
                # Lamp: ON/OFF
                cursor.execute('''
                    INSERT INTO rack_data (timestamp, data_type, lamp_state)
                    VALUES (?, ?, ?)
                ''', (timestamp, data_type, payload.strip()))
                logger.info(f"RACK Lamp: {payload.strip()}")
                
            elif data_type == 'exhaust':
                # Exhaust: ON/OFF
                cursor.execute('''
                    INSERT INTO rack_data (timestamp, data_type, exhaust_state)
                    VALUES (?, ?, ?)
                ''', (timestamp, data_type, payload.strip()))
                logger.info(f"RACK Exhaust: {payload.strip()}")
                
            elif data_type == 'dht':
                # DHT: Parse JSON
                try:
                    dht_data = json.loads(payload)
                    temp = dht_data.get('temp_c')
                    humidity = dht_data.get('hum_pct')
                    
                    cursor.execute('''
                        INSERT INTO rack_data (timestamp, data_type, temperature, humidity)
                        VALUES (?, ?, ?, ?)
                    ''', (timestamp, data_type, temp, humidity))
                    logger.info(f"RACK DHT: {temp}°C, {humidity}%")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing RACK DHT JSON: {e}")
                    return
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Error inserting RACK data: {e}")
        finally:
            conn.close()
    
    def insert_raw_message(self, topic: str, payload: str):
        """Insert raw MQTT message ke database (backup)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO mqtt_messages (topic, payload) VALUES (?, ?)
            ''', (topic, payload))
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting raw message: {e}")
        finally:
            conn.close()
    
    def cleanup_old_data(self, days_to_keep: int = 30):
        """Cleanup data yang lebih lama dari X hari"""
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Cleanup old data
            tables = ['pzem_data', 'dht22_data', 'system_data', 'rack_data', 'mqtt_messages']
            total_deleted = 0
            
            for table in tables:
                if table == 'mqtt_messages':
                    cursor.execute(f'DELETE FROM {table} WHERE received_at < ?', (cutoff_date,))
                else:
                    cursor.execute(f'DELETE FROM {table} WHERE timestamp < ?', (cutoff_date,))
                deleted = cursor.rowcount
                total_deleted += deleted
                logger.info(f"Deleted {deleted} old records from {table}")
            
            conn.commit()
            logger.info(f"Cleanup completed: {total_deleted} total records deleted")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            conn.close()

class MQTTWorker:
    """MQTT Worker untuk subscribe sensor data"""
    
    def __init__(self, broker: str, port: int = 1883):
        self.broker = broker
        self.port = port
        self.client = None
        self.connected = False
        self.db_manager = DatabaseManager()
        
        if not MQTT_AVAILABLE:
            logger.error("MQTT library tidak tersedia")
            return
        
        try:
            self.client = mqtt.Client()
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
        except Exception as e:
            logger.error(f"MQTT client initialization failed: {e}")
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker {self.broker}:{self.port}")
            
            # Subscribe to all topics
            for topic in MQTT_TOPICS:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker, return code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.debug(f"Received message from {topic}")
            
            # Save raw message first (backup)
            self.db_manager.insert_raw_message(topic, payload)
            
            # Handle RACK topics
            if topic.startswith('arjasari/rack/'):
                data_type = topic.split('/')[-1]  # status, lamp, exhaust, dht
                self.db_manager.insert_rack_data(data_type, payload)
                return
            
            # Parse JSON payload untuk sensor data
            try:
                data = json.loads(payload)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from {topic}: {e}")
                return
            
            # Route data berdasarkan topic
            if 'sensor/pzem016_ac' in topic:
                self.db_manager.insert_pzem_data(data)
                logger.info(f"Stored PZEM-016 AC data: {data.get('status')}")
                
            elif 'sensor/pzem017_dc' in topic:
                self.db_manager.insert_pzem_data(data)
                logger.info(f"Stored PZEM-017 DC data: {data.get('status')}")
                
            elif 'sensor/dht22' in topic:
                self.db_manager.insert_dht22_data(data)
                temp = data.get('temperature', -1)
                humidity = data.get('humidity', -1)
                logger.info(f"Stored DHT22 data: {temp}°C, {humidity}%")
                
            elif 'resource/system' in topic:
                self.db_manager.insert_system_data(data)
                ram = data.get('ram_usage_percent', -1)
                logger.info(f"Stored System data: RAM {ram}%")
                
            elif 'all' in topic:
                # Handle complete sensor data dari /all topic
                sensors = data.get('sensors', {})
                
                if 'pzem016_ac' in sensors and sensors['pzem016_ac']:
                    self.db_manager.insert_pzem_data(sensors['pzem016_ac'])
                
                if 'pzem017_dc' in sensors and sensors['pzem017_dc']:
                    self.db_manager.insert_pzem_data(sensors['pzem017_dc'])
                
                if 'dht22' in sensors and sensors['dht22']:
                    self.db_manager.insert_dht22_data(sensors['dht22'])
                
                if 'system' in sensors and sensors['system']:
                    self.db_manager.insert_system_data(sensors['system'])
                
                logger.info("Stored complete sensor data from /all topic")
            
        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")
    
    def connect(self) -> bool:
        """Connect to MQTT broker"""
        if not self.client:
            return False
        
        try:
            logger.info(f"Connecting to MQTT broker {self.broker}:{self.port}")
            self.client.connect(self.broker, self.port, MQTT_KEEPALIVE)
            self.client.loop_start()
            
            # Wait for connection
            timeout = time.time() + 10
            while not self.connected and time.time() < timeout:
                time.sleep(0.1)
            
            return self.connected
        except Exception as e:
            logger.error(f"MQTT connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def start_monitoring(self):
        """Start MQTT monitoring dengan periodic cleanup"""
        if not self.connect():
            logger.error("Failed to connect to MQTT broker")
            return
        
        logger.info("MQTT Worker started successfully")
        logger.info(f"Subscribed topics: {MQTT_TOPICS}")
        logger.info(f"Database: {DB_PATH}")
        
        try:
            # Cleanup old data setiap 1 jam
            last_cleanup = time.time()
            cleanup_interval = 3600  # 1 hour
            
            while True:
                # Check if still connected
                if not self.connected:
                    logger.warning("MQTT connection lost, attempting reconnect...")
                    if not self.connect():
                        logger.error("Reconnection failed, waiting 30s...")
                        time.sleep(30)
                        continue
                
                # Periodic cleanup
                current_time = time.time()
                if current_time - last_cleanup > cleanup_interval:
                    logger.info("Performing periodic database cleanup...")
                    self.db_manager.cleanup_old_data(days_to_keep=30)
                    last_cleanup = current_time
                
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("MQTT Worker stopped by user")
        finally:
            self.disconnect()

def main():
    """Main function"""
    print("=== MQTT Worker for Sensor Monitoring ===")
    print(f"MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"Topics: {MQTT_TOPICS}")
    print(f"Database: {DB_PATH}")
    print()
    
    if not MQTT_AVAILABLE:
        print("❌ MQTT library tidak tersedia!")
        print("Install dengan: pip install paho-mqtt")
        return
    
    # Initialize MQTT Worker
    worker = MQTTWorker(MQTT_BROKER, MQTT_PORT)
    
    # Start monitoring
    try:
        worker.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Program terminated by user")

if __name__ == "__main__":
    main()