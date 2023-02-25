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
    if PRACTICUM_TOKEN is None:
        logger.critical('PRACTICUM_TOKEN не найден')
        return False
    elif TELEGRAM_TOKEN is None:
        logger.critical('TELEGRAM_TOKEN не найден')
        return False
    elif TELEGRAM_CHAT_ID is None:
        logger.critical('TELEGRAM_CHAT_ID не найден')
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
        if homework_statuses.status_code == HTTPStatus.OK:
            logger.info('Эндпоинт успешно получен')
            return homework_statuses.json()
        else:
            message = (f'Сбой в работе программы:'
                       f' Эндпоинт {ENDPOINT} недоступен.'
                       f'Код ответа API: {homework_statuses.status_code}')
            logger.error(message)
            raise ValueError(message)
    except Exception as error:
        message = f'Что то пошло не так, ошибка при запросе к эндпоинт {error}'
        logger.error(message)
        raise ValueError(message)


def check_response(response):
    """Проверка корректности ответа API Яндекс Практикум."""
    if type(response) == dict:
        if 'homeworks' in response.keys():
            if type(response['homeworks']) == list:
                return response['homeworks']
            else:
                message = 'Ответ API не содержит homeworks в виде списка'
                logger.error(message)
                raise TypeError(message)
        else:
            message = 'Ответ API не содержит ключ homeworks'
            logger.error(message)
            raise TypeError(message)
    else:
        message = 'Ответ API пришел не в виде словаря'
        logger.error(message)
        raise TypeError(message)


def parse_status(homework):
    """Проверка статуса домашнего задания."""
    if 'homework_name' in homework.keys():
        homework_name = homework['homework_name']
        homework_status = homework.get('status')
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            return (f'Изменился статус проверки работы "{homework_name}".'
                    f' {verdict}')
        else:
            message = 'Статус не обнаружен в списке API'
            logger.error(message)
            raise KeyError(message)
    else:
        message = 'Ответ API не содержит ключ homework_name'
        logger.error(message)
        raise KeyError(message)


def main():
    """Основная логика работы бота."""
    if check_tokens():
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
                send_message(bot, message)
            finally:
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
