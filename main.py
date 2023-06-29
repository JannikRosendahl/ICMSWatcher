import pickle
import os
import time
import traceback

import selenium.webdriver.remote.webelement
import asyncio

# https://github.com/python-telegram-bot/python-telegram-bot
import telegram

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions

debug = True

icms_url = 'https://icms.hs-hannover.de/qisserver/rds?state=user&type=0'
telegram_api_token = 'TELEGRAM_API_TOKEN'

bot: telegram.Bot

userdata = [
    {
        'username': 'USERNAME',
        'password': '',
        'telegram_chat_id': TELEGRAM_CHAT_ID
    },
    {
        'username': '4td-y05-u1',
        'password': '',
        'telegram_chat_id': 1334516177
    }
]

status_codes = {
    'AN': 'angemeldet',
    'BE': 'bestanden',
    'NB': 'nicht bestanden',
    'EN': 'endgültig nicht bestanden',
    'AB': 'abgemeldet',
    'KR': 'Krankmeldung',
    'GR': 'genehmigter Rücktritt',
    'NGR': 'nicht genehmigter Rücktritt',
    'NE': 'nicht erschienen',
    'RT': 'abgemeldet über QISPOS',
    'ME': 'mündl. Ergänzungsprüfung',
    'VZ': 'Verzicht auf Wiederholung',
    'TA': 'Täuschungsversuch',
    'PV': 'Konto/Modul nicht vollständig',
    'FAE': 'fristgerechte Arbeitsabgabe erfolgt',
}

art_codes = {
    'GE': 'Modul',
    'PL': 'Teilmodul',
    'MB': 'Modul Bachelorarbeit',
    'MM': 'Modul Masterarbeit',
    'AA': 'Abschlussarbeit (Bachelor od. Master)',
}


async def send_telegram_alert(msg, telegram_chat_id):
    global bot

    print('sending telegram message')
    if debug:
        print('debug: skipping sending telegram message')
        return

    async with bot:
        await bot.send_message(text=msg, chat_id=telegram_chat_id)


async def telegram_debug():
    global bot
    async with bot:
        print((await bot.get_updates())[0])


def try_find_partial_name(driver, names) -> selenium.webdriver.remote.webelement.WebElement:
    for name in names:
        try:
            element = driver.find_element(By.PARTIAL_LINK_TEXT, name)
            return element
        except Exception as e:
            pass
    raise Exception('could not locate element')


def element_exists(driver: webdriver, method: selenium.webdriver.common.by, arg) -> bool:
    return len(driver.find_elements(method, arg)) > 0


async def main():
    global bot
    bot = telegram.Bot(telegram_api_token)

    for user in userdata:
        username = user['username']
        password = user['password']
        telegram_chat_id = user['telegram_chat_id']
        filename = f'{os.path.dirname(__file__)}/marks_{username}.pickle'

        print(f'beginning for user: {username}, file_path: {filename}, telegram_chat_id: {telegram_chat_id}')

        options = Options()
        # options.add_argument('-headless')

        driver = None

        try:
            driver = webdriver.Firefox(options=options)
            driver.get('https://icms.hs-hannover.de/qisserver/rds?state=user&type=0&category=auth.logout')

            # login
            element_username = driver.find_element(By.XPATH, '//*[@id="asdf"]')
            element_password = driver.find_element(By.XPATH, '//*[@id="fdsa"]')
            element_login = driver.find_element(By.XPATH, '//*[@id="loginForm:login"]')

            element_username.send_keys(username)
            element_password.send_keys(password)
            element_login.click()
            time.sleep(10)

            # navigate
            element_sitemap = driver.find_element(By.XPATH, '/html/body/div/div[2]/div[2]/ol/li[2]/a')
            element_sitemap.click()
            # WebDriverWait(driver, timeout=60).until_not(element_exists(driver, By.XPATH, '//*[@id="loginForm:login"]'))
            WebDriverWait(driver, timeout=60).until(
                expected_conditions.presence_of_element_located((By.PARTIAL_LINK_TEXT, 'Notenspiegel')))

            time.sleep(3)

            # element_grades = driver.find_element(By.XPATH, '/html/body/div/div[6]/div[2]/div/ul[1]/li/ul/li[3]/ul/li[3]/a')
            element_grades = try_find_partial_name(driver, ['Notenspiegel', 'Notenspiegel'.lower(), 'Exams Extract',
                                                            'Exams Extract'.lower()])
            element_grades.click()

            time.sleep(3)

            element_show_icon = driver.find_element(By.XPATH, '/html/body/div/div[6]/div[2]/form/ul/li/a[2]/img')
            element_show_icon.click()

            time.sleep(3)

            # get all tr elements
            elements = driver.find_elements(By.XPATH, '/html/body/div/div[6]/div[2]/form/table[2]/tbody/tr')
            if len(elements) == 0:
                print('no elements in list??')

            # discard first (table header) and last element (Abschluss)
            elements = elements[1:-1]

            marks = {}

            for element in elements:
                # get all td elements (a row )
                tds = element.find_elements(By.XPATH, 'td')
                if len(tds) <= 4:
                    continue

                if int(tds[0].text) < 9999:
                    continue

                name = tds[1].text
                art = tds[2].text
                art = art_codes[art] if art in art_codes else art
                mark = tds[3].text
                status = tds[4].text
                status = status_codes[status] if status in status_codes else status

                marks[name] = mark, art, status
        except Exception as e:
            print('failed during webpage navigation, exiting')
            print(e)
            print(traceback.format_exc())
            print(driver.page_source)
            return
        finally:
            driver.close()

        print(marks)

        # compare to old marks
        updates = {}
        # try to open file with old date
        try:
            with open(filename, 'rb') as infile:
                old_marks = pickle.load(infile)
                for key in marks.keys():
                    if key not in old_marks or marks[key] != old_marks[key]:
                        updates[key] = marks[key]

        # if no file with old data could be opened, consider all data new
        except OSError as e:
            print('failed to open file with previous data, considering all data updated')
            for key in marks.keys():
                updates[key] = marks[key]

        # if updates occurred, write data to file
        if len(updates) > 0:
            print(f'the following updates occurred for user {username}:')
            for key in updates:
                print('\t', key, updates[key][0], updates[key][1])
            with open(filename, 'wb') as outfile:
                pickle.dump(marks, outfile)
            msg_str = 'ICMS-Watcher Update:\n'
            for key in updates.keys():
                msg_str += f'{key}: {updates[key][0]} - {updates[key][1]} - {updates[key][2]}\n'
            await send_telegram_alert(msg_str, telegram_chat_id)
        else:
            print(f'no update occurred for user {username}')


if __name__ == '__main__':
    asyncio.run(main())
