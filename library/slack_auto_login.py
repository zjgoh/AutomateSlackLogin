"""
Slack auto-login script.
Uses Selenium with auto-detected ChromeDriver. 2FA via TOTP (paste your 2FA secret key in .env).
"""
import os
import sys
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

try:
    import pyotp
except ImportError:
    pyotp = None

try:
    import pyautogui
except ImportError:
    pyautogui = None

# For focusing Chrome on Windows so pyautogui keys go to the right window
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        _user32 = ctypes.windll.user32
        _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        _user32.SetForegroundWindow.restype = wintypes.BOOL
        _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        _user32.GetWindowTextW.restype = ctypes.c_int
        _user32.IsWindowVisible.argtypes = [wintypes.HWND]
        _user32.IsWindowVisible.restype = wintypes.BOOL
    except Exception:
        _user32 = None
else:
    _user32 = None

# Load .env from project root (parent of library folder)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
load_dotenv(dotenv_path=os.path.join(_PROJECT_ROOT, ".env"))

SLACK_EMAIL = os.getenv("SLACK_EMAIL", "").strip()
SLACK_PASSWORD = os.getenv("SLACK_PASSWORD", "").strip()
# TOTP secret for 2FA (base32, from Slack's "Set up authenticator app" → "Enter key manually")
SLACK_TOTP_SECRET = os.getenv("SLACK_TOTP_SECRET", "").strip().replace(" ", "").upper()
SLACK_SIGNIN_URL = os.getenv("SLACK_SIGNIN_URL", "").strip()
HEADLESS = os.getenv("HEADLESS", "false").strip().lower() in ("true", "1", "yes")
TWOFA_WAIT_SECONDS = int(os.getenv("TWOFA_WAIT_SECONDS", "120").strip())

# Timeouts
PAGE_LOAD_TIMEOUT = 30
ELEMENT_WAIT_TIMEOUT = 20


def get_chrome_options() -> Options:
    """Build Chrome options."""
    opts = Options()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")

    # Suppress "Open with app?" / external protocol handler prompt for slack:// (like "Always allow")
    opts.add_experimental_option("prefs", {
        "protocol_handler.excluded_schemes": {
            "slack": True,
            "slack-workspace": True,
            "mailto": True,
            "file": True,
        }
    })

    return opts


def _chromedriver_cache_path():
    """Path to file where we cache the ChromeDriver executable path."""
    return os.path.join(_PROJECT_ROOT, ".chromedriver_path")


def _get_cached_driver_path():
    """Return cached ChromeDriver path if file exists and the exe exists."""
    cache_file = _chromedriver_cache_path()
    if not os.path.isfile(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            path = (f.read() or "").strip()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def _save_driver_path(path: str) -> None:
    """Save ChromeDriver path to cache file."""
    cache_file = _chromedriver_cache_path()
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(path)
    except Exception:
        pass


def create_driver():
    """Create Chrome WebDriver. Use cached driver if it exists and works; else download and cache."""
    opts = get_chrome_options()
    driver_path = _get_cached_driver_path()
    if driver_path:
        try:
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=opts)
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            return driver
        except Exception:
            pass  # Cached driver invalid (e.g. Chrome updated); fall back to download
    print("ChromeDriver not cached or outdated; downloading...")
    path = ChromeDriverManager().install()
    _save_driver_path(path)
    service = Service(path)
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver


def get_totp_code() -> str:
    """Generate current 6-digit TOTP code from SLACK_TOTP_SECRET."""
    if not pyotp:
        return ""
    if not SLACK_TOTP_SECRET:
        return ""
    try:
        totp = pyotp.TOTP(SLACK_TOTP_SECRET)
        return totp.now()
    except Exception:
        return ""


def wait_and_find(driver, by, value, timeout=ELEMENT_WAIT_TIMEOUT):
    """Wait for element and return it."""
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.presence_of_element_located((by, value)))


def wait_and_clickable(driver, by, value, timeout=ELEMENT_WAIT_TIMEOUT):
    """Wait for element to be clickable and return it."""
    wait = WebDriverWait(driver, timeout)
    return wait.until(EC.element_to_be_clickable((by, value)))


def _click_sign_in_with_password(driver, wait):
    """Click 'Sign in with password' / 'manually' so we use email+password instead of magic link."""
    for substring in ("password", "manually"):
        try:
            link = driver.find_element(
                By.XPATH,
                f"//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{substring}')] | //button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{substring}')] | //span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{substring}')]/ancestor::a[1]"
            )
            link.click()
            time.sleep(0.8)
            return True
        except Exception:
            continue
    return False


