import requests
s = requests.Session()
r = s.post('http://localhost:8000/api/auth/login', data={'username':'testuser','password':'testpassword123'})
token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

print('Brainstorm test...')
r2 = s.post('http://localhost:8000/api/workflow/brainstorm', json={
    'user_intent': '主角觉醒时间回溯能力',
    'chapter_num': 1,
    'book_id': '98f625cb-f9e5-4e99-b293-2bdbc149967f'
}, headers=headers, timeout=120)
print('Status:', r2.status_code)
import json
data = r2.json()
if isinstance(data, list):
    print(f'{len(data)} options:')
    for opt in data[:3]:
        print(f'  {opt.get("option","?")}: {opt.get("title","?")} - {opt.get("desc","")[:60]}')
else:
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
