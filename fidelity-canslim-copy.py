from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
import subprocess
import pyautogui
pyautogui.FAILSAFE = False # Avoid killing script on mouse movement
import pyperclip
import pandas as pd
from datetime import datetime, time, timedelta
import pytz
from time import sleep
from io import StringIO
import os
import json

# Load stock symbols
def fetch_tickers():
    print('Fetching tickers...')
    url = "https://www.sec.gov/files/company_tickers.json"
    firefox_options = webdriver.FirefoxOptions()
    firefox_options.add_argument('--headless')
    driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=firefox_options)
    driver.get(url)
    raw_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Raw')]")))
    raw_button.click()
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "pre")))
    sec_text = driver.find_element(By.TAG_NAME, "pre").text
    driver.close()
    data = json.loads(sec_text)
    tickers = [item["ticker"].replace('-', '/') for item in data.values()]
    print(f'{len(tickers)} fetched from SEC')
    return tickers

# Simulate pressing tab n times
def tab(n=1):
    if n > 0:
        for _ in range(n):
            pyautogui.press('tab')
    else:
        for _ in range(-n):
            pyautogui.hotkey('shift', 'tab')

# Simulate pasting from clipboard
def paste(s):
    pyperclip.copy(s)
    pyautogui.hotkey('command', 'v')

# Copy and return text on page 
def get_page_text():
    page = ''
    while not len(page):
        pyautogui.hotkey('command', 'a')
        sleep(.05)
        pyautogui.hotkey('command', 'c')
        sleep(.05)
        page = pyperclip.paste()
        if not page:
            page = ''
            continue
        if len(page):
            break
    return page

# Simulate waiting for text to appear or disappear onto or from page
def wait_for(s, repeat_hotkey='a', max_seconds=None, appear=True):
    # Returns boolean if max_seconds defined, None otherwise
    copied = ''
    if max_seconds:
        a = datetime.today().time()
        b = datetime.today().time()
        while datetime.combine(datetime.today(), b) - datetime.combine(datetime.today(), a) < timedelta(seconds=max_seconds):
            pyautogui.hotkey('command', repeat_hotkey)
            pyautogui.hotkey('command', 'c')
            copied = pyperclip.paste()
            if not copied:
                copied = ''
                b = datetime.today().time()
                continue
            if appear and s in copied:
                return True
            elif not appear and s not in copied:
                return True
            b = datetime.today().time()
        return False
    else:
        while (appear and s not in copied) or (not appear and s in copied):
            pyautogui.hotkey('command', repeat_hotkey)
            pyautogui.hotkey('command', 'c')
            copied = pyperclip.paste()
            if not copied:
                copied = ''
    return None if not max_seconds else True if appear else False

# Log into Fidelity using shortkeys extension to fill form
def login(browser='Google Chrome'):
    login_url = 'https://digital.fidelity.com/prgw/digital/login/full-page'
    subprocess.Popen(["open", "-na", browser, "--args", "--new-window", login_url])
    wait_for('Username')
            
    pyautogui.hotkey(shortkeys['LOGIN_BUTTON'])

    if not wait_for(login_url, 'l', appear=False, max_seconds=60):
        pyautogui.hotkey('command', 'w')
        login(browser=browser)
    logged_in_url = 'https://digital.fidelity.com/ftgw/digital/portfolio/summary'
    wait_for(logged_in_url, 'l')

# Function to convert string values to numeric, removing commas
def to_numeric(val):
    if isinstance(val, str):
        val = val.replace(',', '')
        try:
            if '(' in val and ')' in val:
                return -float(val.replace('(', '').replace(')', ''))
            return float(val)
        except ValueError:
            return val  # Return the original value if it's not convertible
    return val

# True if ROE > 17%
def check_roe(income_statement, balance_sheet):
    net_income = income_statement.loc["Net income"]
    shareholders_equity = balance_sheet.loc["Shareholder's equity total"]
    
    roe = (net_income / shareholders_equity) * 100
    return (roe > 17).all()

