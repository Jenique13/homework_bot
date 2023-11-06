import logging
import os
import time
from datetime import datetime
from locale import LC_TIME, setlocale

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

start_date = datetime(2023, 11, 1)
start_timestamp = int(start_date.timestamp())

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

RETRY_PERIOD = 600
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


setlocale(LC_TIME, 'ru_RU.UTF-8')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ya_hw_bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('root')


def check_tokens():
    """Проверка наличия всех необходимых токенов."""
    required_env_vars = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing_tokens = []

    for env_key, env_value in required_env_vars.items():
        if env_value is None or not env_value.strip():
            missing_tokens.append(env_key)
            logger.critical(
                f'Отсутствует переменная окружения или она пуста: {env_key}')

    return not missing_tokens


def send_message(bot, message):
    """Функция отправки ответов ботом на входящие сообщения."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id=chat_id, text=message)
        logger.debug(f"Sent message to chat ID {chat_id}: {message}")
    except Exception as e:
        print(f'Ошибка отправки сообщения в Телеграм: {str(e)}')
        raise


def get_api_answer(timestamp):
    """Делаем запрос к API-сервису."""
    url = ENDPOINT
    payload = {'from_date': timestamp}
    response = None
    try:
        homework_statuses = requests.get(url, headers=HEADERS, params=payload)
        response = homework_statuses.json()
        logger.debug(f'Response from API: {response}')

        if homework_statuses.status_code != 200:
            message = (f'Ошибка при запросе к API'
                       f': {homework_statuses.status_code}')
            print(message)
            send_message(Bot(token=TELEGRAM_TOKEN), message)

        return response
    except Exception as e:
        message = str(e)
        print(message)
        send_message(Bot(token=TELEGRAM_TOKEN), message)
        return response


def check_response(response):
    """Проверяем данные полученные от запроса к API-сервису."""
    if (
        isinstance(response, dict)
        and 'homeworks' in response
        and isinstance(response['homeworks'], list)
    ):
        return True
    raise TypeError(
        "Неверная структура данных в ответе API домашки."
    )


def parse_status(homework):
    """Проверяем статус домашней работы."""
    if isinstance(homework, dict) and 'homework_name' in homework:
        homework_name = homework['homework_name']
        status = homework.get('status', 'unknown')
        verdict = HOMEWORK_VERDICTS.get(
            status, f'Неизвестный статус: {status}')
        if status == 'unknown':
            raise KeyError(f"Недокументированный статус: {status}")
        return (f'Изменился статус проверки работы '
                f'"{homework_name}". {verdict}')
    else:
        raise KeyError("homework_name ключ отсутствует в ответе API домашки.")


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError(
            'Ошибка глобальной переменной: '
            'Отсутствуют необходимые токены.'
        )

    bot = Bot(token=TELEGRAM_TOKEN)

    while True:
        try:
            timestamp = start_timestamp
            response = get_api_answer(timestamp)
            if response and check_response(response):
                data = response['homeworks']
                for homework in data:
                    message = parse_status(homework)
                    if message:
                        send_message(bot, message)

            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            print(message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
