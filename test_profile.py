import requests

url = "http://localhost:8001/api/v1/patient-assistant/profile/create"
payload = {
  "clinic_id": 1,
  "patient_id": "PAT_0054",
  "first_name": "John",
  "last_name": "Doe",
  "gender": "M",
  "dob": "1980-05-15"
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.json())