# True if Quarterly EPS has grown 18% compared to 1Y ago
def quarterly_eps_growth(df):
    recent_quarter = df.iloc[0]
    one_year_ago = df[(df["Report date"] >= recent_quarter["Report date"] - timedelta(days=410)) & 
                      (df["Report date"] <= recent_quarter["Report date"] - timedelta(days=320))]
    if not one_year_ago.empty:
        return recent_quarter["GAAP EPS ($)"] > one_year_ago.iloc[0]["GAAP EPS ($)"] * 1.18
    return False

# True if Quarterly Sales have grown 25% compared to 1Q ago
def quarterly_sales_growth(sales):
    return sales[0] > sales[1] * 1.25

# True if Quarterly Sales have accelerated for last 3Q
def quarterly_sales_acceleration(sales):
    return (sales[0] > sales[1]) and (sales[1] > sales[2]) and (sales[2] > sales[3])

# True if Annual Earnings has grown 25% from 4Y ago or earliest date
def annual_earnings_growth(income_statement):
    # Check if there are at least 5 columns (excluding the first column)
    if len(income_statement.columns) >= 5:
        recent_earnings_col = income_statement.columns[1]  # Second column
        compare_earnings_col = income_statement.columns[4]  # Fifth column
    else:
        recent_earnings_col = income_statement.columns[1]  # Second column
        compare_earnings_col = income_statement.columns[-1]  # Last column

    # Convert the columns to strings for indexing
    recent_earnings_col = str(recent_earnings_col)
    compare_earnings_col = str(compare_earnings_col)

    recent_earnings = income_statement.loc["Net income", recent_earnings_col]
    compare_earnings = income_statement.loc["Net income", compare_earnings_col]
    
    return recent_earnings > compare_earnings * 1.25

# True if Debt-to-Equity Ratio is decreasing for last 3Y
def debt_to_equity_decreasing(balance_sheet):
    debt_to_equity = [total_debt / equity for total_debt, equity in zip(
        balance_sheet.loc["Debt in current liabilities"] + balance_sheet.loc["Long-term debt"],
        balance_sheet.loc["Shareholder's equity total"]
    )]
    return (debt_to_equity[0] < debt_to_equity[1]) and (debt_to_equity[1] < debt_to_equity[2])

# True if Annual Cash Flow / Shares > Annual EPS by at least 20%
def cash_flow_vs_eps(cash_flow, earnings_df, shares):
    annual_cash_flow = cash_flow.loc["Operating activities – net cash flow"]
    annual_eps = earnings_df[earnings_df["Report date"].dt.year == earnings_df["Report date"].dt.year.max()]["GAAP EPS ($)"]
    cash_flow_per_share = annual_cash_flow / shares
    if not annual_eps.empty:
        return cash_flow_per_share.iloc[0] > annual_eps.iloc[0] * 1.20
    return False

today = datetime.now(pytz.timezone('US/Eastern'))
current_date = today.strftime("%Y-%m-%d")

