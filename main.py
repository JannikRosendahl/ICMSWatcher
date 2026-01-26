import asyncio
import os
import pickle
from datetime import datetime
from typing import Any

import selenium.webdriver.remote.webelement

# https://github.com/python-telegram-bot/python-telegram-bot
import telegram
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

debug_telegram = False
debug_chrome = True  # set to 'True' to run Chrome in non-headless mode. Note: running in non-headless mode does not work inside Docker containers
debug = debug_telegram or debug_chrome

ensure_student_role = True  # set to 'True' to ensure that the 'Student/-in Hochschule Hannover' role is selected after login. this is needed if the account has multiple roles e.g. student and employee

load_dotenv()

# Grace parameter: number of consecutive failures allowed before notifying the user.
# Default is 3 but can be overridden with the environment variable `ICMS_GRACE`.
try:
    GRACE: int = int(os.getenv("ICMS_GRACE", "3"))
except Exception:
    GRACE = 3

required_env_vars: list[str] = [
    "ICMS_TG_API_TOKEN",
    "ICMS_USERNAME",
    "ICMS_PASSWORD",
    "ICMS_TG_ID",
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(
        f"Missing required environment variables: {', '.join(missing_vars)}"
    )

icms_url = "https://campusmanagement.hs-hannover.de/qisserver/pages/cs/sys/portal/hisinoneStartPage.faces"
telegram_api_token = os.getenv("ICMS_TG_API_TOKEN").strip("\"'")  # type: ignore

bot: telegram.Bot

userdata: dict[str, Any] = {
    "username": os.getenv("ICMS_USERNAME").strip("\"'"),  # type: ignore
    "password": os.getenv("ICMS_PASSWORD").strip("\"'"),  # type: ignore
    "telegram_chat_id": os.getenv("ICMS_TG_ID").strip("\"'"),  # type: ignore
    "telegram_subscribers": [],
}

status_codes: dict[str, str] = {
    "AN": "angemeldet",
    "BE": "bestanden",
    "NB": "nicht bestanden",
    "EN": "endgültig nicht bestanden",
    "AB": "abgemeldet",
    "KR": "Krankmeldung",
    "GR": "genehmigter Rücktritt",
    "NGR": "nicht genehmigter Rücktritt",
    "NE": "nicht erschienen",
    "RT": "abgemeldet über QISPOS",
    "ME": "mündl. Ergänzungsprüfung",
    "VZ": "Verzicht auf Wiederholung",
    "TA": "Täuschungsversuch",
    "PV": "Konto/Modul nicht vollständig",
    "FAE": "fristgerechte Arbeitsabgabe erfolgt",
}

art_codes: dict[str, str] = {
    "GE": "Modul",
    "PL": "Teilmodul",
    "MB": "Modul Bachelorarbeit",
    "MM": "Modul Masterarbeit",
    "AA": "Abschlussarbeit (Bachelor od. Master)",
}


async def send_telegram_alert(msg: str, telegram_chat_id: str) -> None:
    global bot

    print(f"sending telegram message to {telegram_chat_id}")
    print(f"msg: {msg}\n")
    if debug_telegram:
        print("debug: skipping sending telegram message")
        return

    async with bot:
        await bot.send_message(text=msg, chat_id=telegram_chat_id)


async def telegram_debug() -> None:
    global bot
    async with bot:
        print((await bot.get_updates())[0])


def try_find_partial_name(
    driver, names
) -> selenium.webdriver.remote.webelement.WebElement:
    for name in names:
        try:
            element = driver.find_element(By.PARTIAL_LINK_TEXT, name)
            return element
        except Exception:
            pass
    raise Exception(f"could not locate element with any of the names {names}")


def _load_failure_count(path: str) -> int:
    try:
        with open(path, "rb") as infile:
            return pickle.load(infile)
    except Exception:
        return 0


def _save_failure_count(path: str, count: int) -> None:
    try:
        # ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as outfile:
            pickle.dump(count, outfile)
    except Exception:
        # best-effort only; don't let failure-count handling raise
        pass


def element_exists(driver: WebDriver, method: str, arg) -> bool:
    return len(driver.find_elements(method, arg)) > 0


def wait_for_element(
    driver: WebDriver, method: str, arg, timeout: int = 10, condition="clickable"
) -> selenium.webdriver.remote.webelement.WebElement:
    print(
        f"waiting for element with method {method} and arg {arg} (condition: {condition})...",
        end=" ",
    )
    conditions = {
        "present": EC.presence_of_element_located,
        "visible": EC.visibility_of_element_located,
        "clickable": EC.element_to_be_clickable,
    }
    try:
        element = WebDriverWait(driver, timeout).until(
            conditions[condition]((method, arg))
        )
        WebDriverWait(driver, timeout=timeout).until(
            lambda driver: driver.execute_script("return document.readyState")
            == "complete"
        )
        print("done")
        return element
    except Exception as e:
        print(
            f"failed to find element with method {method} and arg {arg} after {timeout}s"
        )
        raise e


def wait_for_login_completion(driver, timeout=10):
    """Wait for login to complete"""
    print("waiting for page to load after login...", end=" ")

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
                EC.invisibility_of_element_located(
                    (By.XPATH, '//*[@id="loginForm:login"]')
                )
            )
        except:
            # Strategy 3: Just wait for document ready state
            WebDriverWait(driver, timeout=timeout).until(
                lambda driver: driver.execute_script("return document.readyState")
                == "complete"
            )

    print("done")


