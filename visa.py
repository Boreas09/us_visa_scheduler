import time
import json
import random
import requests
import configparser
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait as Wait
from selenium.webdriver.common.by import By

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from embassy import *

config = configparser.ConfigParser()
config.read("config.ini")

# Personal Info:
# Account and current appointment info from https://ais.usvisa-info.com
USERNAME = config["PERSONAL_INFO"]["USERNAME"]
PASSWORD = config["PERSONAL_INFO"]["PASSWORD"]
# Find SCHEDULE_ID in re-schedule page link:
# https://ais.usvisa-info.com/en-am/niv/schedule/{SCHEDULE_ID}/appointment
SCHEDULE_ID = config["PERSONAL_INFO"]["SCHEDULE_ID"]
# Target Period:
PRIOD_START = config["PERSONAL_INFO"]["PRIOD_START"]
PRIOD_END = config["PERSONAL_INFO"]["PRIOD_END"]
# Embassy Section:
YOUR_EMBASSY = config["PERSONAL_INFO"]["YOUR_EMBASSY"]
EMBASSY = Embassies[YOUR_EMBASSY][0]
FACILITY_ID = Embassies[YOUR_EMBASSY][1]
REGEX_CONTINUE = Embassies[YOUR_EMBASSY][2]

# Notification:
# Get email notifications via https://sendgrid.com/ (Optional)
SENDGRID_API_KEY = config["NOTIFICATION"]["SENDGRID_API_KEY"]
# Get push notifications via https://pushover.net/ (Optional)
PUSHOVER_TOKEN = config["NOTIFICATION"]["PUSHOVER_TOKEN"]
PUSHOVER_USER = config["NOTIFICATION"]["PUSHOVER_USER"]
# Get push notifications via PERSONAL WEBSITE http://yoursite.com (Optional)
PERSONAL_SITE_USER = config["NOTIFICATION"]["PERSONAL_SITE_USER"]
PERSONAL_SITE_PASS = config["NOTIFICATION"]["PERSONAL_SITE_PASS"]
PUSH_TARGET_EMAIL = config["NOTIFICATION"]["PUSH_TARGET_EMAIL"]
PERSONAL_PUSHER_URL = config["NOTIFICATION"]["PERSONAL_PUSHER_URL"]

# Time Section:
minute = 60
hour = 60 * minute
# Time between steps (interactions with forms)
STEP_TIME = 0.5
# Time between retries/checks for available dates (seconds)
RETRY_TIME_L_BOUND = config["TIME"].getfloat("RETRY_TIME_L_BOUND")
RETRY_TIME_U_BOUND = config["TIME"].getfloat("RETRY_TIME_U_BOUND")
# Cooling down after WORK_LIMIT_TIME hours of work (Avoiding Ban)
WORK_LIMIT_TIME = config["TIME"].getfloat("WORK_LIMIT_TIME")
WORK_COOLDOWN_TIME = config["TIME"].getfloat("WORK_COOLDOWN_TIME")
# Temporary Banned (empty list): wait COOLDOWN_TIME hours
BAN_COOLDOWN_TIME = config["TIME"].getfloat("BAN_COOLDOWN_TIME")

# CHROMEDRIVER
# Details for the script to control Chrome
LOCAL_USE = config["CHROMEDRIVER"].getboolean("LOCAL_USE")
# Optional: HUB_ADDRESS is mandatory only when LOCAL_USE = False
HUB_ADDRESS = config["CHROMEDRIVER"]["HUB_ADDRESS"]

SIGN_IN_LINK = f"https://ais.usvisa-info.com/{EMBASSY}/niv/users/sign_in"
APPOINTMENT_URL = (
    f"https://ais.usvisa-info.com/{EMBASSY}/niv/schedule/{SCHEDULE_ID}/appointment"
)
DATE_URL = f"https://ais.usvisa-info.com/{EMBASSY}/niv/schedule/{SCHEDULE_ID}/appointment/days/{FACILITY_ID}.json?appointments[expedite]=false"
TIME_URL = f"https://ais.usvisa-info.com/{EMBASSY}/niv/schedule/{SCHEDULE_ID}/appointment/times/{FACILITY_ID}.json?date=%s&appointments[expedite]=false"
SIGN_OUT_LINK = f"https://ais.usvisa-info.com/{EMBASSY}/niv/users/sign_out"

JS_SCRIPT = (
    "var req = new XMLHttpRequest();"
    f"req.open('GET', '%s', false);"
    "req.setRequestHeader('Accept', 'application/json, text/javascript, */*; q=0.01');"
    "req.setRequestHeader('X-Requested-With', 'XMLHttpRequest');"
    f"req.setRequestHeader('Cookie', '_yatri_session=%s');"
    "req.send(null);"
    "return req.responseText;"
)


