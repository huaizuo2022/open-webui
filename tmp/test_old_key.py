import json
import requests

BASE_URL = 'https://www.aiclaude360.com/v1'
API_KEY = 'sk-eh6pWNDSjlMNmnm3y5r8ybkkWpv7ceBxpaQQfRH3xjWRTELY'
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
}

print('== models ==')
r = requests.get(f'{BASE_URL}/models', headers=HEADERS, timeout=30)
print(r.status_code)
print(r.text[:500])

payload = {
    'model': 'gpt-5.5-chat-latest',
    'messages': [
        {'role': 'user', 'content': 'Reply with exactly: hello'}
    ],
    'stream': False,
}

print('\n== chat ==')
r2 = requests.post(f'{BASE_URL}/chat/completions', headers=HEADERS, json=payload, timeout=60)
print(r2.status_code)
print(r2.text[:1000])

try:
    data = r2.json()
    content = data['choices'][0]['message']['content']
    print('\n== parsed content ==')
    print(content)
except Exception as e:
    print('\n== parse failed ==')
    print(repr(e))
