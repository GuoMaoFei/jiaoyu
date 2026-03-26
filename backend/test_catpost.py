import requests

url = 'http://localhost:8000/api/materials/f9191676-a98b-4c1c-86f6-750b0a2ff175/upload'
files = {'file': open(r'D:\BaiduNetdiskDownload\25中级会计-实务官方教材电子书.pdf', 'rb')}

print('Uploading PDF...')
response = requests.post(url, files=files)
print(f'Status: {response.status_code}')
print(response.text[:500])