def _fill_2fa_with_code(driver, wait, code: str) -> bool:
    """Find 2FA code input (e.g. 'Enter your authentication code' page), type the code, and submit."""
    # Slack shows "Enter your authentication code" / "Check your authentication app" - find input on that page
    code_selectors = [
        (By.XPATH, "//*[contains(., 'Enter your authentication code') or contains(., 'authentication code')]//input"),
        (By.XPATH, "//*[contains(text(), 'authentication code')]/following::input[1]"),
        (By.XPATH, "//*[contains(., 'Check your authentication app')]//input"),
        (By.CSS_SELECTOR, 'input[autocomplete="one-time-code"]'),
        (By.CSS_SELECTOR, 'input[inputmode="numeric"]'),
        (By.CSS_SELECTOR, 'input[maxlength="6"]'),
        (By.CSS_SELECTOR, 'input[data-qa="two_factor_input"], input[data-qa="two_factor_input_field"]'),
        (By.CSS_SELECTOR, 'input[placeholder*="code" i], input[placeholder*="Code" i], input[placeholder*="verification" i]'),
    ]
    code_el = None
    for by, selector in code_selectors:
        try:
            code_el = wait.until(EC.presence_of_element_located((by, selector)))
            if code_el and code_el.is_displayed():
                break
        except Exception:
            continue
    if not code_el or not code:
        return False

    try:
        code_el.click()
        time.sleep(0.15)
    except Exception:
        pass
    code_el.clear()
    code_el.send_keys(code)
    time.sleep(0.3)
    for btn_text in ("Verify", "Submit", "Continue", "Sign in", "Log in"):
        try:
            btn = driver.find_element(By.XPATH, f"//button[contains(., '{btn_text}')]")
            if btn.is_displayed():
                btn.click()
                return True
        except Exception:
            continue
    try:
        code_el.submit()
    except Exception:
        pass
    return True


def slack_login(driver):
    """Navigate to Slack sign-in (email + password), submit, then fill 2FA with TOTP code."""
    driver.get(SLACK_SIGNIN_URL)
    wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT)
    time.sleep(0.7)

    # --- Prefer email + password: click "Sign in with password" / "manually" if present
    _click_sign_in_with_password(driver, wait)

    # --- Step 1: Email
    email_selector = (
        By.CSS_SELECTOR,
        'input[type="email"], input[name="email"], input[data-qa="signin_email_input"], #email'
    )
    try:
        email_el = wait.until(EC.presence_of_element_located(email_selector))
        email_el.clear()
        email_el.send_keys(SLACK_EMAIL)
    except Exception as e:
        try:
            email_el = driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="email" i], input[placeholder*="Email" i]')
            email_el.clear()
            email_el.send_keys(SLACK_EMAIL)
        except Exception:
            raise RuntimeError(f"Could not find email field. {e}") from e

    # Click Continue / Next if present (to get to password screen)
    for btn_text in ("Continue", "Next", "Continue with Email"):
        try:
            btn = driver.find_element(By.XPATH, f"//button[contains(., '{btn_text}')]")
            btn.click()
            time.sleep(1.0)
            break
        except Exception:
            continue

    # --- Step 2: Password (email + password flow only, no magic link)
    pwd_selector = (
        By.CSS_SELECTOR,
        'input[type="password"], input[name="password"], input[data-qa="signin_password_input"], #password'
    )
    try:
        pwd_el = wait.until(EC.presence_of_element_located(pwd_selector))
        pwd_el.clear()
        pwd_el.send_keys(SLACK_PASSWORD)
    except Exception as e:
        try:
            pwd_el = driver.find_element(By.CSS_SELECTOR, 'input[placeholder*="password" i], input[placeholder*="Password" i]')
            pwd_el.clear()
            pwd_el.send_keys(SLACK_PASSWORD)
        except Exception:
            raise RuntimeError(f"Could not find password field. {e}") from e

    # Submit sign-in
    for btn_text in ("Sign in", "Log in", "Sign In", "Log In"):
        try:
            btn = driver.find_element(By.XPATH, f"//button[contains(., '{btn_text}')]")
            btn.click()
            break
        except Exception:
            continue
    else:
        try:
            pwd_el.submit()
        except Exception:
            pass

    # Wait for "Enter your authentication code" page to appear after Login
    time.sleep(0.6)
    code = get_totp_code()
    print(f"\n>>> 2FA code: {code} <<<" if code else "\n>>> No TOTP code (enter 2FA manually).")

    # --- 2FA: paste code into the authentication code field and submit
    twofa_timeout = 15
    try:
        wait_2fa = WebDriverWait(driver, twofa_timeout)
        if code:
            if _fill_2fa_with_code(driver, wait_2fa, code):
                print("2FA code entered and submitted.")
                time.sleep(0.5)
            else:
                print(f">>> Could not find 2FA input. Type this code in the browser: {code}")
                if not HEADLESS and TWOFA_WAIT_SECONDS > 0:
                    wait_start = time.time()
                    while (time.time() - wait_start) < TWOFA_WAIT_SECONDS:
                        if "signin" not in driver.current_url.lower():
                            break
                        time.sleep(0.5)
                    else:
                        try:
                            input("Press Enter when you have finished 2FA...")
                        except (KeyboardInterrupt, EOFError):
                            pass
        else:
            if not HEADLESS and TWOFA_WAIT_SECONDS > 0:
                print(f"\n>>> No SLACK_TOTP_SECRET in .env. Enter 2FA manually in the browser. Waiting up to {TWOFA_WAIT_SECONDS}s...")
                wait_start = time.time()
                while (time.time() - wait_start) < TWOFA_WAIT_SECONDS:
                    if "signin" not in driver.current_url.lower():
                        break
                    time.sleep(0.5)
                else:
                    try:
                        input("Press Enter when you have finished 2FA...")
                    except (KeyboardInterrupt, EOFError):
                        pass
    except Exception as e:
        print(f">>> 2FA step error: {e}")
        _code = get_totp_code()
        if _code and not HEADLESS:
            print(f">>> Type this code in the browser: {_code}")
        if not HEADLESS and TWOFA_WAIT_SECONDS > 0:
            wait_start = time.time()
            while (time.time() - wait_start) < TWOFA_WAIT_SECONDS:
                if "signin" not in driver.current_url.lower():
                    break
                time.sleep(0.5)
            else:
                try:
                    input("Press Enter when you have finished 2FA...")
                except (KeyboardInterrupt, EOFError):
                    pass

    time.sleep(0.2)

    # --- After 2FA: send Right+Enter (Open Slack), refresh, wait for load; repeat until Slack desktop opens
    _open_slack_via_keys(driver)

    time.sleep(0.3)
    print("Current URL:", driver.current_url)
    return driver


