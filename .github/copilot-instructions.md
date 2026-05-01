# Enpal Wallbox Controller - AI Coding Agent Instructions

## Project Overview
This is a **Home Assistant Add-on** that controls Enpal Wallbox charging stations via web UI automation. It uses Selenium + Firefox in headless mode to click buttons on the local Enpal Box web interface (`http://192.168.x.x/wallbox`), exposing those actions via a REST API.

**Critical**: This is NOT a standalone Python app - it's a containerized Home Assistant add-on with specific packaging requirements.

## Architecture

### Component Stack
1. **Flask REST API** (`run.py`) - Exposes HTTP endpoints on port 36725
2. **Selenium WebDriver** - Firefox headless browser automation
3. **Shared Driver Pool** - Single WebDriver instance reused across requests with 5-minute timeout
4. **Docker Container** - Multi-arch support (amd64, aarch64, armv7)

### Critical Files
- `enpal_wallbox_controller/run.py` - Main application (Flask + Selenium logic)
- `enpal_wallbox_controller/config.yaml` - Home Assistant add-on configuration schema
- `enpal_wallbox_controller/Dockerfile` - Build instructions with architecture-aware geckodriver install
- `repository.yaml` - Repository metadata for Home Assistant add-on store

### Health Monitoring
- `/health` endpoint returns HTTP 200 (healthy) or 503 (unhealthy)
- Home Assistant supervisor uses this for automated restarts
- Checks driver availability and configuration validity

## Key Patterns & Conventions

### Web Scraping Strategy
- **XPath with case-insensitive matching**: Use `build_button_xpath(label_text)` - centralizes XPath logic
  ```python
  xpath = build_button_xpath(ButtonLabels.START_CHARGING)
  ```
- **Button label constants**: All UI text centralized in `ButtonLabels` class for easy localization
- **Robust retry logic**: `robust_wait()` retries element location up to 3 times with configurable timeouts
- **Driver reuse with auto-recovery**: Shared WebDriver instance with health checks - auto-recreates on crash

### Configuration Management
- Options loaded from `/data/options.json` (Home Assistant convention)
- `base_url` validation: Must match `http://IP` format (IPv4 only)
- Log levels: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET (mapped from string to logging constants)

### API Endpoint Pattern
All wallbox control endpoints follow this pattern:
```python
@app.route("/wallbox/action", methods=["POST"])
def action_name():
    return jsonify({"success": click_button_by_text("Button Label")})
```

### Multi-Architecture Support
Dockerfile detects architecture (`uname -m`) and downloads correct geckodriver binary:
- `x86_64` → `linux64`
- `aarch64` → `linux-aarch64`
- Other architectures fail fast with clear error

## Development Workflows

### Local Testing
```bash
# Build Docker image
docker build -t enpal-wallbox-controller ./enpal_wallbox_controller

# Run with mock options
docker run -p 36725:36725 -v $(pwd)/test-options.json:/data/options.json enpal-wallbox-controller
```

### Debugging Selenium Issues
- Set `log_level: DEBUG` in config to see XPath queries and page source dumps
- On timeout/errors, `driver.page_source` is logged for post-mortem analysis
- Use `_LOGGER.debug(driver.page_source)` sparingly (produces huge logs)

### Version Bumping
1. Update `version` in `enpal_wallbox_controller/config.yaml`
2. Tag release (triggers changelog generation via GitHub Actions)
3. Users update via Home Assistant add-on store

## Common Pitfalls

### 1. Button Text Localization
The Enpal Box UI may serve German or English text. XPath uses uppercase normalization, but button labels are hardcoded in English:
- "Start Charging" / "Stop Charging"
- "Set Eco" / "Set Solar" / "Set Full" / "Set Smart"

**If localization breaks**: Add German equivalents or regex patterns in XPath.

### 1b. Status Field Label (Firmware Drift)
Newer Enpal Box firmware renamed the wallbox status field from `Status ...` to `Connector ...` (OCPP `ChargePointStatus` values such as `Available`, `Charging`, `Finishing`, `SuspendedEV`).
- `get_status()` iterates over a `STATUS_LABELS` list (`["Status", "Connector"]`) and uses the first label that resolves on the page.
- When the value comes from the `Connector` label, it is translated back to the legacy vocabulary (`NotConnected`, `Connected`, `Charging`, `Finishing`, `Unknown`) via `CONNECTOR_TO_LEGACY_STATUS` so the Home Assistant integration (https://github.com/derolli1976/enpal) keeps working unchanged.
- The original OCPP value is always exposed as `raw_status` (with `status_source: "connector"`) in the JSON response.
- Unknown OCPP values are passed through and logged as `WARNING` so the map can be extended.

**If a new firmware introduces yet another label or value**: extend `STATUS_LABELS` and/or `CONNECTOR_TO_LEGACY_STATUS` in `run.py` — do not change the legacy output vocabulary, that is the public contract toward the HA integration.

### 2. Driver Lifecycle
- **Always use `get_shared_driver()`** - never access `shared_driver` directly
- Driver health is checked on each request - auto-recreates if unresponsive
- Background thread shuts down driver after 300s of inactivity
- Lock acquisition is critical: always use `with driver_lock:` when accessing `shared_driver`

### 3. Home Assistant Add-on Constraints
- Must expose port in `config.yaml` ports section
- `startup: services` means add-on waits for Home Assistant services
- `map: config:rw` provides persistent storage access
- `schema` section enforces type validation for user options

### 4. Timeout Tuning
- `robust_wait()` default: 10s timeout, 3 retries
- Page load timeout: implicit in `driver.get()`
- If Enpal Box is slow, increase `timeout` parameter in `robust_wait()` calls

## Extension Points

### Adding New Endpoints
1. Identify button text on `/wallbox` page
2. Add route in `run.py`:
   ```python
   @app.route("/wallbox/new_action", methods=["POST"])
   def new_action():
       return jsonify({"success": click_button_by_text("Button Text")})
   ```
3. Update README.md with new endpoint

### Supporting New Status Fields
Modify `get_status()` to extract additional elements:
```python
element = robust_wait(driver, "//xpath-to-element", timeout=5, retries=3)
result["new_field"] = element.text.strip()
```

### Multi-Language Support
Currently only English button labels. To support German:
1. Detect page language from HTML `lang` attribute
2. Use dict mapping: `{"en": "Start Charging", "de": "Laden Starten"}`
3. Pass correct label to `click_button_by_text()`

## Testing Notes
- No automated tests exist (manual validation via browser)
- Test with actual Enpal Box hardware on local network
- Validate all endpoints return `{"success": true/false}` JSON
- Check `docker logs` for Selenium errors during button clicks
