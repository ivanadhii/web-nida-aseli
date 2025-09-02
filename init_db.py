#!/usr/bin/env python3
"""
Database Initialization Script for Docker
Creates SQLite database with proper schema for sensor monitoring including RACK
"""

import sqlite3
import os
import sys
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', '/app/data/sensor_monitoring.db')

def init_database():
    """Initialize database with proper schema"""
    
    # Create data directory if not exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    print(f"Initializing database at: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pzem_device_type ON pzem_data(device_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dht22_timestamp ON dht22_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_system_timestamp ON system_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rack_timestamp ON rack_data(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_rack_type ON rack_data(data_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mqtt_timestamp ON mqtt_messages(received_at)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_mqtt_topic ON mqtt_messages(topic)')
        
        # Insert initial test data (optional)
        cursor.execute('''
            INSERT OR IGNORE INTO mqtt_messages (topic, payload) 
            VALUES ('system/init', ?)
        ''', (f'{{"message": "Database initialized with RACK support", "timestamp": "{datetime.now().isoformat()}"}}',))
        
        conn.commit()
        
        # Verify tables created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("✅ Database initialized successfully!")
        print(f"📊 Created tables: {[table[0] for table in tables]}")
        
        # Set proper permissions
        os.chmod(DB_PATH, 0o666)
        
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)
    finally:
        conn.close()

def verify_database():
    """Verify database is working properly"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Test database connectivity
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        
        if table_count >= 5:  # Updated to 5 tables (including rack_data)
            print(f"✅ Database verification passed ({table_count} tables)")
        else:
            print(f"⚠️ Database verification warning: only {table_count} tables found")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Starting database initialization...")
    
    # Initialize database
    init_database()
    
    # Verify database
    if verify_database():
        print("🎉 Database setup completed successfully!")
        sys.exit(0)
    else:
        print("💥 Database setup failed!")
        sys.exit(1)