# Ensure shortkeys extension is configured on both browsers
shortkeys = {
    'USERNAME_INPUT': ['ctrl', 'l'], 
    'PASSWORD_INPUT': ['ctrl', 'option', 'l'], 
    'LOGIN_BUTTON': ['ctrl', 'b'], 
    'LOGOUT_BUTTON': ['ctrl', 'shift', 'l'], 
    'CANCEL_ORDER': ['ctrl', 'c'], 
    'COPY_SECTOR': ['ctrl', 'option', 's'], 
    'VIEW_EARNINGS': ['ctrl', 'option', 'e'], 
    'EXPAND_EARNINGS': ['ctrl', 'shift', 'e'], 
    'COPY_EARNINGS': ['ctrl', 'option', 'shift', 'e'], 
    'CLOSE_EARNINGS': ['command', 'option', 'e'], 
    'VIEW_INSTITUTIONS': ['ctrl', 'option', 'i'], 
    'VIEW_FINANCIALS': ['ctrl', 'option', 'f'], 
    'VIEW_ANNUAL_ASSETS': ['ctrl', 'option', 'b'], 
    'COPY_ASSETS': ['ctrl', 'shift', 'option', 'b'], 
    'VIEW_INCOME': ['ctrl', 'option', 'p'], 
    'COPY_INCOME': ['ctrl', 'shift', 'option', 'p'], 
    'VIEW_QUARTERLY_INCOME': ['ctrl', 'option', 'q'], 
    'VIEW_CASH_FLOW': ['ctrl', 'option', 'c'], 
    'COPY_CASH_FLOW': ['ctrl', 'shift', 'option', 'c'], 
    'CLOSE_STATISTICS': ['command', 'option', 'i'], 
    'COPY_PRICE': ['ctrl', 'p'], 
    'COPY_VOLUME': ['ctrl', 'v'], 
    'COPY_AVG_VOLUME': ['ctrl', 'shift', 'v'], 
    'COPY_52WK_LOW': ['ctrl', 'shift', 'p'], 
    'COPY_52WK_HIGH': ['command', 'shift', 'p'], 
    'COPY_1D_RANGE': ['ctrl', 'shift', 'd'],
}

results = []

tickers = fetch_tickers()
#tickers = tickers[tickers.index('GM'):]
login()

