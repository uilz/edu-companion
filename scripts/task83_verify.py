#!/usr/bin/env python3
"""
Task #83 浏览器复测 — 验证 secretary 模块功能
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8080")
E2E_USER = os.environ.get("E2E_USER", "admin")
E2E_PASS = os.environ.get("E2E_PASS", "admin123")

SCREENSHOT_DIR = Path("/home/deploy/edu-companion/.browser_screenshots/task83")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class Report:
    def __init__(self):
        self.findings: List[Dict] = []
        self.console_errors: List[Dict] = []
        self.console_warnings: List[Dict] = []
        self.page_errors: List[Dict] = []
        self.network_errors: List[Dict] = []
        self.screenshots: List[str] = []

    def add(self, key: str, ok: bool, detail: str = ""):
        self.findings.append({"key": key, "ok": ok, "detail": detail})

    def summary(self) -> Dict[str, Any]:
        passed = sum(1 for f in self.findings if f["ok"])
        failed = sum(1 for f in self.findings if not f["ok"])
        return {
            "timestamp": datetime.now().isoformat(),
            "total_checks": len(self.findings),
            "passed": passed,
            "failed": failed,
            "findings": self.findings,
            "console_errors_count": len(self.console_errors),
            "console_warnings_count": len(self.console_warnings),
            "page_errors_count": len(self.page_errors),
            "network_errors_count": len(self.network_errors),
            "console_errors_sample": self.console_errors[:5],
            "page_errors_sample": self.page_errors[:5],
            "network_errors_sample": self.network_errors[:5],
            "screenshots": self.screenshots,
        }


def make_driver(width: int = 1440, height: int = 900) -> webdriver.Firefox:
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument(f"--width={width}")
    opts.add_argument(f"--height={height}")
    opts.set_preference("general.useragent.override",
        "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0 EduTask83")
    service = Service(executable_path="/snap/bin/geckodriver")
    driver = webdriver.Firefox(service=service, options=opts)
    driver.set_window_size(width, height)
    driver.set_page_load_timeout(30)
    return driver


def attach_listeners(driver):
    js = """
    (function() {
      if (window.__eduTask83) return;
      window.__eduTask83 = { errors: [], warns: [], pageErrors: [], netErrors: [] };
      var origError = console.error;
      var origWarn = console.warn;
      console.error = function() {
        try {
          var parts = Array.from(arguments).map(function(a){
            try { return typeof a === 'object' ? JSON.stringify(a) : String(a); }
            catch(e){ return String(a); }
          });
          window.__eduTask83.errors.push(parts.join(' '));
        } catch(e){}
        return origError.apply(console, arguments);
      };
      console.warn = function() {
        try {
          var parts = Array.from(arguments).map(function(a){
            try { return typeof a === 'object' ? JSON.stringify(a) : String(a); }
            catch(e){ return String(a); }
          });
          window.__eduTask83.warns.push(parts.join(' '));
        } catch(e){}
        return origWarn.apply(console, arguments);
      };
      window.addEventListener('error', function(e) {
        window.__eduTask83.pageErrors.push((e.message||'') + ' @ ' + (e.filename||'') + ':' + (e.lineno||''));
      });
      window.addEventListener('unhandledrejection', function(e) {
        window.__eduTask83.pageErrors.push('unhandledrejection: ' + (e.reason||''));
      });
      var origFetch = window.fetch;
      if (origFetch) {
        window.fetch = function() {
          var p = origFetch.apply(this, arguments);
          p.catch(function(err){
            try { window.__eduTask83.netErrors.push('fetch: ' + (err.message||err)); } catch(e){}
          });
          return p;
        };
      }
    })();
    """
    try:
        driver.execute_script(js)
    except Exception:
        pass


def collect_logs(driver, report: Report):
    try:
        logs = driver.execute_script(
            "return {e: window.__eduTask83.errors||[], w: window.__eduTask83.warns||[], "
            "p: window.__eduTask83.pageErrors||[], n: window.__eduTask83.netErrors||[]};"
        )
        report.console_errors = logs.get("e", [])
        report.console_warnings = logs.get("w", [])
        report.page_errors = logs.get("p", [])
        report.network_errors = logs.get("n", [])
    except Exception:
        pass


def login(driver, report: Report):
    """登录并跳转至首页"""
    try:
        driver.get(f"{BASE_URL}/login")
        time.sleep(1)
        # 尝试找 username/password 字段
        try:
            u = driver.find_element(By.NAME, "username") if driver.find_elements(By.NAME, "username") else driver.find_element(By.CSS_SELECTOR, "input[type='text']")
        except NoSuchElementException:
            u = driver.find_element(By.CSS_SELECTOR, "input[name*='user'], input[name*='account']")
        u.send_keys(E2E_USER)
        try:
            p = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        except NoSuchElementException:
            p = driver.find_element(By.NAME, "password")
        p.send_keys(E2E_PASS)
        try:
            btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except NoSuchElementException:
            btn = driver.find_element(By.XPATH, "//button[contains(text(),'登录') or contains(text(),'Login')]")
        btn.click()
        time.sleep(2)
        report.add("login", True, "登录成功")
    except Exception as e:
        report.add("login", False, f"登录失败: {e}")
        return False
    return True


def visit_and_screenshot(driver, path: str, name: str, report: Report, wait_sec: float = 2.0):
    """访问页面并截图"""
    try:
        driver.get(f"{BASE_URL}{path}")
        time.sleep(wait_sec)
        WebDriverWait(driver, 8).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(0.5)
        ss = SCREENSHOT_DIR / f"{name}.png"
        driver.save_screenshot(str(ss))
        report.screenshots.append(str(ss))
        report.add(f"visit_{name}", True, f"已截图 {path}")
        return True
    except Exception as e:
        report.add(f"visit_{name}", False, f"访问失败 {path}: {e}")
        return False


def main():
    report = Report()
    driver = make_driver()
    attach_listeners(driver)
    try:
        # 1. 登录
        if not login(driver, report):
            print(json.dumps(report.summary(), ensure_ascii=False, indent=2))
            driver.quit()
            return 1

        # 2. 访问首页
        visit_and_screenshot(driver, "/", "home", report, wait_sec=2.0)

        # 3. 访问 secretary 主面板
        visit_and_screenshot(driver, "/secretary", "secretary_main", report, wait_sec=3.0)

        # 4. 访问 secretary 设置
        visit_and_screenshot(driver, "/secretary/settings", "secretary_settings", report, wait_sec=2.0)

        # 5. 测试移动断点
        driver.set_window_size(390, 800)
        time.sleep(1)
        visit_and_screenshot(driver, "/secretary", "secretary_mobile", report, wait_sec=2.0)

    finally:
        collect_logs(driver, report)
        driver.quit()

    # 输出报告
    summary = report.summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 and summary["console_errors_count"] == 0 and summary["page_errors_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
