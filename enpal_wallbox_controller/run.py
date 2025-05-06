from flask import Flask, jsonify, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import time
import os

#BASE_URL = os.environ.get("BASE_URL", "http://192.168.178.178")  # Fallback optional

OPTIONS_PATH = "/data/options.json"

with open(OPTIONS_PATH, "r") as f:
    opts = json.load(f)

BASE_URL = opts.get("base_url", "http://192.168.178.178")

app = Flask(__name__)

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def click_button_by_id(driver, button_id):
    try:
        driver.get(f"{BASE_URL}/wallbox")
        time.sleep(2)  # wait for JS to load
        button = driver.find_element(By.ID, button_id)
        button.click()
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Fehler beim Klicken des Buttons {button_id}: {e}")
        return False
    finally:
        driver.quit()

def click_button_by_text(driver, label_text):
    try:
        driver.get(f"{BASE_URL}/wallbox")
        time.sleep(2)  # wait for JS to load

        with open("/app/debug.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)

        xpath = f"//span[translate(normalize-space(text()), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{label_text.upper()}']/.."
        print(f"Suche nach Button via XPath: {xpath}")
        button = driver.find_element(By.XPATH, xpath)
        button.click()
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Fehler beim Klicken des Buttons '{label_text}': {e}")
        traceback.print_exc()
        return False
    finally:
        driver.quit()

@app.route("/wallbox/available_buttons", methods=["GET"])
def check_buttons_by_text():
    driver = get_driver()
    try:
        driver.get(f"{BASE_URL}/wallbox")
        time.sleep(2)

        button_labels = ["Start Charging", "Stop Charging", "Set Eco", "Set Full", "Set Solar"]
        results = {}

        for label in button_labels:
            xpath = f"//span[translate(normalize-space(text()), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{label.upper()}']/.."
            try:
                driver.find_element(By.XPATH, xpath)
                results[label] = True
            except:
                results[label] = False

        return jsonify({"success": True, "buttons": results})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    finally:
        driver.quit()
        
@app.route("/wallbox/status", methods=["GET"])
def get_status():
    try:
        driver = get_driver()
        driver.get(os.environ.get("WALLBOX_URL", "http://192.168.178.178/wallbox"))
        time.sleep(2)

        # Mode extrahieren
        mode_elem = driver.find_element(By.XPATH, "//h6[contains(text(), 'Mode ')]")
        mode_text = mode_elem.text.replace("Mode ", "").strip() if mode_elem else ""

        # Status extrahieren
        status_elem = driver.find_element(By.XPATH, "//p[contains(text(), 'Status ')]")
        status_text = status_elem.text.replace("Status ", "").strip() if status_elem else ""
        

        return jsonify({"success": True, "mode": mode_text, "status": status_text})

    except Exception as e:
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
    app.run(host="0.0.0.0", port=36725)