for k in range(len(tickers)):
    try:
        ticker = tickers[k]
        ticker_start_time = datetime.now()

        research_urls = {
            'Overview': f'https://digital.fidelity.com/prgw/digital/research/quote/dashboard/summary?symbol={ticker}',
            'Dividends & Earnings': f'https://digital.fidelity.com/prgw/digital/research/quote/dashboard/dividends-earnings?symbol={ticker}',
            'Statistics': f'https://digital.fidelity.com/prgw/digital/research/quote/dashboard/key-statistics?symbol={ticker}',
            }

        research_items = {
            'Price': '',
            'Volume': '',
            '10/90d Avg Volume': '',
            '1d High': '',
            '1d Low': '',
            '52wk High': '',
            '52wk Low': '',
            'Sector': '',
            'Industry': '',
            'Company Location': '',
            'Curr Quarter Institutional Change': '',
            'Last Quarter Institutional Change': '',
            }

        page_titles = ['Overview', 'Dividends & Earnings', 'Statistics']
        search_bar_text = ''

        for i in range(len(page_titles)):
            title = page_titles[i]
            research_url = research_urls[title]
            search_bar_text = ''
            while research_url not in search_bar_text:
                pyautogui.hotkey('command', 'l')
                sleep(.05)
                paste(research_url)
                search_bar_text = get_page_text()
            pyautogui.press('enter')
            if k == 0:
                if i != len(page_titles) - 1:
                    pyautogui.hotkey('command', 't')
                else:
                    pyautogui.hotkey('command', 'option', 'right')
            else:
                pyautogui.hotkey('command', 'option', 'right')
            sleep(0.05)
            

        skip = False
        for i in range(len(page_titles)):
            title = page_titles[i]
            wait_for('Market insights')
            page = get_page_text()
            if not page:
                page = ''
            if 'No matches found' in page:
                print(f'Skipping {ticker} (invalid ticker)')
                skip = True
                pyautogui.hotkey('command', 'option', 'right')
                continue
            if 'Top holdings' in page:
                print(f'Skipping {ticker} (index fund)')
                skip = True
                pyautogui.hotkey('command', 'option', 'right')
                continue

            if skip:
                pyautogui.hotkey('command', 'option', 'right')
                continue
            else:
                if title == 'Overview':
                    if wait_for('Opens in a new window', max_seconds=5):
                        page = get_page_text()
                        page_rows = page.split('\n')
                        sector, industry, hq = '', '', ''
                        sector_found, industry_found, hq_found = False, False, False
                        for row in page_rows:
                            if sector_found and industry_found and hq_found:
                                break
                            row_stripped = row.strip()
                            if row_stripped.startswith('Sector') and row_stripped.endswith('Opens in a new window'):
                                sector = row_stripped.replace('Sector', '').replace('Opens in a new window', '')
                                research_items['Sector'] = sector
                                sector_found = True
                            if row_stripped.startswith('Industry') and row_stripped.endswith('Opens in a new window'):
                                industry = row_stripped.replace('Industry', '').replace('Opens in a new window', '')
                                research_items['Industry'] = industry
                                industry_found = True
                            if row_stripped.startswith('Company Location'):
                                hq = row_stripped[row_stripped.index('Company Location') + len('Company Location'):]
                                research_items['Company Location'] = hq
                        pyautogui.hotkey(shortkeys['COPY_PRICE'])
                        sleep(.05)
                        curr_price = pyperclip.paste()
                        research_items['Price'] = curr_price
                        
                        pyautogui.hotkey(shortkeys['COPY_VOLUME'])
                        sleep(.05)
                        curr_volume = pyperclip.paste().strip()
                        research_items['Volume'] = curr_volume
                        pyautogui.hotkey(shortkeys['COPY_AVG_VOLUME'])
                        sleep(.05)
                        avg_volume = pyperclip.paste().strip()
                        research_items['10/90d Avg Volume'] = avg_volume
                        pyautogui.hotkey(shortkeys['COPY_1D_RANGE'])
                        sleep(.05)
                        range_price_1d = pyperclip.paste().split('$')[1:]
                        low_price_1d = '$' + range_price_1d[0]
                        high_price_1d = '$' + range_price_1d[1]
                        research_items['1d Low'] = low_price_1d
                        research_items['1d High'] = high_price_1d
                        pyautogui.hotkey(shortkeys['COPY_52WK_LOW'])
                        sleep(.05)
                        low_price_52wk = pyperclip.paste()
                        research_items['52wk Low'] = low_price_52wk
                        pyautogui.hotkey(shortkeys['COPY_52WK_HIGH'])
                        sleep(.05)
                        high_price_52wk = pyperclip.paste()
                        research_items['52wk High'] = high_price_52wk
                        #print(f'Price: {curr_price}')
                        #print(f'1 Day Range: {low_price_1d} Low, {high_price_1d} High')
                        #print(f'52 Week Range: {low_price_52wk}, {high_price_52wk}')
                        #print(f'Volume: {curr_volume}, 10/90 Day Avg Volume: {avg_volume}')
                        
                    elif len(sector) == 0 or len(industry) == 0 or 'Skip to Main Content' in sector:
                        print(f'Skipping {ticker} (no sector/industry)')
                        skip = True
                        continue
                    #print(f'{ticker}: {sector} ({industry}) - {hq}')

                elif title == 'Dividends & Earnings':
                    wait_for('Earnings')
                    page = get_page_text()
                    if 'Fidelity Investments does not make additional research' in page or 'There are no reports available.' in page or 'currently does not have earnings' in page or 'Fundamental Analysis is not available' in page or 'No Fundamental Events' in page:
                        print(f'Skipping {ticker} (no earnings)')
                        skip = True
                        pyautogui.hotkey('command', 'option', 'right')
                        continue
                    while not wait_for('Earnings Metrics', max_seconds=10):
                        pyautogui.hotkey('command', 'r')
                        sleep(2)
                    pyautogui.hotkey(shortkeys['VIEW_EARNINGS'])
                    sleep(1)
                    pyautogui.hotkey(shortkeys['EXPAND_EARNINGS'])
                    sleep(1)
                    pyautogui.hotkey(shortkeys['COPY_EARNINGS'])
                    sleep(1)
                    earnings_text = pyperclip.paste().replace('\n                \n                    \n                    ', '')
                    earnings_text = earnings_text.replace('\n                    \n                        \n                    \n                            \n                About StarMine from Refinitiv SmartEstimate\n                    \n                    The StarMine from Refinitiv SmartEstimate seeks to be more accurate than the consensus EPS by calculating an analyst\'s accuracy and timeliness of an analyst\'s estimates into its estimate of earnings.', '')
                    header_start = earnings_text.find('"Quarter","Report date"')
                    earnings_text = earnings_text[header_start:]
                    earnings_df = pd.read_csv(StringIO(earnings_text))
                    earnings_df.replace('--', pd.NA, inplace=True)
                    try:
                        earnings_df.dropna(subset=['GAAP EPS ($)'], inplace=True)
                        earnings_df['Report date'] = pd.to_datetime(earnings_df['Report date'])
                        earnings_df['GAAP EPS ($)'] = earnings_df['GAAP EPS ($)'].astype(float)
                    except:
                        print(f'Skipping {ticker} (no GAAP earnings)')
                        skip = True
                        pyautogui.hotkey('command', 'option', 'right')

                    try:
                        earnings_df.dropna(subset=['GAAP EPS ($)'], inplace=True)
                        earnings_df['Report date'] = pd.to_datetime(earnings_df['Report date'])
                        earnings_df['GAAP EPS ($)'] = earnings_df['GAAP EPS ($)'].astype(float)
                    except:
                        print(f'Skipping {ticker} (no GAAP earnings)')
                        skip = True
                        pyautogui.hotkey('command', 'option', 'right')
                                    
                elif title == 'Statistics':
                    wait_for('Market insights')
                    page = ''
                    institution_fails = 0
                    while 'Institutional ownership details' not in page and 'Institutional stock & mutual fund ownership' not in page:
                        if institution_fails >= 5:
                            print(f'Skipping {ticker} (no institutions)')
                            skip = True
                            pyautogui.hotkey('command', 'option', 'right')
                            continue
                        while not wait_for('Ownership & insiders', max_seconds=10):
                            pyautogui.hotkey('command', 'r')
                            institution_fails += 1
                            sleep(2)
                        pyautogui.hotkey(shortkeys['VIEW_INSTITUTIONS'])
                        if wait_for('Institutional ownership details', max_seconds=10):
                            if wait_for('Institutional stock & mutual fund ownership', max_seconds=10):
                                page = get_page_text()
                                if not page or 'Institutional ownership details' not in page and 'Institutional stock & mutual fund ownership' not in page:
                                    page = ''
                                    pyautogui.hotkey('command', 'r')
                                    institution_fails += 1
                                    sleep(2)
                                    continue
                                break
                        
                    page = page[page.index('Institutional ownership details'):]#page.index('Institutional stock & mutual fund ownership')]
                    institutions_text = page[page.index('Change in ownership'):].split('\n')[1]
                    institutions_curr_qtr_chg = institutions_text[:institutions_text.index('%') + 1]
                    institutions_last_qtr_chg = institutions_text[institutions_text.index('%') + 1:]
                    
                    research_items['Curr Quarter Institutional Change'] = institutions_curr_qtr_chg
                    research_items['Last Quarter Institutional Change'] = institutions_last_qtr_chg
                    pyautogui.hotkey('command', 'r')

                    wait_for('Balance sheet')
                    pyautogui.hotkey(shortkeys['VIEW_FINANCIALS'])
                    wait_for('Assets')
                    pyautogui.hotkey(shortkeys['VIEW_ANNUAL_ASSETS'])
                    sleep(.25)
                    wait_for('Assets')
                    pyautogui.hotkey(shortkeys['COPY_ASSETS'])
                    balance_sheet = pd.read_csv(StringIO(pyperclip.paste()), header=0, index_col=0).applymap(to_numeric)
                    shares_outstanding = balance_sheet.loc["Shareholder's equity total"].tolist()
                    #print(f'Balance sheet:\n{balance_sheet}')

                    pyautogui.hotkey(shortkeys['VIEW_INCOME'])
                    wait_for('Net income')
                    pyautogui.hotkey(shortkeys['COPY_INCOME'])
                    income_statement_yr = pd.read_csv(StringIO(pyperclip.paste()), header=0, index_col=0).applymap(to_numeric)
                    #print(f'Net income:\n{income_statement_yr}')
                    pyautogui.hotkey(shortkeys['VIEW_QUARTERLY_INCOME'])
                    sleep(.25)
                    wait_for('Net income')
                    pyautogui.hotkey(shortkeys['COPY_INCOME'])
                    income_statement_qtr = pd.read_csv(StringIO(pyperclip.paste()), header=0, index_col=0).applymap(to_numeric)
                    sales_quarterly = income_statement_qtr.loc["Sales/turnover (net)"].tolist()
                    #print(f'Quarterly net income:\n{income_statement_yr}')
                    pyautogui.hotkey(shortkeys['VIEW_CASH_FLOW'])
                    wait_for('Operating activities')
                    pyautogui.hotkey(shortkeys['COPY_CASH_FLOW'])
                    cash_flow = pd.read_csv(StringIO(pyperclip.paste()), header=0, index_col=0).applymap(to_numeric)
                    #print(f'Operating activities:\n{cash_flow}')                

                pyautogui.hotkey('command', 'option', 'right')

    except:
        print(f'Skipping {ticker} due to parsing error')
            
    if skip:
        continue

    try:
        # Metrics
        metrics = {
            'Symbol': False,
            'Sector': False,
            'Industry': False,
            'ROE > 17%': check_roe(income_statement_yr, balance_sheet),
            'Quarterly EPS Growth 18%': quarterly_eps_growth(earnings_df),
            'Quarterly Sales Growth 25%': quarterly_sales_growth(sales_quarterly),
            'Quarterly Sales Acceleration': quarterly_sales_acceleration(sales_quarterly),
            'Annual Earnings Growth 25%': annual_earnings_growth(income_statement_yr),
            'Debt-to-Equity Ratio Decreasing': debt_to_equity_decreasing(balance_sheet),
            'Annual Cash Flow / Shares > Annual EPS by 20%': cash_flow_vs_eps(cash_flow, earnings_df, shares_outstanding),
            'Accelerating Institutional Ownership': len(research_items['Curr Quarter Institutional Change']) > 1 and len(research_items['Last Quarter Institutional Change']) > 1 and float(research_items['Curr Quarter Institutional Change'][:-1].replace(',', '')) >= float(research_items['Curr Quarter Institutional Change'][:-1].replace(',', '')) > 0,
            #'New High or Within 5%': len(research_items['Price']) > 1 and len(research_items['52wk High']) > 1 and float(research_items['Price'][1:].replace(',', '')) >= .95 * float(research_items['52wk High'][1:research_items['52wk High'].index(' ')].replace(',', '')),
            'Passes': False,
        }

        # Count the number of CAN SLIM passes
        pass_count = sum(metrics.values())
        print(f'{ticker} passes {pass_count} of {len([metric for metric in metrics if metric not in ["Symbol", "Sector", "Industry", "Passes"]])} tests')
        
        elapsed_time = (datetime.now() - ticker_start_time).total_seconds()
        print(f'Time to fetch data for {ticker}: {round(elapsed_time, 3)}s\n')
        pyautogui.hotkey('command', 'l')

        metrics['Symbol'] = ticker
        metrics['Sector'] = research_items['Sector']
        metrics['Industry'] = research_items['Industry']
        metrics['Passes'] = pass_count

        results.append(metrics)
        results_df = pd.DataFrame(results)
        results_df.sort_values(by='Passes', ascending=False, inplace=True)
        results_df.to_csv(f'canslim-metrics-{current_date}.csv', index=False)

    except Exception as e:
        print(f'Skipping {ticker} on error {e}')
