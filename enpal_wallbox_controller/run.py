import json
import logging
import os
import re
import traceback
import threading
import time

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
logging.basicConfig(level=log_level, format="%(asctime)s [%(levelname)s] %(message)s")
_LOGGER = logging.getLogger(__name__)
_LOGGER.info(f"Logging level set to: {configured_level}")

BASE_URL = opts.get("base_url", "http://192.168.x.x").strip()
VALID_URL_REGEX = r"^http://((25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)\.){3}(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)$"
if not BASE_URL or BASE_URL in ["http://192.168.x.x", "__PLEASE_CONFIGURE__"] or not re.match(VALID_URL_REGEX, BASE_URL):
    _LOGGER.error(f"BASE_URL is invalid or not configured: '{BASE_URL}'")
    exit(1)

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Home Assistant supervisor monitoring.
    
    Returns HTTP 200 if service is healthy, 503 if unhealthy.
    """
    try:
        # Verify configuration is valid
        if not BASE_URL:
            return jsonify({"status": "unhealthy", "error": "BASE_URL not configured"}), 503
        
        # Verify driver can be accessed (doesn't create new one if exists)
        driver = get_shared_driver()
        is_active = driver is not None
        
        return jsonify({
            "status": "healthy",
            "driver_active": is_active,
            "base_url": BASE_URL
        }), 200
    except Exception as e:
        _LOGGER.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503

# Shared WebDriver management
shared_driver = None
driver_lock = threading.Lock()
last_used = 0
DRIVER_TIMEOUT_SEC = 300

# Status caching for transient "Unknown" states
# When the wallbox reports "Charging" and then briefly switches to "Unknown",
# we cache the last valid "Charging" status for up to 2 minutes.
STATUS_CACHE_TIMEOUT_SEC = 120  # 2 minutes
_cached_status = None       # Last known valid "Charging" status text
_cached_mode = None         # Corresponding mode at the time of caching
_unknown_since = None       # Timestamp when "Unknown" was first seen after "Charging"

def init_driver():
    _LOGGER.debug("Starting new Firefox WebDriver...")
    options = FirefoxOptions()
    options.add_argument("--headless")
    options.add_argument("--width=1920")
    options.add_argument("--height=1080")
    service = FirefoxService(executable_path="/usr/bin/geckodriver")
    return webdriver.Firefox(service=service, options=options)

def get_shared_driver():
    global shared_driver, last_used
    with driver_lock:
        # Check if driver exists and is still responsive
        if shared_driver is not None:
            try:
                # Quick health check - accessing current_url should be fast
                _ = shared_driver.current_url
                _LOGGER.debug("Existing driver is responsive")
            except Exception as e:
                _LOGGER.warning(f"Driver became unresponsive: {e}. Recreating...")
                try:
                    shared_driver.quit()
                except Exception:
                    pass
                shared_driver = None
        
        # Create new driver if needed
        if shared_driver is None:
            shared_driver = init_driver()
        
        last_used = time.time()
        return shared_driver

def shutdown_driver_when_unused():
    global shared_driver, last_used
    while True:
        time.sleep(60)
        with driver_lock:
            if shared_driver and (time.time() - last_used > DRIVER_TIMEOUT_SEC):
                _LOGGER.info("Shutting down unused WebDriver...")
                try:
                    shared_driver.quit()
                except Exception:
                    pass
                shared_driver = None

threading.Thread(target=shutdown_driver_when_unused, daemon=True).start()

class ButtonLabels:
    """Enpal Box UI button text (currently English only).
    
    Centralized button labels for easier maintenance and future localization.
    """
    START_CHARGING = "Start Charging"
    STOP_CHARGING = "Stop Charging"
    SET_ECO = "Set Eco"
    SET_FULL = "Set Full"
    SET_SOLAR = "Set Solar"
    SET_SMART = "Set Smart"

    @classmethod
    def all(cls):
        """Return list of all button labels."""
        return [cls.START_CHARGING, cls.STOP_CHARGING, cls.SET_ECO, cls.SET_FULL, cls.SET_SOLAR, cls.SET_SMART]

def build_button_xpath(label_text):
    """Build case-insensitive XPath for button matching by text.
    
    Args:
        label_text: The button text to search for (case-insensitive)
    
    Returns:
        XPath string for locating the button element
    """
    return f"//span[translate(normalize-space(text()), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')='{label_text.upper()}']/.."

def robust_wait(driver, xpath, timeout=10, retries=3):
    for attempt in range(1, retries + 1):
        try:
            _LOGGER.debug(f"[robust_wait] Attempt {attempt}/{retries} for xpath: {xpath}")
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))
        except TimeoutException:
            _LOGGER.warning(f"[robust_wait] Timeout waiting for {xpath} (attempt {attempt})")
    raise TimeoutException(f"Element not found after {retries} retries: {xpath}")

def click_button_by_text(label_text):
    driver = get_shared_driver()
    try:
        _LOGGER.info(f"Clicking button '{label_text}'...")
        driver.get(f"{BASE_URL}/wallbox")
        _LOGGER.debug(f"Page loaded: {driver.current_url}")
        # _LOGGER.debug(driver.page_source)

        xpath = build_button_xpath(label_text)
        _LOGGER.debug(f"Using XPath: {xpath}")
        _LOGGER.debug("Waiting for element to become clickable...")
        WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.find_element(By.XPATH, xpath).click()
        _LOGGER.info(f"Button '{label_text}' clicked successfully.")
        return True
    except Exception as e:
        _LOGGER.error(f"Error clicking button '{label_text}': {e}")
        _LOGGER.debug(traceback.format_exc())
        _LOGGER.debug(driver.page_source)
        return False

@app.route("/wallbox/available_buttons", methods=["GET"])
def check_buttons_by_text():
    driver = get_shared_driver()
    try:
        _LOGGER.info("Checking available buttons...")
        driver.get(f"{BASE_URL}/wallbox")
        _LOGGER.debug(f"Page loaded: {driver.current_url}")
        # _LOGGER.debug(driver.page_source)

        button_labels = ButtonLabels.all()
        results = {}
        for label in button_labels:
            xpath = build_button_xpath(label)
            try:
                _LOGGER.debug(f"Checking for button '{label}' using XPath: {xpath}")
                WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.XPATH, xpath)))
                _LOGGER.debug(f"Button '{label}' found.")
                results[label] = True
            except Exception as ex:
                _LOGGER.debug(f"Button '{label}' not found: {ex}")
                results[label] = False
        response = {"success": True, "buttons": results}
        _LOGGER.debug(f"Response JSON: {json.dumps(response)}")
        return jsonify(response)
    except Exception as e:
        _LOGGER.error(f"Error checking buttons: {e}")
        _LOGGER.debug(traceback.format_exc())
        _LOGGER.debug(driver.page_source)
        return jsonify({"success": False, "error": str(e)})

# Translation map: new OCPP-style "Connector" values → legacy "Status" values.
# Newer Enpal Box firmware exposes the OCPP ChargePointStatus on the wallbox
# page (e.g. "Connector SuspendedEV") instead of the previous short status
# tokens (e.g. "Status Charging"). The Home Assistant integration consumes
# the /wallbox/status endpoint and still expects the legacy vocabulary, so we
# normalize the new values here. Unknown/missing keys are passed through
# unchanged and a warning is logged so we can extend the map over time.
#
# Legacy "Status" values produced by the old firmware:
#   Unknown, NotConnected, unknown, Connected, Charging, Finishing
#
# Mapping confirmed against Enpal Box behaviour (user feedback):
#   Connector Available    → no car connected         → NotConnected
#   Connector Charging     → actively charging        → Charging
#   Connector Finishing    → car only plugged in      → Connected
#   Connector SuspendedEV  → fully charged / target   → Finishing
# The original OCPP value is always exposed as `raw_status` in the response
# so users who want finer granularity can still react on it.
CONNECTOR_TO_LEGACY_STATUS = {
    "Available": "NotConnected",
    "Preparing": "Connected",
    "Charging": "Charging",
    "SuspendedEV": "Finishing",
    "SuspendedEVSE": "Connected",
    "Finishing": "Connected",
    "Reserved": "Connected",
    "Unavailable": "Unknown",
    "Faulted": "Unknown",
}


def _apply_status_cache(status_text, mode_text):
    """Apply caching logic for transient 'Unknown' status after 'Charging'.

    When the wallbox was previously reporting 'Charging' and switches to 'Unknown',
    the cached 'Charging' status is returned for up to STATUS_CACHE_TIMEOUT_SEC (10 min).
    After that timeout, 'Unknown' is passed through.

    Args:
        status_text: The raw status text from the wallbox page
        mode_text: The raw mode text from the wallbox page

    Returns:
        Tuple of (effective_status, effective_mode, is_cached)
    """
    global _cached_status, _cached_mode, _unknown_since

    status_upper = status_text.upper() if status_text else ""

    # Case 1: Status is valid (not "Unknown") → update cache, reset unknown timer
    if status_upper != "UNKNOWN":
        if status_upper == "CHARGING":
            _cached_status = status_text
            _cached_mode = mode_text
            _LOGGER.debug(f"Status cache updated: status='{status_text}', mode='{mode_text}'")
        else:
            # Non-charging, non-unknown status → clear cache
            _cached_status = None
            _cached_mode = None
            _LOGGER.debug(f"Status cache cleared (status='{status_text}' is not 'Charging')")
        _unknown_since = None
        return status_text, mode_text, False

    # Case 2: Status is "Unknown"
    if _cached_status is None:
        # No cached Charging status → pass through Unknown immediately
        _LOGGER.debug("Status is 'Unknown' but no cached 'Charging' status available")
        _unknown_since = None
        return status_text, mode_text, False

    now = time.time()

    if _unknown_since is None:
        # First time seeing Unknown after Charging → start timer, return cached
        _unknown_since = now
        _LOGGER.info(
            f"Status is 'Unknown' after 'Charging' → returning cached status "
            f"'{_cached_status}' (cache window: {STATUS_CACHE_TIMEOUT_SEC}s)"
        )
        return _cached_status, _cached_mode, True

    elapsed = now - _unknown_since
    if elapsed < STATUS_CACHE_TIMEOUT_SEC:
        # Still within cache window → return cached status
        remaining = STATUS_CACHE_TIMEOUT_SEC - elapsed
        _LOGGER.info(
            f"Status still 'Unknown' ({elapsed:.0f}s) → returning cached "
            f"'{_cached_status}' ({remaining:.0f}s remaining)"
        )
        return _cached_status, _cached_mode, True

    # Cache window expired → pass through Unknown, clear cache
    _LOGGER.warning(
        f"Status 'Unknown' persisted for {elapsed:.0f}s (>{STATUS_CACHE_TIMEOUT_SEC}s) "
        f"→ cache expired, passing through 'Unknown'"
    )
    _cached_status = None
    _cached_mode = None
    _unknown_since = None
    return status_text, mode_text, False


@app.route("/wallbox/status", methods=["GET"])
def get_status():
    driver = get_shared_driver()
    try:
        _LOGGER.info("Retrieving wallbox status...")
        driver.get(f"{BASE_URL}/wallbox")
        _LOGGER.debug(f"Page loaded: {driver.current_url}")
        # _LOGGER.debug(driver.page_source)

        _LOGGER.debug("Waiting for 'Mode' element...")
        mode_element = robust_wait(driver, "//h6[contains(text(), 'Mode ')]", timeout=5, retries=3)

        # The status field label changed in newer Enpal Box firmware versions.
        # Older firmware: <p>Status Charging</p>
        # Newer firmware: <p>Connector SuspendedEV</p>
        # Try known labels in order; the first match wins.
        STATUS_LABELS = ["Status", "Connector"]
        status_element = None
        status_label_used = None
        for label in STATUS_LABELS:
            try:
                _LOGGER.debug(f"Waiting for status element with label '{label}'...")
                status_element = robust_wait(
                    driver,
                    f"//p[contains(text(), '{label} ')]",
                    timeout=3,
                    retries=2,
                )
                status_label_used = label
                _LOGGER.debug(f"Status element found using label '{label}'")
                break
            except TimeoutException:
                _LOGGER.debug(f"Status label '{label}' not found, trying next...")
                continue

        if status_element is None:
            raise TimeoutException(
                f"No known status label found on page. Tried: {STATUS_LABELS}"
            )

        mode_text = mode_element.text.replace("Mode ", "").strip()
        status_text = status_element.text.replace(f"{status_label_used} ", "").strip()
        raw_status_text = status_text

        # If the status was read from the new "Connector" label, translate the
        # OCPP-style values back to the legacy "Status" vocabulary so that the
        # Home Assistant integration (https://github.com/derolli1976/enpal),
        # which still expects the old wording, keeps working unchanged.
        if status_label_used == "Connector":
            translated = CONNECTOR_TO_LEGACY_STATUS.get(status_text)
            if translated is not None:
                _LOGGER.debug(
                    f"Translated Connector value '{status_text}' "
                    f"→ legacy Status '{translated}'"
                )
                status_text = translated
            else:
                _LOGGER.warning(
                    f"Unknown Connector value '{status_text}' - no legacy "
                    f"translation available, passing through unchanged"
                )

        # Apply status caching logic for transient "Unknown" after "Charging"
        effective_status, effective_mode, is_cached = _apply_status_cache(status_text, mode_text)

        result = {"success": True, "mode": effective_mode, "status": effective_status}
        if status_label_used == "Connector" and raw_status_text != effective_status:
            result["raw_status"] = raw_status_text
            result["status_source"] = "connector"
        if is_cached:
            result["cached"] = True
            result["raw_status"] = raw_status_text
        _LOGGER.debug(f"Status result JSON: {json.dumps(result)}")
        _LOGGER.info(f"Status retrieved: mode='{effective_mode}', status='{effective_status}'{' (cached)' if is_cached else ''}")
        return jsonify(result)

    except TimeoutException as te:
        _LOGGER.warning("Final TimeoutException in get_status. Dumping page source.")
        _LOGGER.debug(driver.page_source)
        _LOGGER.debug(traceback.format_exc())
        return jsonify({"success": False, "error": f"Timeout retrieving wallbox status: {str(te)}"})

    except Exception as e:
        _LOGGER.error(f"Unexpected error in get_status: {e}")
        _LOGGER.debug(traceback.format_exc())
        _LOGGER.debug(driver.page_source)
        return jsonify({"success": False, "error": str(e)})

@app.route("/wallbox/start", methods=["POST"])
def start_charging():
    return jsonify({"success": click_button_by_text(ButtonLabels.START_CHARGING)})

@app.route("/wallbox/stop", methods=["POST"])
def stop_charging():
    return jsonify({"success": click_button_by_text(ButtonLabels.STOP_CHARGING)})

@app.route("/wallbox/set_eco", methods=["POST"])
def set_mode_eco():
    return jsonify({"success": click_button_by_text(ButtonLabels.SET_ECO)})

@app.route("/wallbox/set_full", methods=["POST"])
@app.route("/wallbox/set_fast", methods=["POST"])
def set_mode_full():
    return jsonify({"success": click_button_by_text(ButtonLabels.SET_FULL)})

@app.route("/wallbox/set_solar", methods=["POST"])
def set_mode_solar():
    return jsonify({"success": click_button_by_text(ButtonLabels.SET_SOLAR)})

@app.route("/wallbox/set_smart", methods=["POST"])
def set_mode_smart():
    return jsonify({"success": click_button_by_text(ButtonLabels.SET_SMART)})

if __name__ == "__main__":
    _LOGGER.info("Starting Wallbox API service on port 36725...")
    app.run(host="0.0.0.0", port=36725)