def send_notification(title, msg):
    print(f"Sending notification!")
    if SENDGRID_API_KEY:
        message = Mail(
            from_email=USERNAME, to_emails=USERNAME, subject=msg, html_content=msg
        )
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
        except Exception as e:
            print(e.message)
    if PUSHOVER_TOKEN:
        url = "https://api.pushover.net/1/messages.json"
        data = {"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "message": msg}
        requests.post(url, data)
    if PERSONAL_SITE_USER:
        url = PERSONAL_PUSHER_URL
        data = {
            "title": "VISA - " + str(title),
            "user": PERSONAL_SITE_USER,
            "pass": PERSONAL_SITE_PASS,
            "email": PUSH_TARGET_EMAIL,
            "msg": msg,
        }
        requests.post(url, data)


def auto_action(label, find_by, el_type, action, value, sleep_time=0):
    print("\t" + label + ":", end="")
    # Find Element By
    match find_by.lower():
        case "id":
            item = driver.find_element(By.ID, el_type)
        case "name":
            item = driver.find_element(By.NAME, el_type)
        case "class":
            item = driver.find_element(By.CLASS_NAME, el_type)
        case "xpath":
            item = driver.find_element(By.XPATH, el_type)
        case _:
            return 0
    # Do Action:
    match action.lower():
        case "send":
            item.send_keys(value)
        case "click":
            item.click()
        case _:
            return 0
    print("\t\tCheck!")
    if sleep_time:
        time.sleep(sleep_time)


def start_process():
    # Bypass reCAPTCHA
    driver.get(SIGN_IN_LINK)
    time.sleep(STEP_TIME)
    Wait(driver, 60).until(EC.presence_of_element_located((By.NAME, "commit")))
    auto_action(
        "Click bounce",
        "xpath",
        '//a[@class="down-arrow bounce"]',
        "click",
        "",
        STEP_TIME,
    )
    auto_action("Email", "id", "user_email", "send", USERNAME, STEP_TIME)
    auto_action("Password", "id", "user_password", "send", PASSWORD, STEP_TIME)
    auto_action("Privacy", "class", "icheckbox", "click", "", STEP_TIME)
    auto_action("Enter Panel", "name", "commit", "click", "", STEP_TIME)
    Wait(driver, 60).until(
        EC.presence_of_element_located(
            (By.XPATH, "//a[contains(text(), '" + REGEX_CONTINUE + "')]")
        )
    )
    print("\n\tlogin successful!\n")


def reschedule(date):
    LOG_FILE_NAME = "logs/log_" + str(datetime.now().date()) + ".txt"
    time = get_time(date)
    send_notification("Bulundu!", f"Reschedule! {date}")
    driver.get(APPOINTMENT_URL)
    continueButton = driver.find_element(By.NAME, "commit")
    continueButton.click()
    Wait(driver, 60).until(
        EC.presence_of_element_located(
            (By.ID, "appointments_consulate_appointment_date_input")
        )
    )
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en,tr-TR;q=0.9,tr;q=0.8,en-US;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Content-Type": "application/x-www-form-urlencoded",
        "Cookie": "_yatri_session=" + driver.get_cookie("_yatri_session")["value"],
        "Host": "ais.usvisa-info.com",
        "Origin": "https://ais.usvisa-info.com",
        "Referer": "https://ais.usvisa-info.com/en-tr/niv/schedule/60627961/appointment?applicants%5B%5D=71846579&applicants%5B%5D=71846615&confirmed_limit_message=1&commit=Continue",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }
    data = {
        "authenticity_token": driver.find_element(
            by=By.NAME, value="authenticity_token"
        ).get_attribute("value"),
        "confirmed_limit_message": driver.find_element(
            by=By.NAME, value="confirmed_limit_message"
        ).get_attribute("value"),
        "use_consulate_appointment_capacity": driver.find_element(
            by=By.NAME, value="use_consulate_appointment_capacity"
        ).get_attribute("value"),
        "appointments[consulate_appointment][facility_id]": FACILITY_ID,
        "appointments[consulate_appointment][date]": date,
        "appointments[consulate_appointment][time]": time,
    }
    cookie = {
        "name": "_yatri_session",
        "value": "_yatri_session=" + driver.get_cookie("_yatri_session")["value"],
        "path": "/",
        "domain": "ais.usvisa-info.com",
        "expires": "1969-12-31T23:59:59.000Z",
        "httpOnly": True,
        "secure": True,
        "sameSite": "None",
    }
    send_notification("data!", f"data/payload {data}")
    r = requests.post(APPOINTMENT_URL, headers=headers, data=data, cookies=cookie)
    send_notification("request!", f"request {r.text}")
    info_logger(LOG_FILE_NAME, r.text)
    if r.text.find("Successfully Scheduled") != -1:
        title = "SUCCESS"
        msg = f"Rescheduled Successfully! {date} {time}"
    else:
        title = "FAIL"
        msg = f"Reschedule Failed!!! {date} {time}"
    return [title, msg]


