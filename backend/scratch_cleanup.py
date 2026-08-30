import psycopg2
import os

conn = psycopg2.connect('postgresql://postgres:Aariv%40948*%23%23@db.digktcqwnvkdfyhgkroc.supabase.co:5432/postgres')
cur = conn.cursor()

cur.execute("SELECT id, business_name, risk_profile FROM merchants")
rows = cur.fetchall()
print("Merchants before cleanup:")
for r in rows:
    print(r[0], r[1])

# Delete all mock merchants created by testing
cur.execute("""
    DELETE FROM merchants 
    WHERE business_name LIKE 'SANJAY %'
       OR business_name LIKE 'KIRAN %'
       OR business_name LIKE 'ANIL %'
       OR business_name LIKE 'DEEPAK %'
       OR business_name LIKE 'POOJA %'
       OR business_name LIKE 'VIKRAM %'
       OR business_name LIKE 'SUNIL %'
       OR business_name LIKE 'RAJESH %'
       OR business_name LIKE 'PRAVEEN %'
       OR business_name LIKE 'ARJUN %'
       OR business_name LIKE 'Recipient (%'
""")
conn.commit()

cur.execute("SELECT id, business_name FROM merchants")
print("\nMerchants after cleanup:")
for r in cur.fetchall():
    print(r[0], r[1])
