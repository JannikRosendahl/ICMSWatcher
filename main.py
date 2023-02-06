import pickle

import telegram
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options

icms_url = 'https://icms.hs-hannover.de/qisserver/rds?state=user&type=0'
telegram_api_token = 'TELEGRAM_API_TOKEN'

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


async def send_telegram_alert(msg, telegram_chat_id):
    bot = telegram.Bot(telegram_api_token)
    async with bot:
        await bot.send_message(text=msg, chat_id=telegram_chat_id)


async def telegram_debug():
    bot = telegram.Bot(telegram_api_token)
    async with bot:
        print((await bot.get_updates())[0])


async def main():
    for user in userdata:
        username = user['username']
        password = user['password']
        telegram_chat_id = user['telegram_chat_id']
        filename = f'marks_{username}.pickle'

        print(f'beginning for user: {username}')

        options = Options()
        options.add_argument('-headless')
        driver = webdriver.Firefox(options=options)
        driver.get(icms_url)

        # login
        driver.find_element(By.CLASS_NAME, 'loginuser').send_keys(username)
        driver.find_element(By.CLASS_NAME, 'loginpass').send_keys(password)

        driver.find_element(By.ID, 'loginForm:login').click()

        # nav to notenspiegel
        driver.find_element(By.LINK_TEXT, 'Prüfungen').click()
        driver.find_element(By.LINK_TEXT, 'Notenspiegel').click()

        driver.find_element(By.LINK_TEXT, 'Abschluss 84 Bachelor').click()
        driver.find_element(By.XPATH, '/html/body/div/div[6]/div[2]/form/ul/li/ul/li/a[1]').click()

        # get all tr elements
        elements = driver.find_elements(By.XPATH, '/html/body/div/div[6]/div[2]/form/table[2]/tbody/tr')
        # discard first (table header) and last element (Abschluss)
        elements = elements[1:-1]

        marks = {}

        for element in elements:
            # get all td elements (a row )
            tds = element.find_elements(By.XPATH, 'td')
            # filter meta modules and part modules (GE == Modul)
            if int(tds[0].text) < 99999 or tds[2].text != 'GE':
                continue

            name = tds[1].text
            mark = tds[3].text
            status = tds[4].text

            marks[name] = mark, status

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
                print(key, updates[key][0], updates[key][1])
            with open(filename, 'wb') as outfile:
                pickle.dump(marks, outfile)
            msg_str = 'ICMS-Watcher Update\n'
            for key in updates.keys():
                msg_str += f'{key}: {updates[key][0]} - {updates[key][1]}\n'
            await send_telegram_alert(msg_str, telegram_chat_id)
        else:
            print(f'no update occurred for user {username}')


if __name__ == '__main__':
    asyncio.run(main())
