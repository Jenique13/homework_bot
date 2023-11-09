import logging
import os
import time
from datetime import datetime
from http import HTTPStatus

import requests
from dotenv import load_dotenv
import telegram
from telegram import Bot

from exeptions import TelegramSendError

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
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    if not all(required_env_vars.values()):
        missing_tokens = ([env_key for env_key,
                           env_value in required_env_vars.items()
                           if not env_value])
        for env_key in missing_tokens:
            logger.critical(
                f'Отсутствует переменная окружения или она пуста: {env_key}')
        return False

    return True


def send_message(bot, message):
    """Функция отправки ответов ботом на входящие сообщения."""
    chat_id = TELEGRAM_CHAT_ID
    try:
        bot.send_message(chat_id=chat_id, text=message)
        logger.debug(f'Sent message to chat ID {chat_id}: {message}')
    except telegram.TelegramError as e:
        error_message = f'Ошибка отправки сообщения в Телеграм: {str(e)}'
        logger.error(error_message)
        raise TelegramSendError(error_message)


def get_api_answer(timestamp):
    """Делаем запрос к API-сервису."""
    url = ENDPOINT
    payload = {'from_date': timestamp}
    response = None
    try:
        homework_statuses = requests.get(url, headers=HEADERS, params=payload)
        response = homework_statuses.json()
        logger.debug(f'Response from API: {response}')

        if homework_statuses.status_code != HTTPStatus.OK:
            message = (
                f'Ошибка при запросе к API: {homework_statuses.status_code}')
            send_message(Bot(token=TELEGRAM_TOKEN), message)

    except Exception as e:
        message = str(e)
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
        'Неверная структура данных в ответе API домашки.'
    )


def parse_status(homework):
    """Проверяем статус домашней работы."""
    if isinstance(homework, dict) and 'homework_name' in homework:
        homework_name = homework.get('homework_name', 'Неизвестное имя')
        status = homework.get('status')

        if status is not None and status != 'unknown':
            verdict = HOMEWORK_VERDICTS.get(
                status, f'Неизвестный статус: {status}')
            return (f'Изменился статус проверки работы '
                    f'"{homework_name}". {verdict}')

        raise KeyError(
            f'Недокументированный статус: '
            f'{status if status is not None else "None"}'
        )

    else:
        raise KeyError('homework_name ключ отсутствует в ответе API домашки.')


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
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
