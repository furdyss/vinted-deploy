
import sqlite3
conn = sqlite3.connect('/app/data/vinted.db')
c = conn.cursor()
# Check if constraint exists
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='seller_items'")
print('Current schema:', c.fetchone()[0])
conn.close()
