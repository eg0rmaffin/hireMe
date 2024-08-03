import requests
import os
from urllib.parse import urlparse

# Загружаем переменные среды из .env файла
from dotenv import load_dotenv
load_dotenv()

# Ваш access token
access_token = os.getenv("ACCESS_TOKEN")

# Файлы для URL и исключенных работодателей
EMPLOYER_URLS_FILE = 'employerURLs'
EXCLUDED_EMPLOYERS_FILE = 'excluded_employers'

# Настройка заголовков для авторизации
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

def get_employer_id_from_url(url):
    """Извлекает ID работодателя из URL компании на HeadHunter через API."""
    parsed_url = urlparse(url)
    
    # Проверяем, является ли URL валидным и относится ли к hh.ru
    if 'hh.ru' not in parsed_url.netloc:
        print("Invalid URL or not an hh.ru domain.")
        return None
    
    # Пример URL: https://hh.ru/employer/123456
    path_parts = parsed_url.path.split('/')
    if 'employer' in path_parts:
        employer_id = path_parts[path_parts.index('employer') + 1]
        return employer_id
    else:
        print("Employer ID not found in the URL.")
        return None

def get_employer_name(employer_id):
    """Получает имя работодателя по его ID через API."""
    url = f'https://api.hh.ru/employers/{employer_id}'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get('name')
    else:
        print(f"Failed to get employer information: {response.status_code} - {response.text}")
        return None

def read_ids(file_path):
    """Читает ID из файла и возвращает их в виде множества."""
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r') as file:
        ids = file.read().splitlines()
    return set(ids)

def write_employer_id(file_path, employer_id):
    """Записывает ID работодателя в файл."""
    with open(file_path, 'a') as file:
        file.write(f"{employer_id}\n")

def main():
    # Читаем уже исключенные ID работодателей
    excluded_ids = read_ids(EXCLUDED_EMPLOYERS_FILE)
    
    # Читаем URL работодателей из файла
    if not os.path.exists(EMPLOYER_URLS_FILE):
        print(f"File {EMPLOYER_URLS_FILE} not found.")
        return
    
    with open(EMPLOYER_URLS_FILE, 'r') as file:
        urls = file.read().splitlines()
    
    for url in urls:
        employer_id = get_employer_id_from_url(url)
        if employer_id:
            if employer_id not in excluded_ids:
                employer_name = get_employer_name(employer_id)
                if employer_name:
                    write_employer_id(EXCLUDED_EMPLOYERS_FILE, employer_id)
                    excluded_ids.add(employer_id)
                    print(f"ID работодателя {employer_id} ({employer_name}) добавлен в список исключений.")
                else:
                    print(f"Не удалось получить информацию о работодателе по URL: {url}")
            else:
                print(f"ID работодателя {employer_id} уже находится в списке исключений.")
        else:
            print(f"Не удалось извлечь ID работодателя из URL: {url}")

if __name__ == "__main__":
    main()
