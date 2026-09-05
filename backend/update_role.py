import psycopg2

conn = psycopg2.connect(
    dbname='postgres',
    user='postgres.digktcqwnvkdfyhgkroc',
    password='Aariv@948*##',
    host='aws-0-ap-southeast-1.pooler.supabase.com',
    port=6543,
    connect_timeout=8,
)
cur = conn.cursor()
cur.execute("SELECT id, name, role FROM users WHERE auth_user_id = '618672b0-4a6d-45ee-8f90-a26df8d91192'")
print("User profile in DB:", cur.fetchall())

# Set role to merchant if user wants to use this account as merchant
cur.execute("UPDATE users SET role = 'merchant' WHERE auth_user_id = '618672b0-4a6d-45ee-8f90-a26df8d91192'")
conn.commit()

cur.execute("SELECT id, name, role FROM users WHERE auth_user_id = '618672b0-4a6d-45ee-8f90-a26df8d91192'")
print("Updated profile:", cur.fetchall())
conn.close()
