import requests
import json
import time
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Ваш access token
access_token = os.getenv("ACCESS_TOKEN")
# Ваш ID резюме
resume_id = os.getenv("RESUME_ID")

# Файлы для учета вакансий и исключенных работодателей
SENDED_FILE = 'sended'
ACTION_REQUIRED_FILE = 'action_required'
EXCLUDED_EMPLOYERS_FILE = 'excluded_employers'
ALREADY_APPLIED_FILE = 'already_applied'
LETTER_FILE = 'letter.txt'

# Загружаем конфиг
with open("cfg.json", "r", encoding="utf-8") as cfg_file:
    cfg = json.load(cfg_file)

keywords = cfg["keywords"]
excluded_cities = set(cfg["excluded_cities"])
excluded_words = set([w.lower() for w in cfg["excluded_words"]])
area = cfg["area"]
per_page = cfg["per_page"]

# Настройка заголовков для авторизации
headers = {
    'Authorization': f'Bearer {access_token}',
    'Content-Type': 'application/json'
}

def read_ids(file_path):
    """Читает ID из файла и возвращает их в виде множества."""
    if not os.path.exists(file_path):
        return set()
    ids = set()
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            # Ищем кусок вида "id: 123456"
            if "id:" in line:
                try:
                    parts = line.split("id:")[1].strip().split("|")[0]
                    vacancy_id = parts.strip()
                    ids.add(vacancy_id)
                except IndexError:
                    continue
    return ids

def read_letter():
    """Читает сопроводительное письмо из файла."""
    try:
        with open(LETTER_FILE, 'r', encoding='utf-8') as file:
            letter = file.read().strip()
            return letter if letter else None
    except FileNotFoundError:
        print(f"⚠ Letter file '{LETTER_FILE}' not found. Will send applications without letter.")
        return None
    except Exception as e:
        print(f"⚠ Error reading letter file: {e}")
        return None

def write_log(file_path, vacancy_id, name, city, reason=None):
    """Записывает ID + название + город + причину (если есть)."""
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    reason_text = f" | reason: {reason}" if reason else ""
    line = f"{date} | id: {vacancy_id} | {name} | {city}{reason_text}\n"
    with open(file_path, 'a', encoding='utf-8') as file:
        file.write(line)

