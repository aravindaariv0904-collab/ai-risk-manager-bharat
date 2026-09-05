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
cur.execute("""
    UPDATE auth.users
    SET encrypted_password = crypt('password123', gen_salt('bf')),
        email_confirmed_at = NOW()
    WHERE email = 'aravindaariv0904@gmail.com';
""")
conn.commit()
print("Password updated successfully to 'password123' for aravindaariv0904@gmail.com!")
conn.close()
