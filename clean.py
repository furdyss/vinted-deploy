
import sqlite3
conn = sqlite3.connect('/app/data/vinted.db')
c = conn.cursor()
c.execute('DELETE FROM seller_items')
c.execute('UPDATE watched_sellers SET last_item_count=0')
conn.commit()
print('Cleaned')
conn.close()
