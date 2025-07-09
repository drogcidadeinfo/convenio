import os
import time
import logging
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ─── Config ────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
username = os.getenv("username")
password = os.getenv("password")

if not username or not password:
    raise ValueError("Environment variables 'username' and/or 'password' not set.")

# Calculate dates
today = datetime.today()
report_date = today - timedelta(days=1)
start_date = report_date - timedelta(days=1) if report_date.weekday() == 6 else report_date
inicio = start_date.strftime('%d/%m/%Y')
fim = report_date.strftime('%d/%m/%Y')

# ─── Chrome Setup ──────────────────────────────────────────────
DOWNLOAD_DIR = os.getcwd()

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--force-device-scale-factor=1")
chrome_options.add_argument("--unsafely-treat-insecure-origin-as-secure=http://drogcidade.ddns.net:4647/sgfpod1/Login.pod")
chrome_options.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "plugins.always_open_pdf_externally": True,
    "download.prompt_for_download": False,
})

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# ─── Start Automation ──────────────────────────────────────────
try:
    logging.info("Navigating to login page...")
    driver.get("http://drogcidade.ddns.net:4647/sgfpod1/Login.pod")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_cod_usuario"))).send_keys(username)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "nom_senha"))).send_keys(password)
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "login"))).click()
    WebDriverWait(driver, 10).until(lambda x: x.execute_script("return document.readyState === 'complete'"))

    # Navigate menus
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "sideMenuSearch")))
    driver.find_element(By.ID, "sideMenuSearch").send_keys("Contas Receber ou Recebidas")
    driver.find_element(By.ID, "sideMenuSearch").click()
    driver.implicitly_wait(2)

    driver.find_element(By.CSS_SELECTOR, '[title="Contas Receber ou Recebidas"]').click()
    WebDriverWait(driver, 10).until(lambda x: x.execute_script("return document.readyState === 'complete'"))

    # Fill report filters
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "agrup_fil_2"))).click()
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "sel_contas_2"))).click()
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "tabTabdhtmlgoodies_tabView1_1"))).click()
    
    empresas = ["15", "16", "76"]
    for cod in empresas:
        el = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "cod_empresaEntrada")))
        el.send_keys(cod)
        el.send_keys(Keys.ENTER)

    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "tabTabdhtmlgoodies_tabView1_2"))).click()
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "selecao_periodo_1"))).click()
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "sel2_1"))).click()

    driver.find_element(By.ID, "dat_init").send_keys(inicio)
    driver.find_element(By.ID, "dat_fim").send_keys(fim)
    driver.find_element(By.ID, "saida_1").click()
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "tabTabdhtmlgoodies_tabView1_0"))).click()

    filial = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "cod_filvendEntrada")))
    filial.send_keys("1")
    filial.send_keys(Keys.ENTER)

    time.sleep(2)

    # Trigger download (opens in new window/tab)
    logging.info("Triggering report download...")
    main_window = driver.current_window_handle
    driver.find_element(By.ID, "runReport").click()

    # Force Chrome to download instead of viewing BEFORE visiting URL
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": DOWNLOAD_DIR,
    })
    
    # Wait a moment to ensure setting is applied
    time.sleep(1)
    
    # Grab current URL
    pdf_url = driver.current_url
    logging.info(f"Detected PDF URL: {pdf_url}")
    
    # Revisit the URL to trigger download
    driver.get(pdf_url)
    
    # Wait for download to finish
    logging.info("Waiting for download to complete...")
    time.sleep(10)
    
    # Check for .pdf file
    pdf_files = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.pdf')]
    if pdf_files:
        pdf_files.sort(key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f)))
        latest_pdf = pdf_files[-1]
        full_path = os.path.join(DOWNLOAD_DIR, latest_pdf)
        file_size = os.path.getsize(full_path)
        logging.info(f"Download successful: {latest_pdf} ({file_size} bytes)")
    else:
        logging.error("Download failed. No .pdf file found.")

finally:
    driver.quit()