def _focus_chrome_window(driver) -> bool:
    """Bring the Chrome browser window to the foreground so pyautogui keys go to it (Windows)."""
    if not _user32 or sys.platform != "win32":
        return False
    try:
        page_title = (driver.title or "").strip()
        found_hwnd = [None]

        def enum_callback(hwnd, lParam):
            if not _user32.IsWindowVisible(hwnd):
                return True
            buf = ctypes.create_unicode_buffer(260)
            _user32.GetWindowTextW(hwnd, buf, 260)
            title = (buf.value or "").strip()
            if "Chrome" not in title:
                return True
            if page_title and page_title in title:
                found_hwnd[0] = hwnd
                return False
            if found_hwnd[0] is None:
                found_hwnd[0] = hwnd
            return True

        WNDENUMPROC = ctypes.CFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        _user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
        _user32.EnumWindows.restype = wintypes.BOOL
        _user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
        if found_hwnd[0]:
            _user32.SetForegroundWindow(found_hwnd[0])
            time.sleep(0.08)
            #rint("Focused Chrome window.")
            return True
    except Exception as e:
        print(f"Could not focus Chrome: {e}")
    return False


def _click_open_slack_popup(driver, wait) -> bool:
    """Right after 2FA: focus Chrome, then emulate Right then Enter (Open Slack dialog)."""
    time.sleep(0.1)  # brief moment for "Open Slack?" dialog to appear
    _focus_chrome_window(driver)
    time.sleep(0.08)
    if pyautogui:
        try:
            pyautogui.press("right")
            time.sleep(0.08)
            pyautogui.press("enter")
            #print("Sent Right+Enter (pyautogui).")
            return True
        except Exception as e:
            print(f"pyautogui failed: {e}")
    return False


def _do_refresh(driver):
    """Refresh the page (try refresh() and JS reload)."""
    try:
        driver.refresh()
        #print("Refreshed (driver.refresh()).")
    except Exception:
        pass
    try:
        driver.execute_script("window.location.reload(true);")
        #print("Refreshed (JS reload).")
    except Exception:
        pass


def _open_slack_via_keys(driver, times: int = 6):
    """After 2FA: send Right+Enter (Open Slack), refresh, wait for load; repeat until Slack desktop opens."""
    wait = WebDriverWait(driver, 12)
    for i in range(times):
        time.sleep(0.4 if i == 0 else 0.3)
        print(f"Open Slack attempt {i + 1}/{times}...")
        _click_open_slack_popup(driver, wait)
        time.sleep(0.3)
        _do_refresh(driver)
        time.sleep(0.25)  # wait for page to load / "Open Slack?" dialog to appear again


def main():
    if not SLACK_EMAIL or not SLACK_PASSWORD:
        print("Missing SLACK_EMAIL or SLACK_PASSWORD in .env. Copy .env.example to .env and fill values.")
        sys.exit(1)
    if not pyotp and SLACK_TOTP_SECRET:
        print("Install pyotp for TOTP 2FA: pip install pyotp")
        sys.exit(1)

    driver = None
    try:
        if SLACK_TOTP_SECRET:
            _code = get_totp_code()
            print("2FA: Using TOTP from SLACK_TOTP_SECRET.")
            if _code:
                print(f"     Current 2FA code: {_code}")
        else:
            print("No SLACK_TOTP_SECRET in .env - you may need to enter 2FA manually.")
        print("Detecting Chrome version and preparing ChromeDriver...")
        driver = create_driver()
        print("ChromeDriver ready. Opening Slack sign-in...")
        slack_login(driver)
        print("Login complete. Slack desktop should be opened. Closing browser.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