def search_vacancies(page):
    """Ищет вакансии на указанной странице."""
    url = 'https://api.hh.ru/vacancies'
    params = {
        'text': " OR ".join(keywords),
        'per_page': per_page,
        'page': page,
        'area': area
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to search vacancies: {response.status_code} - {response.text}")
        return None

def apply_to_vacancy(vacancy_id, resume_id, name, city, letter=None):
    """Подает отклик на вакансию."""
    url = f'https://api.hh.ru/negotiations'
    
    # Все параметры отправляем в params, включая message
    params = {
        'vacancy_id': vacancy_id,
        'resume_id': resume_id
    }
    
    # Добавляем письмо в params если есть
    if letter:
        params['message'] = letter
    
    response = requests.post(url, headers=headers, params=params)

    if response.status_code == 201:
        letter_status = "with letter" if letter else "without letter"
        print(f"✓ Successfully applied to vacancy {vacancy_id} ({name} - {city}) [{letter_status}]")
        write_log(SENDED_FILE, vacancy_id, name, city)
        return "success"
    elif response.status_code == 403:
        response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
        
        if 'already_applied' in response.text.lower():
            print(f"⚠ Already applied to vacancy {vacancy_id} ({name} - {city})")
            write_log(ALREADY_APPLIED_FILE, vacancy_id, name, city, reason="already_applied")
            return "already_applied"
        elif 'letter required' in response.text.lower():
            print(f"📝 Letter required for vacancy {vacancy_id} ({name} - {city})")
            write_log(ACTION_REQUIRED_FILE, vacancy_id, name, city, reason="letter_required")
            return "action_required"
        elif 'test_required' in response.text.lower():
            print(f"📋 Test required for vacancy {vacancy_id} ({name} - {city})")
            write_log(ACTION_REQUIRED_FILE, vacancy_id, name, city, reason="test_required")
            return "action_required"
        else:
            print(f"❌ Access denied for vacancy {vacancy_id} ({name} - {city}): {response.text}")
            return "error"
    else:
        print(f"❌ Failed to apply to vacancy {vacancy_id} ({name} - {city}): {response.status_code} - {response.text}")
        return "error"

def contains_excluded_word(text, excluded_words):
    """Проверяет, содержит ли текст какое-либо из исключенных слов."""
    text_lower = text.lower()
    for word in excluded_words:
        if word.lower() in text_lower:
            return True
    return False

def main():
    page = 0
    # Загружаем только excluded_employers
    # Все остальные файлы (sended, action_required, already_applied) используем только для записи
    excluded_employers = read_ids(EXCLUDED_EMPLOYERS_FILE)
    
    # Читаем сопроводительное письмо
    cover_letter = read_letter()
    if cover_letter:
        print(f"📝 Cover letter loaded: {len(cover_letter)} characters")
    else:
        print("📝 No cover letter found, sending applications without letter")
    
    successful_applications = 0
    total_processed = 0
    already_applied_count = 0
    action_required_count = 0
    excluded_by_employer_count = 0
    excluded_by_filter_count = 0

    print("🚀 Starting vacancy application process...")
    
    while True:
        print(f"📖 Processing page {page}...")
        vacancies_data = search_vacancies(page)
        if not vacancies_data or 'items' not in vacancies_data:
            break

        vacancies = vacancies_data['items']
        if not vacancies:
            break
            
        # Отладочная информация о пагинации
        if page == 0:
            print(f"📈 Total vacancies found by API: {vacancies_data.get('found', 'unknown')}")
            print(f"📈 Total pages available: {vacancies_data.get('pages', 'unknown')}")
        
        print(f"📄 Page {page}: processing {len(vacancies)} vacancies")

        for vacancy in vacancies:
            vacancy_id = vacancy.get('id')
            employer_id = vacancy.get('employer', {}).get('id')
            city = vacancy.get('area', {}).get('name', '')
            name = vacancy.get('name', '')

            if not vacancy_id:
                print(f"⚠ Skipping vacancy due to missing ID: {vacancy}")
                continue

            total_processed += 1

            # Проверяем только excluded_employers
            if employer_id in excluded_employers:
                print(f"🚫 Skipping vacancy from excluded employer: {employer_id}")
                excluded_by_employer_count += 1
                continue

            name_lower = name.lower()
            
            # Проверка наличия исключенных слов только в заголовке вакансии
            if city not in excluded_cities and any(kw.lower() in name_lower for kw in keywords):
                if not contains_excluded_word(name_lower, excluded_words):
                    print(f"🎯 Applying to: {name} - {city}")
                    result = apply_to_vacancy(vacancy_id, resume_id, name, city, cover_letter)
                    if result == "success":
                        successful_applications += 1
                    elif result == "already_applied":
                        already_applied_count += 1
                    elif result == "action_required":
                        action_required_count += 1
                    # Пауза между запросами для предотвращения превышения лимитов
                    time.sleep(1)
                else:
                    print(f"🚫 Excluded by word filter: {name}")
                    excluded_by_filter_count += 1
            else:
                print(f"⏭ Excluded by city or keyword filter: {name} - {city}")
                excluded_by_filter_count += 1

        # Проверяем, достигли ли мы последней страницы
        if vacancies_data['pages'] - 1 == page:
            break

        page += 1

    print(f"\n📊 Summary:")
    print(f"Total processed: {total_processed}")
    print(f"✅ Successful applications: {successful_applications}")
    print(f"⚠ Already applied: {already_applied_count}")
    print(f"📝 Action required (letter/test): {action_required_count}")
    print(f"🚫 Excluded by employer: {excluded_by_employer_count}")
    print(f"⏭ Excluded by filters: {excluded_by_filter_count}")
    print(f"✅ Process completed!")

if __name__ == "__main__":
    main()
