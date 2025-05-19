from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json
import re
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
MAX_EXPERIENCE_YEARS = config.get("max_experience_years", 3)

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

def exceeds_experience_limit(text, max_years=MAX_EXPERIENCE_YEARS):
    pattern = r'\b(?:at least|min(?:imum)?|over)?\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s*(?:of experience)?'
    matches = re.findall(pattern, text, re.IGNORECASE)
    for match in matches:
        try:
            years = int(match)
            if years > max_years:
                return True
        except ValueError:
            continue
    return False

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

# --- APPLY TO JOBS PAGE BY PAGE ---
def apply_jobs_on_page(applied_jobs, applied_count):
    wait = WebDriverWait(driver, 10)
    buttons = driver.find_elements(By.XPATH, "//a[contains(@class, 'inline-flex') and @target='_blank']")
    print(f"[→] Found {len(buttons)} job links on page")

    for button in buttons:
        if applied_count >= APPLY_LIMIT:
            return applied_count

        try:
            label = button.text.strip()
            url = button.get_attribute("href")

            if "Applied" in label or not url or "Easy Apply" not in label:
                continue
            if is_already_applied(url, applied_jobs):
                continue

            driver.execute_script("window.open(arguments[0]);", url)
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(4)

            try:
                title = driver.find_element(By.TAG_NAME, "h1").text.strip()
                desc = driver.find_element(By.XPATH, "//div[contains(@class, 'job-description')]").text
                combined = title + " " + desc
                if exceeds_experience_limit(combined):
                    print("    Skipped due to experience requirement")
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
            except:
                pass

            try:
                job_title = driver.find_element(By.TAG_NAME, "h1").text.strip()
            except:
                job_title = "Unknown Title"

            try:
                company = driver.find_element(By.XPATH, "//span[contains(@class, 'company')]").text.strip()
            except:
                company = "Unknown Company"

            try:
                apply_btn = driver.find_element(By.XPATH, "//*[@id='applyButton']/apply-button-wc")
                apply_btn.click()
                print("    Clicked Easy Apply")
                time.sleep(2)
            except:
                print("    Easy Apply not found")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                continue

            try:
                next_btn = driver.find_element(By.XPATH, "//span[text()='Next']")
                next_btn.click()
                time.sleep(2)
            except:
                pass

            try:
                submit_btn = driver.find_element(By.XPATH, "//span[text()='Submit']")
                submit_btn.click()
                print("    Submitted Application")
                time.sleep(2)
            except:
                pass

            mark_job_as_applied(url)
            log_applied_job(url, job_title, company)
            applied_jobs.add(url)
            applied_count += 1
            print(f"    Applied Count: {applied_count}/{APPLY_LIMIT}")

            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(1)

        except Exception as e:
            print(f"    Error: {e}")
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

    return applied_count

def go_to_next_page_and_apply():
    applied_jobs = load_applied_jobs()
    applied_count = 0

    driver.get(FILTERED_JOBS_URL)
    wait = WebDriverWait(driver, 10)
    time.sleep(4)

    while applied_count < APPLY_LIMIT:
        applied_count = apply_jobs_on_page(applied_jobs, applied_count)

        try:
            next_btn = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//span[@role='link' and @aria-label='Next']"))
            )
            if "cursor-not-allowed" in next_btn.get_attribute("class"):
                print("[✓] Reached last page.")
                break

            # Force click using JavaScript
            driver.execute_script("arguments[0].click();", next_btn)
            print("[→] Clicked Next")
            time.sleep(5)

        except Exception as e:
            print(f"[✓] Could not move to next page: {e}")
            break

    print("[✓] Finished job applications.")



# --- RUN APP ---
login()
go_to_next_page_and_apply()
driver.quit()
