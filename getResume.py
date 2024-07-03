import requests
import os

from dotenv import load_dotenv
load_dotenv()

# Ваш access token ОН ВРЕМЕННЫЙ ТО ЕСТЬ ТУТ НАДО ДОРАБОТАТЬ ЧТОБЫ АВТОМАТИЧЕСКИ ВСТАВЛЯЛСЯ НА СЕССИЮ
access_token = os.getenv("ACCESS_TOKEN")

# Настройка заголовков для авторизации
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

# URL для получения информации о резюме
url = 'https://api.hh.ru/resumes/mine'

def get_resumes():
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        resumes = response.json()
        print("Your Resumes:")
        for resume in resumes.get('items', []):
            print(f"ID: {resume['id']}, Title: {resume['title']}, Updated: {resume['updated_at']}")
    else:
        print(f"Failed to get resumes: {response.status_code} - {response.text}")

if __name__ == "__main__":
    get_resumes()
