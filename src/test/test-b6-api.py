#!/usr/bin/env python3
"""
B6 Core Business API Test Suite
Kiểm thử tất cả các endpoint của B6 API
"""

import requests
import json
import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import sys

# Cấu hình
BASE_URL = "http://localhost:4010"
TIMEOUT = 10

# Màu sắc cho terminal
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

def print_header(text: str):
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.CYAN}{text}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.NC}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.NC}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.NC}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.NC}")

# Load mock data
def load_mock_data() -> Dict:
    with open('data/mock-data.json', 'r', encoding='utf-8') as f:
        return json.load(f)

MOCK_DATA = load_mock_data()

# ============================================================
# Test Result Class
# ============================================================
@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    response_time_ms: float = 0.0

# ============================================================
# Test Suite
# ============================================================
class B6APITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzY29wZSI6ImFjY2VzczpyZWFkIiwiZ2F0ZUlkcyI6WyJMT0JCWV8wMSJdfQ.signature'  # Thêm dòng này
        })
        self.results: list[TestResult] = []
    
    def _request(self, method: str, path: str, data: Optional[Dict] = None, 
                 params: Optional[Dict] = None) -> tuple[Optional[Dict], float, int]:
        url = f"{self.base_url}{path}"
        start_time = time.time()
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, params=params, timeout=TIMEOUT)
            else:
                response = self.session.post(url, json=data, timeout=TIMEOUT)
            elapsed_ms = (time.time() - start_time) * 1000
            
            response_data = None
            if response.text:
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
            return response_data, elapsed_ms, response.status_code
        except requests.exceptions.Timeout:
            elapsed_ms = (time.time() - start_time) * 1000
            return None, elapsed_ms, 408
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return {"error": str(e)}, elapsed_ms, 500
    
    def add_result(self, name: str, passed: bool, message: str = "", response_time_ms: float = 0.0):
        result = TestResult(name, passed, message, response_time_ms)
        self.results.append(result)
        if passed:
            print_success(f"{name} ({response_time_ms:.2f}ms)")
        else:
            print_error(f"{name} - {message}")
    
    # ============================================================
    # Test 1: Health Check
    # ============================================================
    def test_health_check(self):
        name = "GET /health"
        response_data, elapsed_ms, status_code = self._request('GET', '/health')
        
        if status_code == 200 and response_data:
            expected_fields = ['status', 'components', 'timestamp']
            passed = all(field in response_data for field in expected_fields)
            self.add_result(name, passed, f"Missing fields: {response_data}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 2: Access Check - ALLOW
    # ============================================================
    def test_access_check_allow(self):
        name = "POST /access/check - ALLOW"
        payload = {
            "cardId": "CARD_12345",
            "gateId": "LOBBY_01",
            "correlationId": str(uuid.uuid4()),
            "direction": "IN",
            "timestamp": "2026-06-15T10:30:00Z"
        }
        response_data, elapsed_ms, status_code = self._request('POST', '/access/check', payload)
        
        if status_code == 200 and response_data:
            passed = response_data.get('decision') in ['ALLOW', 'DENY']
            self.add_result(name, passed, f"Decision: {response_data.get('decision')}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 3: Access Check - Idempotency (Duplicate)
    # ============================================================
    def test_access_check_idempotency(self):
        correlation_id = str(uuid.uuid4())
        payload = {
            "cardId": "CARD_12345",
            "gateId": "LOBBY_01",
            "correlationId": correlation_id,
            "timestamp": "2026-06-15T10:30:00Z"
        }
        
        # First request
        response1, elapsed1, status1 = self._request('POST', '/access/check', payload)
        
        # Second request (duplicate)
        response2, elapsed2, status2 = self._request('POST', '/access/check', payload)
        
        name = "POST /access/check - Idempotency"
        if status1 == 200 and status2 in [200, 409]:
            if status2 == 200:
                passed = response1.get('decisionId') == response2.get('decisionId')
            else:
                passed = True  # 409 Conflict is acceptable
            self.add_result(name, passed, f"Status codes: {status1}, {status2}", elapsed2)
        else:
            self.add_result(name, False, f"Status codes: {status1}, {status2}", elapsed2)
    
    # ============================================================
    # Test 4: Get Policy Details
    # ============================================================
    def test_get_policy(self):
        policy_id = "POL_STUDENT_001"
        name = f"GET /policies/access/{policy_id}"
        response_data, elapsed_ms, status_code = self._request('GET', f'/policies/access/{policy_id}')
        
        if status_code in [200, 404]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 5: Get Audit Decision
    # ============================================================
    def test_get_audit_decision(self):
        decision_id = "550e8400-e29b-41d4-a716-446655440000"
        name = f"GET /decisions/{decision_id}"
        response_data, elapsed_ms, status_code = self._request('GET', f'/decisions/{decision_id}')
        
        if status_code in [200, 404]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 6: Cache Invalidate
    # ============================================================
    def test_cache_invalidate(self):
        policy_id = "POL_STUDENT_001"
        name = f"POST /cache/invalidate/{policy_id}"
        _, elapsed_ms, status_code = self._request('POST', f'/cache/invalidate/{policy_id}')
        
        if status_code in [204, 404]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 7: Evaluate Sensor (Queue Async)
    # ============================================================
    def test_evaluate_sensor(self):
        name = "POST /internal/evaluate-sensor"
        payload = MOCK_DATA['sensorEvent']['normal']
        response_data, elapsed_ms, status_code = self._request('POST', '/internal/evaluate-sensor', payload)
        
        if status_code in [200, 202]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 8: Evaluate Detection (AI Vision)
    # ============================================================
    def test_evaluate_detection(self):
        name = "POST /evaluate-detection"
        payload = {
            "correlationId": str(uuid.uuid4()),
            "imageRef": "https://example.com/image.jpg",
            "detectionId": str(uuid.uuid4())
        }
        response_data, elapsed_ms, status_code = self._request('POST', '/evaluate-detection', payload)
        
        if status_code in [200, 422]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 9: Get Access Logs
    # ============================================================
    def test_get_access_logs(self):
        name = "GET /internal/access-logs"
        params = {"from": "2026-06-01T00:00:00Z", "to": "2026-06-30T23:59:59Z", "limit": 10}
        response_data, elapsed_ms, status_code = self._request('GET', '/internal/access-logs', params=params)
        
        if status_code in [200, 404]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 10: Get Gate Status
    # ============================================================
    def test_get_gate_status(self):
        gate_id = "LAB_01"
        name = f"GET /internal/gates/{gate_id}/status"
        response_data, elapsed_ms, status_code = self._request('GET', f'/internal/gates/{gate_id}/status')
        
        if status_code in [200, 404]:
            self.add_result(name, True, f"Status {status_code}", elapsed_ms)
        else:
            self.add_result(name, False, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 11: Access Check - Invalid Request (Missing fields)
    # ============================================================
    def test_access_check_invalid(self):
        name = "POST /access/check - Invalid Request (Missing cardId)"
        payload = {
            "gateId": "LOBBY_01",
            "correlationId": str(uuid.uuid4())
        }
        _, elapsed_ms, status_code = self._request('POST', '/access/check', payload)
        
        passed = status_code in [400, 422]
        self.add_result(name, passed, f"Status {status_code}", elapsed_ms)
    
    # ============================================================
    # Test 12: Health Check - Response Time SLA
    # ============================================================
    def test_health_check_sla(self):
        name = "GET /health - SLA < 500ms"
        _, elapsed_ms, status_code = self._request('GET', '/health')
        
        passed = status_code == 200 and elapsed_ms < 500
        self.add_result(name, passed, f"Response time: {elapsed_ms:.2f}ms", elapsed_ms)
    
    # ============================================================
    # Run all tests
    # ============================================================
    def run_all_tests(self):
        print_header("B6 Core Business API Test Suite")
        print_info(f"Base URL: {self.base_url}")
        
        tests = [
            ("Health Check", self.test_health_check),
            ("Access Check - ALLOW", self.test_access_check_allow),
            ("Access Check - Idempotency", self.test_access_check_idempotency),
            ("Get Policy Details", self.test_get_policy),
            ("Get Audit Decision", self.test_get_audit_decision),
            ("Cache Invalidate", self.test_cache_invalidate),
            ("Evaluate Sensor", self.test_evaluate_sensor),
            ("Evaluate Detection", self.test_evaluate_detection),
            ("Get Access Logs", self.test_get_access_logs),
            ("Get Gate Status", self.test_get_gate_status),
            ("Access Check - Invalid Request", self.test_access_check_invalid),
            ("Health Check SLA", self.test_health_check_sla),
        ]
        
        for name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                self.add_result(name, False, f"Exception: {str(e)}")
        
        self.print_summary()
    
    def print_summary(self):
        print_header("Test Summary")
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"\n  Total Tests: {total}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.NC}")
        print(f"  {Colors.RED}Failed: {total - passed}{Colors.NC}")
        print(f"  Success Rate: {(passed/total)*100:.1f}%\n")
        
        if total - passed > 0:
            print_warning("Failed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"    - {r.name}: {r.message}")
        
        return passed == total

# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='B6 API Test Suite')
    parser.add_argument('--url', default=BASE_URL, help='Base URL of the API')
    args = parser.parse_args()
    
    tester = B6APITester(args.url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)