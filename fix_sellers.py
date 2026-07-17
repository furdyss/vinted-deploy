import sqlite3
conn = sqlite3.connect('/app/data/vinted.db')
c = conn.cursor()
c.execute("UPDATE watched_sellers SET user_id='255046552' WHERE id=1")
c.execute("UPDATE watched_sellers SET user_id='3161630841' WHERE id=2")
conn.commit()
c.execute('SELECT id, username, user_id FROM watched_sellers')
for row in c.fetchall():
    print(row)
conn.close()
