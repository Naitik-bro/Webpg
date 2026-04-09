import mysql.connector

con = mysql.connector.connect(host="localhost", user="root", password="1234", database="bookstore")
cur = con.cursor()

migrations = [
    ("trending",       "ALTER TABLE books ADD COLUMN trending TINYINT(1) DEFAULT 0"),
    ("category",       "ALTER TABLE books ADD COLUMN category VARCHAR(20) DEFAULT NULL"),
    ("original_price", "ALTER TABLE books ADD COLUMN original_price DECIMAL(10,2) DEFAULT NULL"),
]

for col, sql in migrations:
    cur.execute(f"SHOW COLUMNS FROM books LIKE '{col}'")
    if not cur.fetchone():
        cur.execute(sql)
        print(f"Added '{col}' column")
    else:
        print(f"'{col}' already exists")

con.commit()
con.close()
print("Migration complete!")