def get_date():
    # Requesting to get the whole available dates
    session = driver.get_cookie("_yatri_session")["value"]
    script = JS_SCRIPT % (str(DATE_URL), session)
    try:
        content = driver.execute_script(script)
        if content:
            return json.loads(content)
        else:
            print("The response is empty.")
            return None
    except json.JSONDecodeError as e:
        print(f"get_date JSON decoding error: {e}")
        return None


def get_time(date):
    time_url = TIME_URL % date
    session = driver.get_cookie("_yatri_session")["value"]
    script = JS_SCRIPT % (str(time_url), session)
    try:
        content = driver.execute_script(script)
        if content:
            data = json.loads(content)
            time = data.get("available_times")[-1]
            print(f"Got time successfully! {date} {time}")
            return time
        else:
            print("The response is empty.")
            return None
    except json.JSONDecodeError as e:
        print(f"get_time JSON decoding error: {e}")
        return None


def get_available_date(dates):
    # Finding The Best Available Date
    for i, date in enumerate(dates):
        if PRIOD_START <= date.get("date") <= PRIOD_END:
            msg = f"\nA Good Available Date: {date.get('date')}\n"
            print(msg)
            info_logger(LOG_FILE_NAME, msg)
            return date.get("date")
    return 0


def info_logger(filename, message):
    with open(filename, "a") as file:
        file.write(message)


def is_logged_in():
    "Check if the user is logged in by looking for a specific element."
    try:
        driver.find_element(By.XPATH, "//a[contains(text(), '" + REGEX_CONTINUE + "')]")
        return True
    except:
        return False


def ensure_logged_in():
    "Ensure that the user is logged in, otherwise log in."
    if not is_logged_in():
        print("Session expired. Logging in again.")
        start_process()
    else:
        print("Already logged in.")


if __name__ == "__main__":
    first_loop = True
    options = webdriver.ChromeOptions()
    if LOCAL_USE:
        driver = webdriver.Chrome(r"chromedriver.exe")
    else:
        driver = webdriver.Remote(command_executor=HUB_ADDRESS, options=options)
    while True:
        LOG_FILE_NAME = "logs/log_" + str(datetime.now().date()) + ".txt"
        if first_loop:
            t0 = time.time()
            total_time = 0
            Req_count = 0
            start_process()
            first_loop = False
        Req_count += 1
        try:
            ensure_logged_in()  # Ensure login status before each request
            msg = (
                "-" * 60
                + f"\nRequest count: {Req_count}, Log time: {datetime.today()}, Start Time: {datetime.fromtimestamp(t0)}\n"
            )
            print(msg)
            info_logger(LOG_FILE_NAME, msg)
            dates = get_date()
            if not dates:
                # Ban Situation
                msg = f"List is empty, Probably banned!\n\tSleep for {BAN_COOLDOWN_TIME} hours!\n"
                print(msg)
                info_logger(LOG_FILE_NAME, msg)
                send_notification("BAN", msg)
                driver.get(SIGN_OUT_LINK)
                time.sleep(BAN_COOLDOWN_TIME * hour)
                first_loop = True
            else:
                # Print Available dates:
                msg = ""
                for d in dates:
                    msg = msg + "%s" % (d.get("date")) + ", "
                msg = "Available dates:\n" + msg
                print(msg)
                info_logger(LOG_FILE_NAME, msg)
                date = get_available_date(dates)
                if date:
                    # A good date to schedule for
                    END_MSG_TITLE, msg = reschedule(date)
                    break
                RETRY_WAIT_TIME = random.randint(RETRY_TIME_L_BOUND, RETRY_TIME_U_BOUND)
                t1 = time.time()
                total_time = t1 - t0
                msg = "\nWorking Time:  ~ {:.2f} minutes".format(total_time / minute)
                print(msg)
                info_logger(LOG_FILE_NAME, msg)
                if total_time > WORK_LIMIT_TIME * hour:
                    # Let program rest a little
                    send_notification(
                        "REST",
                        f"Break-time after {WORK_LIMIT_TIME} hours | Repeated {Req_count} times",
                    )
                    driver.get(SIGN_OUT_LINK)
                    time.sleep(WORK_COOLDOWN_TIME * hour)
                    first_loop = True
                else:
                    msg = "Retry Wait Time: " + str(RETRY_WAIT_TIME) + " seconds"
                    print(msg)
                    info_logger(LOG_FILE_NAME, msg)
                    time.sleep(RETRY_WAIT_TIME)
        except Exception as e:
            # Exception Occurred
            msg = f"Break the loop after exception: {e}\n"
            END_MSG_TITLE = "EXCEPTION"
            break

print(msg)
info_logger(LOG_FILE_NAME, msg)
send_notification(END_MSG_TITLE, msg)
driver.get(SIGN_OUT_LINK)
driver.stop_client()
driver.quit()
