import pickle
import os
import time
import traceback
from datetime import datetime
from dotenv import load_dotenv

import selenium.webdriver.remote.webelement
from selenium.webdriver.remote.webdriver import WebDriver
import asyncio

# https://github.com/python-telegram-bot/python-telegram-bot
import telegram

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

debug = True

load_dotenv()

required_env_vars = [
    'ICMS_TG_API_TOKEN',
    'ICMS_USERNAME',
    'ICMS_PASSWORD',
    'ICMS_TG_ID',
]

missing_vars = [var for var in required_env_vars if os.getenv(var) is None]
if missing_vars:
    raise EnvironmentError(f'Missing required environment variables: {", ".join(missing_vars)}')

icms_url = 'https://campusmanagement.hs-hannover.de/qisserver/pages/cs/sys/portal/hisinoneStartPage.faces'
telegram_api_token = os.getenv('ICMS_TG_API_TOKEN').strip("\"\'") # type: ignore

bot: telegram.Bot

userdata = [
    {
        'username': os.getenv('ICMS_USERNAME').strip("\"\'"), # type: ignore
        'password': os.getenv('ICMS_PASSWORD').strip("\"\'"), # type: ignore
        'telegram_chat_id': os.getenv('ICMS_TG_ID').strip("\"\'"), # type: ignore
        'telegram_subscribers': [],
    },
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

    print(f'sending telegram message to {telegram_chat_id}')
    print(f'msg: {msg}\n')
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
    raise Exception(f'could not locate element with any of the names {names}')

def element_exists(driver: WebDriver, method: str, arg) -> bool:
    return len(driver.find_elements(method, arg)) > 0

def wait_for_element(driver: WebDriver, method: str, arg, timeout: int = 10, condition='clickable') -> selenium.webdriver.remote.webelement.WebElement:
    print(f'waiting for element with method {method} and arg {arg} (condition: {condition})...', end=' ')
    conditions = {
        'present': EC.presence_of_element_located,
        'visible': EC.visibility_of_element_located,
        'clickable': EC.element_to_be_clickable
    }
    try:
        element = WebDriverWait(driver, timeout).until(conditions[condition]((method, arg)))
        WebDriverWait(driver, timeout=timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        print('done')
        return element
    except Exception as e:
        print(f'failed to find element with method {method} and arg {arg} after {timeout}s')
        raise e

def wait_for_login_completion(driver, timeout=10):
    """Wait for login to complete"""
    print('waiting for page to load after login...', end=' ')

    current_url = driver.current_url

    try:
        # Strategy 1: Wait for URL change
        WebDriverWait(driver, timeout=5).until(
            lambda driver: driver.current_url != current_url
        )
    except:
        try:
            # Strategy 2: Wait for login form to disappear
            WebDriverWait(driver, timeout=5).until(
                EC.invisibility_of_element_located((By.XPATH, '//*[@id="loginForm:login"]'))
            )
        except:
            # Strategy 3: Just wait for document ready state
            WebDriverWait(driver, timeout=timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

    print('done')

async def main():
    global bot
    bot = telegram.Bot(telegram_api_token)

    for user in userdata:
        username = user['username']
        password = user['password']
        telegram_chat_id = user['telegram_chat_id']
        filename = f'{os.path.dirname(__file__)}/marks_{username}.pickle'

        print(f'beginning for user: {username}, {"password: " + password if debug else "*"*8} file_path: {filename}, telegram_chat_id: {telegram_chat_id}')

        options = ChromeOptions()
        if debug:
            print('debug: skipping headless mode')
        else:
            options.add_argument('--headless=new')

        driver: webdriver.Chrome | None = None

        try:
            driver = webdriver.Chrome(options=options)
            driver.get(icms_url)

            element_login = wait_for_element(driver, By.XPATH, '//*[@id="loginForm:login"]')
            element_username = driver.find_element(By.XPATH, '//*[@id="asdf"]')
            element_password = driver.find_element(By.XPATH, '//*[@id="fdsa"]')

            element_username.send_keys(username)

            element_password.clear()
            element_password.send_keys(password)
            element_login.click()

            wait_for_login_completion(driver)

            driver.get('https://campusmanagement.hs-hannover.de/qisserver/pages/cs/sys/portal/hisinoneIframePage.faces?id=qis_meine_funktionen&navigationPosition=hisinoneMeinStudium')

            wait_for_element(driver, By.TAG_NAME, 'iframe', condition='present')
            driver.switch_to.frame('frame_iframe_qis_meine_funktionen')

            element_pruefungen = wait_for_element(driver, By.LINK_TEXT, 'Prüfungen')
            print(f'element_pruefungen: {element_pruefungen}')
            element_pruefungen.click()

            element_grades = wait_for_element(driver, By.LINK_TEXT, 'Notenspiegel')
            element_grades.click()

            element_show_icon = wait_for_element(driver, By.XPATH, '//*[@title="Leistungen für Abschluss 90 Master anzeigen"]')
            element_show_icon.click()

            elements = wait_for_element(driver, By.XPATH, '/html/body/div/div[2]/div[2]/form/table[2]/tbody').find_elements(By.XPATH, 'tr')
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
            if driver is not None:
                print(driver.page_source)
            # every day at 0400 we get ERR_CONNECTION_REFUSED, not our fault i guess
            if not datetime.now().strftime('%H:%M') == '04:00':
                await send_telegram_alert(str(e), userdata[0]['telegram_chat_id'])
            if driver is not None:
                driver.close()
            return
        finally:
            if driver is not None:
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
            msg_subscriber_str = 'ICMS-Watcher Update:\n'
            for key in updates.keys():
                msg_str += f'{key}: {updates[key][0]} - {updates[key][1]} - {updates[key][2]}\n'
                msg_subscriber_str += f'{key}\n'
            await send_telegram_alert(msg_str, telegram_chat_id)
            for sub in user['telegram_subscribers']:
                await send_telegram_alert(msg_subscriber_str, sub)
        else:
            print(f'no update occurred for user {username}')


if __name__ == '__main__':
    asyncio.run(main())
