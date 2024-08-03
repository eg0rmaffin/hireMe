import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

# Ваш access token
access_token = os.getenv("ACCESS_TOKEN")
# Ваш ID резюме
resume_id = os.getenv("RESUME_ID")

# Файлы для учета вакансий и исключенных работодателей
SENDED_FILE = 'sended'
ACTION_REQUIRED_FILE = 'action_required'
EXCLUDED_EMPLOYERS_FILE = 'excluded_employers'

# Города, исключенные из поиска
excluded_cities = ["Караганда"]

# Слова, исключенные из поиска
excluded_words = ["QA", "Junior", "Ментор", "Android"]

# Настройка заголовков для авторизации
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

def read_ids(file_path):
    """Читает ID из файла и возвращает их в виде множества."""
    if not os.path.exists(file_path):
        return set()
    with open(file_path, 'r') as file:
        ids = file.read().splitlines()
    return set(ids)

def write_id(file_path, vacancy_id):
    """Записывает ID вакансии в файл."""
    with open(file_path, 'a') as file:
        file.write(f"{vacancy_id}\n")

def search_vacancies(page):
    """Ищет вакансии на указанной странице."""
    url = 'https://api.hh.ru/vacancies'
    params = {
        'text': 'Java',
        'per_page': 20,
        'page': page,
        'area': 113  # Код России в HeadHunter
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to search vacancies: {response.status_code} - {response.text}")
        return None

def apply_to_vacancy(vacancy_id, resume_id):
    """Подает отклик на вакансию."""
    url = f'https://api.hh.ru/negotiations?vacancy_id={vacancy_id}&resume_id={resume_id}'
    response = requests.post(url, headers=headers)
    if response.status_code == 201:
        print(f"Successfully applied to vacancy {vacancy_id} with resume {resume_id}")
        write_id(SENDED_FILE, vacancy_id)
    else:
        print(f"Failed to apply to vacancy {vacancy_id}: {response.status_code} - {response.text}")
        if 'Letter required' in response.text:
            write_id(ACTION_REQUIRED_FILE, vacancy_id)

def contains_excluded_word(text, excluded_words):
    """Проверяет, содержит ли текст какое-либо из исключенных слов."""
    text_lower = text.lower()
    for word in excluded_words:
        if word.lower() in text_lower:
            return True
    return False

def main():
    page = 0
    sended_ids = read_ids(SENDED_FILE)
    action_required_ids = read_ids(ACTION_REQUIRED_FILE)
    excluded_employers = read_ids(EXCLUDED_EMPLOYERS_FILE)
    
    while True:
        vacancies_data = search_vacancies(page)
        if not vacancies_data or 'items' not in vacancies_data:
            break

        vacancies = vacancies_data['items']
        if not vacancies:
            break

        for vacancy in vacancies:
            vacancy_id = vacancy.get('id')
            employer_id = vacancy.get('employer', {}).get('id')
            city = vacancy.get('area', {}).get('name', '')

            # Получение названия вакансии
            name = vacancy.get('name', '').lower()

            if not vacancy_id:
                print(f"Skipping vacancy due to missing ID: {vacancy}")
                continue

            if vacancy_id in sended_ids or vacancy_id in action_required_ids:
                print(f"Already processed vacancy with ID: {vacancy_id}")
                continue

            if employer_id in excluded_employers:
                print(f"Skipping vacancy from excluded employer: {employer_id}")
                continue

            # Проверка наличия исключенных слов только в заголовке вакансии
            if city not in excluded_cities and 'java' in name:
                if not contains_excluded_word(name, excluded_words):
                    apply_to_vacancy(vacancy_id, resume_id)
                    # Пауза между запросами для предотвращения превышения лимитов
                    time.sleep(1)
                else:
                    print(f"Excluded by word filter: {name}")
            else:
                print(f"Excluded by city or keyword filter: {name} - {city}")

        # Проверяем, достигли ли мы последней страницы
        if vacancies_data['pages'] - 1 == page:
            break

        page += 1

if __name__ == "__main__":
    main()
