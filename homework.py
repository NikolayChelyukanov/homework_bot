import logging
import os
import time

from http import HTTPStatus

import requests
import telegram

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

handler = logging.StreamHandler()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    missing_tokens = []
    if not PRACTICUM_TOKEN:
        missing_tokens.append('PRACTICUM_TOKEN')
        print(missing_tokens)
    if not TELEGRAM_TOKEN:
        missing_tokens.append('TELEGRAM_TOKEN')
        print(missing_tokens)
    if not TELEGRAM_CHAT_ID:
        missing_tokens.append('TELEGRAM_CHAT_ID')
        print(missing_tokens)
    if len(missing_tokens) > 0:
        message = ', '.join(missing_tokens)
        logger.critical(f'Отсутствует:{message}')
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Успешная отправка сообщения.')
    except Exception as error:
        logger.error(f'Не отправляются сообщения в Telegram, {error}')


def get_api_answer(timestamp):
    """Получение ответа API Яндекс Практикум."""
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as e:
        logger.error(f'Ошибка при запросе к эндпоинт: {e}')
        raise ValueError from e
    else:
        if homework_statuses.status_code != HTTPStatus.OK:
            message = (f'Сбой в работе программы: '
                       f' эндпоинт {ENDPOINT} недоступен. '
                       f'Код ответа API: {homework_statuses.status_code}')
            logger.error(message)
            raise ValueError(message)
        logger.info('Эндпоинт успешно получен')
        return homework_statuses.json()


def check_response(response):
    """Проверка корректности ответа API Яндекс Практикум."""
    if not isinstance(response, dict):
        message = 'Ответ API пришел не в виде словаря'
        logger.error(message)
        raise TypeError(message)
    if 'homeworks' not in response:
        message = 'Ответ API не содержит ключ homeworks'
        logger.error(message)
        raise TypeError(message)
    if not isinstance(response['homeworks'], list):
        message = 'Ответ API не содержит homeworks в виде списка'
        logger.error(message)
        raise TypeError(message)
    return response['homeworks']


def parse_status(homework):
    """Проверка статуса домашнего задания."""
    if 'homework_name' not in homework:
        message = 'Ответ API не содержит ключ homework_name'
        logger.error(message)
        raise KeyError(message)
    homework_name = homework['homework_name']
    if 'status' not in homework:
        message = 'Статус не обнаружен в списке API'
        logger.error(message)
        raise KeyError(message)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        message = 'Полученный статус не соответствует ожидаемому'
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return (f'Изменился статус проверки работы "{homework_name}".'
            f' {verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = 'Сбой в работе программы: недоступны переменные окружения'
        logger.error(message)
        raise SystemExit
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    sent_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homeworks = check_response(response)
            if len(homeworks) > 0:
                message = parse_status(homeworks[0])
                if message != sent_message:
                    send_message(bot, message)
                    sent_message = message
            logger.debug('Статус проверки ДЗ не изменился')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != sent_message:
                send_message(bot, message)
                sent_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
