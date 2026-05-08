import requests

API_URL = "http://your-server:8080/api/v1/generate"
API_KEY = "your-api-key-here"

def ask(prompt):
    response = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"prompt": prompt}
    )

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.json().get('error')}")
        return None

    return response.json()["response"]


answer = ask("What is a thesis statement?")
print(answer)
