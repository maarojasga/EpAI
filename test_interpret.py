import requests

url = "http://localhost:8001/api/v1/patient-assistant/interpret-labs/1/12342"
print(f"Testing {url}")
response = requests.get(url, headers={"accept": "application/json"})
print("Status Code:", response.status_code)
print("Response JSON:")
print(response.json())
