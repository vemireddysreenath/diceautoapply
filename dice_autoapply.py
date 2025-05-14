from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json
from datetime import datetime
from dotenv import load_dotenv

# --- LOAD ENV (.env) ---
load_dotenv()
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

# --- LOAD CONFIG (config.json) ---
with open("config.json", "r") as f:
    config = json.load(f)

FILTERED_JOBS_URL = config.get("filtered_jobs_url")
APPLY_LIMIT = config.get("apply_limit", 30)

APPLIED_JOBS_FILE = "applied_jobs.txt"
APPLIED_LOG_FILE = "applied_log.json"

# --- SETUP ---
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=options)

# --- TRACKING ---
def load_applied_jobs():
    if not os.path.exists(APPLIED_JOBS_FILE):
        return set()
    with open(APPLIED_JOBS_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())

def mark_job_as_applied(url):
    with open(APPLIED_JOBS_FILE, "a") as f:
        f.write(url + "\n")

def is_already_applied(url, applied_jobs_set):
    return url in applied_jobs_set

def log_applied_job(job_url, job_title, company):
    log_entry = {
        "url": job_url,
        "title": job_title,
        "company": company,
        "applied_at": datetime.now().isoformat()
    }

    logs = []
    if os.path.exists(APPLIED_LOG_FILE):
        with open(APPLIED_LOG_FILE, "r") as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = []

    logs.append(log_entry)

    with open(APPLIED_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

# --- LOGIN ---
def login():
    print("[*] Navigating to Dice login page...")
    driver.get("https://www.dice.com/dashboard/login")

    try:
        print("[*] Entering email...")
        email_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        email_input.send_keys(EMAIL)

        continue_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Continue']]"))
        )
        continue_btn.click()

        print("[*] Entering password...")
        password_input = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        password_input.send_keys(PASSWORD)

        signin_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Sign In']]"))
        )
        signin_btn.click()

        print("[+] Login successful.")
        time.sleep(5)

    except Exception as e:
        print("[!] Login failed:", e)
        driver.quit()

# --- OPEN JOB PAGES ---
def open_all_job_pages_in_tabs(driver, FILTERED_JOBS_URL):
    print("[*] Loading base search URL...")
    driver.get(FILTERED_JOBS_URL)
    wait = WebDriverWait(driver, 10)

    try:
        page_spans = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//span[contains(@class, 'font-bold') and text()[number()=number(.)]]"))
        )
        page_numbers = [int(span.text.strip()) for span in page_spans if span.text.strip().isdigit()]
        total_pages = max(page_numbers) if page_numbers else 1
        print(f"[+] Found total pages: {total_pages}")
    except Exception:
        print("[!] Could not determine page count. Defaulting to 1.")
        total_pages = 1

    all_page_urls = [
        FILTERED_JOBS_URL if i == 1 else f"{FILTERED_JOBS_URL}&page={i}"
        for i in range(1, total_pages + 1)
    ]

    for url in all_page_urls:
        print(f"[→] Opening: {url}")
        driver.execute_script(f"window.open('{url}', '_blank');")
        time.sleep(1)

    print("[✓] All pages opened.")

# --- EASY APPLY FLOW ---
def handle_easy_apply_flow():
    print("[*] Starting Easy Apply flow...")
    tabs = driver.window_handles
    applied_jobs = load_applied_jobs()
    applied_count = 0

    for tab_index, tab in enumerate(tabs[1:], start=1):
        print(f"[→] Processing tab {tab_index}/{len(tabs) - 1}")
        driver.switch_to.window(tab)
        time.sleep(2)

        buttons = driver.find_elements(By.XPATH, "//a[contains(@class, 'inline-flex') and @target='_blank']")
        print(f"    Found {len(buttons)} job buttons")

        for button_index, button in enumerate(buttons, start=1):
            try:
                label = button.text.strip()
                url = button.get_attribute("href")

                if "Applied" in label or not url or "Easy Apply" not in label:
                    continue
                if is_already_applied(url, applied_jobs):
                    print(f"    [→] Already applied (tracked): {url}")
                    continue

                print(f"    [✓] Opening job {button_index}: {url}")
                driver.execute_script(f"window.open('{url}', '_blank');")
                time.sleep(3)

                new_tab = driver.window_handles[-1]
                driver.switch_to.window(new_tab)
                time.sleep(5)

                try:
                    title_elem = driver.find_element(By.TAG_NAME, "h1")
                    job_title = title_elem.text.strip()
                except:
                    job_title = "Unknown Title"

                try:
                    company_elem = driver.find_element(By.XPATH, "//span[contains(@class, 'company')]")
                    company_name = company_elem.text.strip()
                except:
                    company_name = "Unknown Company"

                try:
                    easy_apply_btn = driver.find_element(By.XPATH, "//*[@id='applyButton']/apply-button-wc")
                    easy_apply_btn.click()
                    print("        → Clicked Easy apply")
                    time.sleep(2)
                except:
                    print("        → Easy apply button not found")
                    driver.close()
                    driver.switch_to.window(tab)
                    continue

                try:
                    next_span = driver.find_element(By.XPATH, "//span[text()='Next']")
                    next_span.click()
                    print("        → Clicked Next")
                    time.sleep(2)
                except:
                    print("        → No Next button")

                try:
                    submit_span = driver.find_element(By.XPATH, "//span[text()='Submit']")
                    submit_span.click()
                    print("        → Clicked Submit")
                    time.sleep(2)
                except:
                    print("        → No Submit button")

                mark_job_as_applied(url)
                log_applied_job(url, job_title, company_name)
                applied_jobs.add(url)
                applied_count += 1
                print(f"        → Applied count: {applied_count}/{APPLY_LIMIT}")

                driver.close()
                driver.switch_to.window(tab)
                time.sleep(1)

                if applied_count >= APPLY_LIMIT:
                    print(f"[✓] Apply limit {APPLY_LIMIT} reached. Stopping.")
                    return

            except Exception as e:
                print(f"    [!] Error processing job {button_index}: {e}")
                driver.switch_to.window(tab)
                continue

    print("[✓] Completed Easy Apply flow.")

# --- RUN APP ---
login()
open_all_job_pages_in_tabs(driver, FILTERED_JOBS_URL)
handle_easy_apply_flow()
driver.quit()