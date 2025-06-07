# This script automates job applications on multiple portals.
# Use responsibly and ensure it complies with website terms of service.

import os
import json
import difflib
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

# Credentials for different portals
DICE_EMAIL = os.getenv("DICE_EMAIL")
DICE_PASSWORD = os.getenv("DICE_PASSWORD")
LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
INDEED_EMAIL = os.getenv("INDEED_EMAIL")
INDEED_PASSWORD = os.getenv("INDEED_PASSWORD")

with open("config.json", "r") as f:
    config = json.load(f)

APPLY_LIMIT = config.get("apply_limit", 30)
SEARCHES = config.get("searches", [])

# Playwright will be launched later in the main block


def find_and_click(page, keywords):
    """Click the first button or link whose text closely matches any keyword."""
    # direct text match
    for kw in keywords:
        element = page.query_selector(f"button:has-text('{kw}')")
        if not element:
            element = page.query_selector(f"a:has-text('{kw}')")
        if element:
            element.click()
            return True
    # fuzzy match
    buttons = page.query_selector_all("button, a")
    for btn in buttons:
        text = (btn.inner_text() or "").strip().lower()
        for kw in keywords:
            ratio = difflib.SequenceMatcher(None, text, kw.lower()).ratio()
            if ratio > 0.6:
                btn.click()
                return True
    return False


def login_dice(page):
    page.goto("https://www.dice.com/dashboard/login")
    page.fill("input[name=email]", DICE_EMAIL)
    page.click("button:has-text('Continue')")
    page.fill("input[name=password]", DICE_PASSWORD)
    page.click("button:has-text('Sign In')")
    page.wait_for_timeout(5000)


def login_linkedin(page):
    page.goto("https://www.linkedin.com/login")
    page.fill("input#username", LINKEDIN_EMAIL)
    page.fill("input#password", LINKEDIN_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_timeout(5000)


def login_indeed(page):
    page.goto("https://secure.indeed.com/account/login")
    page.fill("#login-email-input", INDEED_EMAIL)
    page.fill("#login-password-input", INDEED_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_timeout(5000)


def generic_apply(page):
    """Attempt to click through a generic application flow."""
    if not find_and_click(page, ["Easy Apply", "Apply on company site", "Apply Now", "Apply"]):
        return False
    page.wait_for_timeout(2000)
    find_and_click(page, [
        "Next",
        "Continue",
        "Submit",
        "Submit application",
        "Finish",
        "Complete",
    ])
    page.wait_for_timeout(2000)
    return True


def apply_job(page, url):
    """Open a job URL and try applying. If external portal opens, try there."""
    page.goto(url)
    page.wait_for_timeout(4000)
    if generic_apply(page):
        return True
    external = page.query_selector("a:has-text('Apply on company site'), a:has-text('Apply Now')")
    if external:
        with page.expect_popup() as pop:
            external.click()
        new_page = pop.value
        new_page.wait_for_load_state()
        success = generic_apply(new_page)
        new_page.close()
        return success
    return False


def search_linkedin(page, query):
    page.goto(f"https://www.linkedin.com/jobs/search/?keywords={query}")
    page.wait_for_timeout(5000)
    anchors = page.query_selector_all("a.base-card__full-link, a.result-card__full-card-link")
    links = []
    for a in anchors:
        href = a.get_attribute("href")
        if href and href not in links:
            links.append(href)
    return links


def search_dice(page, query):
    page.goto(f"https://www.dice.com/jobs?q={query}")
    page.wait_for_timeout(5000)
    anchors = page.query_selector_all("a[href*='/job-detail/']")
    links = []
    for a in anchors:
        href = a.get_attribute("href")
        if href and href not in links:
            links.append(href)
    return links


def search_indeed(page, query):
    page.goto(f"https://www.indeed.com/jobs?q={query}")
    page.wait_for_timeout(5000)
    anchors = page.query_selector_all("a[data-jk]")
    links = []
    for a in anchors:
        href = a.get_attribute("href")
        if href:
            if not href.startswith("http"):
                href = "https://www.indeed.com" + href
            if href not in links:
                links.append(href)
    return links


PORTAL_LOGIN = {
    "dice": login_dice,
    "linkedin": login_linkedin,
    "indeed": login_indeed,
}

PORTAL_SEARCH = {
    "dice": search_dice,
    "linkedin": search_linkedin,
    "indeed": search_indeed,
}


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    logged_in = set()
    applied = 0
    for search in SEARCHES:
        if applied >= APPLY_LIMIT:
            break
        portal = search.get("portal")
        query = search.get("query")
        if not portal or not query:
            continue
        if portal not in logged_in:
            login_func = PORTAL_LOGIN.get(portal)
            if login_func:
                login_func(page)
            logged_in.add(portal)
        search_func = PORTAL_SEARCH.get(portal)
        if not search_func:
            continue
        urls = search_func(page, query)
        for url in urls:
            if applied >= APPLY_LIMIT:
                break
            print(f"Applying to {url} via {portal}")
            if apply_job(page, url):
                applied += 1

    print("Finished applying to jobs")
    browser.close()
