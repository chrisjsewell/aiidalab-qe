#!/usr/bin/env python
from selenium.webdriver.common.by import By
import time


def test_qe_app_take_screenshot(selenium, url):
    selenium.get(url("http://localhost:8100/apps/apps/quantum-espresso/qe.ipynb"))
    selenium.set_window_size(1920, 985)
    time.sleep(10)
    selenium.get_screenshot_as_file('screenshots/qe-app.png')


def test_qe_app_select_silicon(selenium, url):
    selenium.get(url("http://localhost:8100/apps/apps/quantum-espresso/qe.ipynb"))
    selenium.set_window_size(1920, 985)
    time.sleep(10)
    selenium.find_element(By.CSS_SELECTOR, ".p-TabBar-tab:nth-child(6) > .p-TabBar-tabLabel").click()
    selenium.find_element(By.XPATH, "//option[@value=\'Silicon\']").click()
    selenium.find_element(By.CSS_SELECTOR, ".mod-success:nth-child(4)").click()
    selenium.get_screenshot_as_file('screenshots/qe-app-select-silicon.png')
