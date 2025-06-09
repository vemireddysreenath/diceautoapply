"""Dice Auto Apply Agent.

This module defines a class-based agent that logs into Dice.com and applies to
jobs using the Easy Apply feature. Applied and failed attempts are recorded in
JSON log files which can be viewed using `index.html`.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import List, Set

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class DiceAutoApplyAgent:
    """A simple Selenium-based agent to auto-apply to Dice jobs."""

    APPLIED_JOBS_FILE = "applied_jobs.txt"
    APPLIED_LOG_FILE = "applied_log.json"
    FAILED_LOG_FILE = "failed_log.json"

    def __init__(self) -> None:
        load_dotenv()
        self.email = os.getenv("EMAIL")
        self.password = os.getenv("PASSWORD")

        with open("config.json", "r") as f:
            cfg = json.load(f)

        self.filtered_jobs_url = cfg.get("filtered_jobs_url")
        self.apply_limit = cfg.get("apply_limit", 30)
        self.max_experience_years = cfg.get("max_experience_years", 3)

        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _load_applied_jobs(self) -> Set[str]:
        if not os.path.exists(self.APPLIED_JOBS_FILE):
            return set()
        with open(self.APPLIED_JOBS_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())

    def _mark_job_as_applied(self, url: str) -> None:
        with open(self.APPLIED_JOBS_FILE, "a") as f:
            f.write(url + "\n")

    def _is_already_applied(self, url: str, applied_jobs: Set[str]) -> bool:
        return url in applied_jobs

    def _append_json_log(self, filename: str, entry: dict) -> None:
        logs: List[dict] = []
        if os.path.exists(filename):
            with open(filename, "r") as f:
                try:
                    logs = json.load(f)
                except json.JSONDecodeError:
                    logs = []
        logs.append(entry)
        with open(filename, "w") as f:
            json.dump(logs, f, indent=2)

    def _log_applied_job(self, url: str, title: str, company: str) -> None:
        entry = {
            "url": url,
            "title": title,
            "company": company,
            "applied_at": datetime.now().isoformat(),
        }
        self._append_json_log(self.APPLIED_LOG_FILE, entry)

    def _log_failed_job(self, url: str, title: str, company: str, reason: str) -> None:
        entry = {
            "url": url,
            "title": title,
            "company": company,
            "reason": reason,
            "failed_at": datetime.now().isoformat(),
        }
        self._append_json_log(self.FAILED_LOG_FILE, entry)

    @staticmethod
    def _exceeds_experience_limit(text: str, max_years: int) -> bool:
        pattern = r"\b(?:at least|min(?:imum)?|over)?\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s*(?:of experience)?"
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                if int(m) > max_years:
                    return True
            except ValueError:
                continue
        return False

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login(self) -> None:
        print("[*] Navigating to Dice login page...")
        self.driver.get("https://www.dice.com/dashboard/login")
        try:
            email_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            email_input.send_keys(self.email)

            continue_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Continue']]"))
            )
            continue_btn.click()

            password_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.NAME, "password"))
            )
            password_input.send_keys(self.password)

            signin_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//span[text()='Sign In']]"))
            )
            signin_btn.click()

            print("[+] Login successful.")
            time.sleep(5)
        except Exception as e:
            print(f"[!] Login failed: {e}")
            self.driver.quit()

    # ------------------------------------------------------------------
    # Core application logic
    # ------------------------------------------------------------------
    def _apply_jobs_on_page(self, applied_jobs: Set[str], applied_count: int) -> int:
        buttons = self.driver.find_elements(By.XPATH, "//a[contains(@class, 'inline-flex') and @target='_blank']")
        print(f"[→] Found {len(buttons)} job links on page")

        for button in buttons:
            if applied_count >= self.apply_limit:
                return applied_count

            label = button.text.strip()
            url = button.get_attribute("href")

            if "Applied" in label or not url or "Easy Apply" not in label:
                continue
            if self._is_already_applied(url, applied_jobs):
                continue

            self.driver.execute_script("window.open(arguments[0]);", url)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            time.sleep(4)

            title = "Unknown Title"
            company = "Unknown Company"
            try:
                title = self.driver.find_element(By.TAG_NAME, "h1").text.strip()
            except Exception:
                pass

            try:
                company = self.driver.find_element(By.XPATH, "//span[contains(@class, 'company')]").text.strip()
            except Exception:
                pass

            try:
                desc = self.driver.find_element(By.XPATH, "//div[contains(@class, 'job-description')]").text
                if self._exceeds_experience_limit(f"{title} {desc}", self.max_experience_years):
                    print("    Skipped due to experience requirement")
                    self._log_failed_job(url, title, company, "Experience requirement")
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    continue
            except Exception:
                pass

            try:
                apply_btn = self.driver.find_element(By.XPATH, "//*[@id='applyButton']/apply-button-wc")
                apply_btn.click()
                print("    Clicked Easy Apply")
                time.sleep(2)
            except Exception:
                print("    Easy Apply not found")
                self._log_failed_job(url, title, company, "Easy Apply not found")
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
                continue

            try:
                next_btn = self.driver.find_element(By.XPATH, "//span[text()='Next']")
                next_btn.click()
                time.sleep(2)
            except Exception:
                pass

            try:
                submit_btn = self.driver.find_element(By.XPATH, "//span[text()='Submit']")
                submit_btn.click()
                print("    Submitted Application")
                time.sleep(2)
            except Exception:
                pass

            self._mark_job_as_applied(url)
            self._log_applied_job(url, title, company)
            applied_jobs.add(url)
            applied_count += 1
            print(f"    Applied Count: {applied_count}/{self.apply_limit}")

            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            time.sleep(1)

        return applied_count

    def apply_all(self) -> None:
        applied_jobs = self._load_applied_jobs()
        applied_count = 0

        self.driver.get(self.filtered_jobs_url)
        time.sleep(4)

        while applied_count < self.apply_limit:
            applied_count = self._apply_jobs_on_page(applied_jobs, applied_count)
            if applied_count >= self.apply_limit:
                break
            try:
                next_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//span[@role='link' and @aria-label='Next']"))
                )
                if "cursor-not-allowed" in next_btn.get_attribute("class"):
                    print("[✓] Reached last page.")
                    break
                self.driver.execute_script("arguments[0].click();", next_btn)
                print("[→] Clicked Next")
                time.sleep(5)
            except Exception as e:
                print(f"[✓] Could not move to next page: {e}")
                break

        print("[✓] Finished job applications.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        self.login()
        self.apply_all()
        self.driver.quit()


if __name__ == "__main__":
    agent = DiceAutoApplyAgent()
    agent.run()