async def main():
    global bot
    bot = telegram.Bot(telegram_api_token)

    marks_dir = os.path.join(os.path.dirname(__file__), "marks")
    os.makedirs(marks_dir, exist_ok=True)

    username: str = userdata["username"]
    password: str = userdata["password"]
    telegram_chat_id = userdata["telegram_chat_id"]
    filename = os.path.join(marks_dir, f"marks_{username}.pickle")

    print(
        f"beginning for user: {username}, file_path: {filename}, telegram_chat_id: {telegram_chat_id}"
    )

    options = ChromeOptions()
    if debug_chrome:
        print("debug: skipping headless mode")
    else:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

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

        # switch to student role
        if ensure_student_role:
            element_role_selector = wait_for_element(
                driver, By.ID, "widgetRender:9:roleSwitcherForm:roles_label"
            )
            element_role_selector.click()

            element_student_role = wait_for_element(
                driver,
                By.XPATH,
                "//li[contains(@class, 'ui-selectonemenu-item') and contains(normalize-space(.), 'Student/-in Hochschule Hannover')]",
                condition="visible",
            )
            element_student_role.click()
            wait_for_login_completion(driver)

        driver.get(
            "https://campusmanagement.hs-hannover.de/qisserver/pages/cs/sys/portal/hisinoneIframePage.faces?id=qis_meine_funktionen&navigationPosition=hisinoneMeinStudium"
        )

        wait_for_element(driver, By.TAG_NAME, "iframe", condition="present")
        driver.switch_to.frame("frame_iframe_qis_meine_funktionen")

        element_pruefungen = wait_for_element(driver, By.LINK_TEXT, "Prüfungen")
        print(f"element_pruefungen: {element_pruefungen}")
        element_pruefungen.click()

        element_grades = wait_for_element(driver, By.LINK_TEXT, "Notenspiegel")
        element_grades.click()

        element_show_icon = wait_for_element(
            driver,
            By.XPATH,
            '//*[@title="Leistungen für Abschluss 90 Master anzeigen"]',
        )
        element_show_icon.click()

        elements = wait_for_element(
            driver, By.XPATH, "/html/body/div/div[2]/div[2]/form/table[2]/tbody"
        ).find_elements(By.XPATH, "tr")
        if len(elements) == 0:
            print("no elements in list??")

        # discard first (table header) and last element (Abschluss)
        elements = elements[1:-1]
        marks = {}

        for element in elements:
            # get all td elements (a row )
            tds = element.find_elements(By.XPATH, "td")
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
        print("failed during webpage navigation, exiting")
        # every day at 04:00 we get ERR_CONNECTION_REFUSED, not our fault i guess
        if datetime.now().strftime("%H:%M") != "04:00":
            # track consecutive failures in a per-user pickle file
            failure_file = os.path.join(marks_dir, f"failure_{username}.pickle")
            count = _load_failure_count(failure_file)
            count += 1
            _save_failure_count(failure_file, count)
            print(f"failure count for {username}: {count} (grace: {GRACE})")
            if count >= GRACE:
                await send_telegram_alert(str(e), userdata["telegram_chat_id"])
                # reset counter after notifying
                _save_failure_count(failure_file, 0)
            else:
                print("within grace period, not sending telegram alert")
        if driver is not None:
            driver.close()
        return
    finally:
        if driver is not None:
            driver.close()

    print(marks)

    # reset failure counter on successful run
    try:
        failure_file = os.path.join(marks_dir, f"failure_{username}.pickle")
        _save_failure_count(failure_file, 0)
    except Exception:
        pass

    # compare to old marks
    updates = {}
    # try to open file with old date
    try:
        with open(filename, "rb") as infile:
            old_marks = pickle.load(infile)
            for key in marks.keys():
                if key not in old_marks or marks[key] != old_marks[key]:
                    updates[key] = marks[key]

    # if no file with old data could be opened, consider all data new
    except OSError:
        print("failed to open file with previous data, considering all data updated")
        for key in marks.keys():
            updates[key] = marks[key]

    # if updates occurred, write data to file
    if len(updates) > 0:
        print(f"the following updates occurred for user {username}:")
        for key in updates:
            print("\t", key, updates[key][0], updates[key][1])
        with open(filename, "wb") as outfile:
            pickle.dump(marks, outfile)
        msg_str = "ICMS-Watcher Update:\n"
        msg_subscriber_str = "ICMS-Watcher Update:\n"
        for key in updates.keys():
            msg_str += (
                f"{key}: {updates[key][0]} - {updates[key][1]} - {updates[key][2]}\n"
            )
            msg_subscriber_str += f"{key}\n"
        await send_telegram_alert(msg_str, telegram_chat_id)
        for sub in userdata["telegram_subscribers"]:
            await send_telegram_alert(msg_subscriber_str, sub)
    else:
        print(f"no update occurred for user {username}")


if __name__ == "__main__":
    asyncio.run(main())
