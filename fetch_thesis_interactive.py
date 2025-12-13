import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ===============================
# CONFIGURE BEFORE RUNNING
# ===============================
CHROME_PROFILE_PATH = ".chrome_profile"    # <-- adjust if needed
PROFILE_NAME = "Default"

MASTER_URL    = "https://apd.sgh.waw.pl/catalogue/search/simple/?query=rubach&type=master&limit=200"
BACHELOR_URL  = "https://apd.sgh.waw.pl/catalogue/search/simple/?query=rubach&type=licentiate&limit=200"

BACHELOR_EN_OVERRIDE = ["Yoshiharu Sato", "Sviatlana Buben", "Miłosz Janas"]

OUTPUT_JSON = "_data/students.json"


# ===============================
# Setup Chrome with your profile
# ===============================
options = Options()
options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
options.add_argument(f"--profile-directory={PROFILE_NAME}")
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
driver = webdriver.Chrome(options=options)


# ===============================
#  STEP 1 — Manual LOGIN FIRST
# ===============================
driver.get("https://apd.sgh.waw.pl")
print("\n🔐 Please login using your Microsoft Account (MFA supported).")
print("💡 After login completes, press ENTER to continue...")
input("   >> Press ENTER after login: ")
print("✨ Login confirmed — starting scraping...\n")
time.sleep(1)

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


import re

import re

def extract_year_from_author_td(author_td):
    """
    Given the <td> element containing Author info,
    extract the year from 'Date of diploma exam'.
    """
    try:
        # find all note divs inside the td
        note_divs = author_td.find_elements(By.CSS_SELECTOR, "div.note")

        for div in note_divs:
            try:
                span = div.find_element(By.CSS_SELECTOR, "span.bold")
                if "Date of diploma exam" in span.text:
                    # remove the span text to get the date part
                    full_text = div.text.replace(span.text, "").strip()
                    # extract 4-digit year
                    match = re.search(r"\b(20\d{2})\b", full_text)
                    if match:
                        return match.group(1)
            except:
                continue

        return None  # not found

    except Exception as e:
        print("Error extracting year:", e)
        return None


def extract_author_year_language___fe(author_td):
    """
    Given the <td> containing thesis info,
    return (author_name, year, lang)
    """
    import re
    from selenium.common.exceptions import NoSuchElementException

    author_name = "UNKNOWN"
    year = None
    lang = 'PL'  # default

    try:
        # Loop over all table rows in this td
        rows = author_td.find_elements(By.TAG_NAME, "tr")
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) >= 2:
                label = cells[0].text.strip().lower()
                value = cells[1].text.strip()

                # Author
                if "author" in label or "autor" in label:
                    author_name = value

                # Year / Date of diploma
                elif "date of diploma exam" in label or "data złożenia" in label:
                    match = re.search(r"\b(20\d{2})\b", value)
                    if match:
                        year = match.group(1)

                # Language
                elif "language" in label or "język pracy" in label:
                    val_upper = value.upper()
                    if "EN" in value:
                        lang = "EN"

    except NoSuchElementException:
        pass
    if author_name in BACHELOR_EN_OVERRIDE:
        lang = "EN"
    return author_name, year, lang


def extract_author_and_year(driver):
    """
    Given the <td> containing Author info,
    return (author_name, year)
    """
    author_name = None
    year = None
    lang = 'PL'

    author_td = driver.find_element(
        By.XPATH,
        "//td[contains(text(),'Author') or contains(text(),'Autor')]/following-sibling::td"
    )
    # Extract author name
    try:
        a = author_td.find_element(By.CSS_SELECTOR, "div.td.padding-0 a")
        author_name = a.text.strip()
    except:
        author_name = "UNKNOWN"

    try:
        note_divs = author_td.find_elements(By.CSS_SELECTOR, "div.note")
        for div in note_divs:
            try:
                span = div.find_element(By.CSS_SELECTOR, "span.bold")
                if "Date of diploma exam" or "Data złożenia" in span.text:
                    full_text = div.text.replace(span.text, "").strip()
                    match = re.search(r"\b(20\d{2})\b", full_text)
                    if match:
                        year = match.group(1)
            except:
                continue
    except:
        year = None

    try:
        # Find the table cell containing Language / Język pracy
        lang_td = driver.find_element(
            By.XPATH,
            "//td[contains(text(),'Language of the thesis') or contains(text(),'Język pracy')]/following-sibling::td"
        )
        lang_text = lang_td.text.strip()
        if 'EN' in lang_text:
            lang = 'EN'
        elif 'PL' in lang_text:
            lang = 'PL'
    except:
        lang = 'PL'

    return author_name, year, lang


def extract_list(url, category_label):
    print(f"\n📄 Loading {category_label} thesis list...")
    driver.get(url)

    # ❗ Wait until table is visible
    try:
        table = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
    except:
        print("❌ No table loaded - likely login not maintained")
        return []

    time.sleep(2)  # let JS populate rows

    # 🆕 dynamic loaded rows
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

    print(f"🔎 Found {len(rows)} rows in table")
    results = []

    for r in rows:
        # Look for thesis links
        link = r.find_elements(By.CSS_SELECTOR, "a[href*='diplomas']")
        if not link:
            continue

        link = link[0]
        title = link.text.strip()
        detail_url = link.get_attribute("href")
        print(detail_url, title)

        # Open details
        driver.execute_script("window.open(arguments[0]);", detail_url)
        driver.switch_to.window(driver.window_handles[-1])

        author_name, year, lang = extract_author_and_year(driver)

        results.append({
            "title": title,
            "author": author_name,
            "year": year,
            "url": detail_url,
            "lang": lang,
            "category": category_label
        })

        print(f"  ✔ {year} — {author_name} — {title}")

        # close tab, return to list
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

    return results


# ===============================
# RUN SCRAPING
# ===============================
master_theses   = extract_list(MASTER_URL, "master")
bachelor_theses = extract_list(BACHELOR_URL, "bachelor")

all_data = master_theses + bachelor_theses
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=2, ensure_ascii=False)

print("\n🎉 DONE — Extracted", len(all_data), "theses")
print(f"📁 Saved → {OUTPUT_JSON}\n")
