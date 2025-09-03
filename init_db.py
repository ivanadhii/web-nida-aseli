#!/usr/bin/env python3
"""
Simple Database Initialization Script
Fixed version to avoid restart loops
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', '/app/data/sensor_monitoring.db')

def init_database():
    """Initialize database with basic schema"""
    
    # Create data directory if not exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    print(f"Initializing database at: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Basic PZEM table with measurement_point
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
                measurement_point TEXT,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # DHT22 table
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
        
        # System table
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
        
        # RACK table
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
        
        # MQTT messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mqtt_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Basic indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pzem_timestamp ON pzem_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pzem_device_type ON pzem_data(device_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pzem_measurement ON pzem_data(measurement_point)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dht22_timestamp ON dht22_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rack_timestamp ON rack_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rack_type ON rack_data(data_type)')
        
        conn.commit()
        conn.close()
        
        # Set permissions
        try:
            os.chmod(DB_PATH, 0o666)
        except:
            pass
        
        print("✅ Database initialized successfully!")
        print("🔋 Battery monitoring support enabled")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()