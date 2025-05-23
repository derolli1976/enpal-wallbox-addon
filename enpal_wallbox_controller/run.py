import json
import logging
import os
import re
import traceback

from flask import Flask, jsonify
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

DEFAULT_LOG_LEVEL = "INFO"
OPTIONS_PATH = "/data/options.json"


try:
    with open(OPTIONS_PATH, "r") as f:
        opts = json.load(f)
except Exception as e:
    print(f"Failed to load options: {e}")
    exit(1)

# Mapping aus Text → Logging-Konstante
LOG_LEVEL_MAP = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET
}

configured_level = opts.get("log_level", DEFAULT_LOG_LEVEL).upper()
log_level = LOG_LEVEL_MAP.get(configured_level, logging.INFO)

# Logging setup
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
_LOGGER = logging.getLogger(__name__)
_LOGGER.info(f"Logging level set to: {configured_level}")


BASE_URL = opts.get("base_url", "http://192.168.x.x").strip()
VALID_URL_REGEX = r"^http://((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)$"

if (
    not BASE_URL
    or BASE_URL in ["http://192.168.x.x", "__PLEASE_CONFIGURE__"]
    or not BASE_URL.startswith("http://")
    or not re.match(VALID_URL_REGEX, BASE_URL)
):
    _LOGGER.error(f"BASE_URL is invalid or not configured: '{BASE_URL}'")
    exit(1)

app = Flask(__name__)

def robust_wait(driver, xpath, timeout=10, retries=3):
    for attempt in range(1, retries + 1):
        try:
            _LOGGER.debug(f"[robust_wait] Attempt {attempt}/{retries} for xpath: {xpath}")
            return WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
        except TimeoutException:
            _LOGGER.warning(f"[robust_wait] Timeout waiting for {xpath} (attempt {attempt})")
    _LOGGER.error(f"[robust_wait] Failed to find {xpath} after {retries} attempts.")
    raise TimeoutException(f"Element not found after {retries} retries: {xpath}")


def get_driver():
    _LOGGER.debug("Initializing Firefox WebDriver...")
    firefox_options = FirefoxOptions()
    firefox_options.add_argument("--headless")
    firefox_options.add_argument("--width=1920")
    firefox_options.add_argument("--height=1080")

    service = FirefoxService(executable_path="/usr/bin/geckodriver")  # falls nötig, Pfad anpassen
    driver = webdriver.Firefox(service=service, options=firefox_options)
    _LOGGER.debug("Firefox WebDriver initialized successfully.")
    return driver

def click_button_by_text(driver, label_text):
    try:
        _LOGGER.info(f"Attempting to click button '{label_text}'...")
        driver.get(f"{BASE_URL}/wallbox")
        xpath = f"//span[translate(normalize-space(text()), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{label_text.upper()}']/.."
        _LOGGER.debug(f"Using XPath: {xpath}")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.find_element(By.XPATH, xpath).click()
        _LOGGER.info(f"Button '{label_text}' clicked successfully.")
        return True
    except Exception as e:
        _LOGGER.error(f"Error clicking button '{label_text}': {e}")
        _LOGGER.debug(traceback.format_exc())
        return False
    finally:
        driver.quit()

@app.route("/wallbox/available_buttons", methods=["GET"])
def check_buttons_by_text():
    _LOGGER.info("Checking available buttons...")
    driver = get_driver()
    try:
        driver.get(f"{BASE_URL}/wallbox")
        button_labels = ["Start Charging", "Stop Charging", "Set Eco", "Set Full", "Set Solar"]
        results = {}
        for label in button_labels:
            xpath = f"//span[translate(normalize-space(text()), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{label.upper()}']/.."
            try:
                WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
                results[label] = True
                _LOGGER.debug(f"Button '{label}' found.")
            except:
                results[label] = False
                _LOGGER.debug(f"Button '{label}' not found.")
        response = {"success": True, "buttons": results}
        _LOGGER.debug(f"Response JSON: {json.dumps(response)}")
        return jsonify(response)
    except Exception as e:
        error_result = {"success": False, "error": str(e)}
        _LOGGER.debug(f"Error JSON: {json.dumps(error_result)}")
        _LOGGER.error(f"Error checking buttons: {e}")
        return jsonify(error_result)
    finally:
        driver.quit()



@app.route("/wallbox/status", methods=["GET"])
def get_status():
    _LOGGER.info("Retrieving wallbox status...")
    driver = get_driver()
    try:
        driver.get(f"{BASE_URL}/wallbox")

        _LOGGER.debug("Waiting for 'Mode' element...")
        mode_element = robust_wait(driver, "//h6[contains(text(), 'Mode ')]", timeout=5, retries=3)

        _LOGGER.debug("Waiting for 'Status' element...")
        status_element = robust_wait(driver, "//p[contains(text(), 'Status ')]", timeout=5, retries=3)

        mode_text = mode_element.text.replace("Mode ", "").strip()
        status_text = status_element.text.replace("Status ", "").strip()

        result = {"success": True, "mode": mode_text, "status": status_text}
        _LOGGER.debug(f"Response JSON: {json.dumps(result)}")
        _LOGGER.info(f"Status retrieved: mode='{mode_text}', status='{status_text}'")
        return jsonify(result)

    except TimeoutException as te:
        _LOGGER.warning("Final TimeoutException in get_status. Dumping page source.")
        _LOGGER.debug(driver.page_source)
        return jsonify({"success": False, "error": f"Timeout retrieving wallbox status: {str(te)}"})

    except Exception as e:
        _LOGGER.debug(driver.page_source)
        _LOGGER.debug(traceback.format_exc())
        _LOGGER.error(f"Unexpected error in get_status: {e}")
        return jsonify({"success": False, "error": str(e)})

    finally:
        driver.quit()


@app.route("/wallbox/start", methods=["POST"])
def start_charging():
    driver = get_driver()
    success = click_button_by_text(driver, "Start Charging")
    return jsonify({"success": success})

@app.route("/wallbox/stop", methods=["POST"])
def stop_charging():
    driver = get_driver()
    success = click_button_by_text(driver, "Stop Charging")
    return jsonify({"success": success})

@app.route("/wallbox/set_eco", methods=["POST"])
def set_mode_eco():
    driver = get_driver()
    success = click_button_by_text(driver, "Set Eco")
    return jsonify({"success": success})

@app.route("/wallbox/set_full", methods=["POST"])
def set_mode_full():
    driver = get_driver()
    success = click_button_by_text(driver, "Set Full")
    return jsonify({"success": success})

@app.route("/wallbox/set_solar", methods=["POST"])
def set_mode_solar():
    driver = get_driver()
    success = click_button_by_text(driver, "Set Solar")
    return jsonify({"success": success})

if __name__ == "__main__":
    _LOGGER.info("Starting Wallbox API service on port 36725...")
    app.run(host="0.0.0.0", port=36725)
