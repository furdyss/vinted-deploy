
import sqlite3
conn = sqlite3.connect('/app/data/vinted.db')
c = conn.cursor()
c.execute('DROP TABLE IF EXISTS seller_items_backup')
c.execute('ALTER TABLE seller_items RENAME TO seller_items_backup')
c.execute('''CREATE TABLE seller_items (
    id INTEGER NOT NULL PRIMARY KEY,
    vinted_id VARCHAR,
    seller_id INTEGER,
    title VARCHAR,
    price FLOAT,
    previous_price FLOAT,
    photo_url VARCHAR,
    url VARCHAR,
    brand VARCHAR,
    is_available BOOLEAN,
    first_seen DATETIME,
    last_checked DATETIME,
    UNIQUE(vinted_id, seller_id)
)''')
c.execute('CREATE INDEX IF NOT EXISTS idx_si_vinted ON seller_items(vinted_id)')
c.execute('CREATE INDEX IF NOT EXISTS idx_si_seller ON seller_items(seller_id)')
c.execute('DROP TABLE seller_items_backup')
conn.commit()
print('Recreated with UNIQUE constraint')
conn.close()
