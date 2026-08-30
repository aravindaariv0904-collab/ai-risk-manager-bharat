import httpx

client_id = '145fccf6-aced-4af8-911d-d417f3e708eb'
client_secret = '6xGF80IWVECiNPV5QCzVcuBfHrMy66O9'

# In Setu The Bridge, what products are enabled on this account?
# Let's test Setu Sandbox & Production endpoints
urls = [
    ('https://dg-sandbox.setu.co/api/verify/vpa', {'vpa': '7989833615@ybl'}),
    ('https://dg-sandbox.setu.co/api/verify/vpa', {'vpa': '7989833615@paytm'}),
    ('https://dg.setu.co/api/verify/vpa', {'vpa': '7989833615@ybl'}),
]

with httpx.Client(timeout=8.0) as client:
    for url, body in urls:
        for p_id in [client_id, 'dg-sandbox', '']:
            headers = {
                'x-client-id': client_id,
                'x-client-secret': client_secret,
                'x-product-instance-id': p_id,
                'content-type': 'application/json'
            }
            try:
                r = client.post(url, headers=headers, json=body)
                print(url, 'p_id:', p_id, 'Status:', r.status_code, 'Response:', r.text[:150])
            except Exception as e:
                print(url, 'Error:', e)
