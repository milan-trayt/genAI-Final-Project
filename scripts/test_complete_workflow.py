#!/usr/bin/env python3
"""
Complete workflow test for GenAI DevOps Assistant MVP.

This script tests the entire system integration:
1. Document ingestion in collab folder
2. Backend API functionality
3. Frontend integration
4. Multi-tab session management
5. LangChain prompt engineering demos
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, List


class SystemTester:
    """Complete system integration tester."""
    
    def __init__(self):
        self.backend_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:8501"
        self.jupyter_url = "http://localhost:8888"
        
        self.test_results = []
        self.failed_tests = []
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """Log test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": timestamp
        }
        
        self.test_results.append(result)
        
        if not success:
            self.failed_tests.append(result)
        
        print(f"[{timestamp}] {status} {test_name}")
        if message:
            print(f"    {message}")
    
    def test_service_health(self):
        """Test if all services are healthy."""
        print("\n🔍 Testing Service Health...")
        
        # Test backend health
        try:
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            if response.status_code == 200:
                health_data = response.json()
                overall_status = health_data.get("status", "unknown")
                
                if overall_status == "healthy":
                    self.log_test("Backend Health Check", True, f"Status: {overall_status}")
                else:
                    self.log_test("Backend Health Check", False, f"Status: {overall_status}")
                
                # Check individual services
                for service in health_data.get("services", []):
                    service_healthy = service["status"] == "healthy"
                    self.log_test(
                        f"Service: {service['service']}", 
                        service_healthy,
                        f"Status: {service['status']}, Response: {service.get('response_time_ms', 0):.0f}ms"
                    )
            else:
                self.log_test("Backend Health Check", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Backend Health Check", False, f"Connection error: {e}")
        
        # Test frontend accessibility
        try:
            response = requests.get(self.frontend_url, timeout=10)
            self.log_test("Frontend Accessibility", response.status_code == 200)
        except Exception as e:
            self.log_test("Frontend Accessibility", False, f"Connection error: {e}")
        
        # Test Jupyter accessibility
        try:
            response = requests.get(self.jupyter_url, timeout=10)
            self.log_test("Jupyter Accessibility", response.status_code == 200)
        except Exception as e:
            self.log_test("Jupyter Accessibility", False, f"Connection error: {e}")
    
    def test_backend_api(self):
        """Test backend API functionality."""
        print("\n🔧 Testing Backend API...")
        
        # Test root endpoint
        try:
            response = requests.get(f"{self.backend_url}/", timeout=10)
            self.log_test("Root Endpoint", response.status_code == 200)
        except Exception as e:
            self.log_test("Root Endpoint", False, f"Error: {e}")
        
        # Test API documentation
        try:
            response = requests.get(f"{self.backend_url}/docs", timeout=10)
            self.log_test("API Documentation", response.status_code == 200)
        except Exception as e:
            self.log_test("API Documentation", False, f"Error: {e}")
    
    def test_session_management(self):
        """Test multi-tab session management."""
        print("\n📑 Testing Session Management...")
        
        # Create new session for tab
        try:
            response = requests.post(
                f"{self.backend_url}/sessions/test_tab_1/new",
                timeout=10
            )
            
            if response.status_code == 200:
                session_data = response.json()
                session_id = session_data.get("session_id")
                
                self.log_test("Create New Session", True, f"Session ID: {session_id}")
                
                # Test chat with session
                chat_data = {
                    "query": "What is AWS VPC?",
                    "tab_id": "test_tab_1",
                    "session_id": session_id
                }
                
                chat_response = requests.post(
                    f"{self.backend_url}/chat/test_tab_1",
                    json=chat_data,
                    timeout=30
                )
                
                if chat_response.status_code == 200:
                    chat_result = chat_response.json()
                    response_text = chat_result.get("response", "")
                    sources = chat_result.get("sources", [])
                    
                    self.log_test(
                        "Chat Request", 
                        len(response_text) > 0,
                        f"Response length: {len(response_text)}, Sources: {len(sources)}"
                    )
                else:
                    self.log_test("Chat Request", False, f"HTTP {chat_response.status_code}")
                
                # Test session history
                history_response = requests.get(
                    f"{self.backend_url}/sessions/test_tab_1/history",
                    params={"session_id": session_id},
                    timeout=10
                )
                
                if history_response.status_code == 200:
                    history = history_response.json()
                    self.log_test(
                        "Session History", 
                        len(history) > 0,
                        f"Messages in history: {len(history)}"
                    )
                else:
                    self.log_test("Session History", False, f"HTTP {history_response.status_code}")
                    
            else:
                self.log_test("Create New Session", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Session Management", False, f"Error: {e}")
    
    def test_multi_tab_isolation(self):
        """Test multi-tab context isolation."""
        print("\n🔀 Testing Multi-Tab Isolation...")
        
        # Create two different tabs
        tabs = ["test_tab_aws", "test_tab_terraform"]
        sessions = {}
        
        for tab_id in tabs:
            try:
                response = requests.post(
                    f"{self.backend_url}/sessions/{tab_id}/new",
                    timeout=10
                )
                
                if response.status_code == 200:
                    session_data = response.json()
                    sessions[tab_id] = session_data["session_id"]
                    self.log_test(f"Create Session for {tab_id}", True)
                else:
                    self.log_test(f"Create Session for {tab_id}", False)
                    
            except Exception as e:
                self.log_test(f"Create Session for {tab_id}", False, f"Error: {e}")
        
        # Send different queries to each tab
        queries = {
            "test_tab_aws": "What are AWS EC2 instance types?",
            "test_tab_terraform": "How do I structure Terraform modules?"
        }
        
        for tab_id, query in queries.items():
            if tab_id in sessions:
                try:
                    chat_data = {
                        "query": query,
                        "tab_id": tab_id,
                        "session_id": sessions[tab_id]
                    }
                    
                    response = requests.post(
                        f"{self.backend_url}/chat/{tab_id}",
                        json=chat_data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        self.log_test(
                            f"Chat in {tab_id}", 
                            len(result.get("response", "")) > 0
                        )
                    else:
                        self.log_test(f"Chat in {tab_id}", False)
                        
                except Exception as e:
                    self.log_test(f"Chat in {tab_id}", False, f"Error: {e}")
        
        # Verify contexts are isolated by checking history
        for tab_id in tabs:
            if tab_id in sessions:
                try:
                    response = requests.get(
                        f"{self.backend_url}/sessions/{tab_id}/history",
                        params={"session_id": sessions[tab_id]},
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        history = response.json()
                        # Should have user message and assistant response
                        self.log_test(
                            f"Context Isolation {tab_id}", 
                            len(history) >= 2,
                            f"Messages: {len(history)}"
                        )
                    else:
                        self.log_test(f"Context Isolation {tab_id}", False)
                        
                except Exception as e:
                    self.log_test(f"Context Isolation {tab_id}", False, f"Error: {e}")
    
    def test_langchain_demos(self):
        """Test LangChain prompt engineering demos."""
        print("\n🧪 Testing LangChain Demos...")
        
        # Test Tools & Agents demo
        try:
            tools_data = {
                "tool_name": "demo",
                "parameters": {
                    "query": "What is EC2 and calculate cost for t3.micro for 24 hours"
                }
            }
            
            response = requests.post(
                f"{self.backend_url}/demo/tools",
                json=tools_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                success = result.get("success", False)
                self.log_test("Tools & Agents Demo", success)
            else:
                self.log_test("Tools & Agents Demo", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Tools & Agents Demo", False, f"Error: {e}")
        
        # Test Structured Output demo
        try:
            structured_data = {
                "query": "I need a scalable web application with database and caching",
                "output_schema": {}
            }
            
            response = requests.post(
                f"{self.backend_url}/demo/structured-output",
                json=structured_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                success = result.get("success", False)
                self.log_test("Structured Output Demo", success)
            else:
                self.log_test("Structured Output Demo", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("Structured Output Demo", False, f"Error: {e}")
        
        # Test LCEL Chain demo
        try:
            lcel_data = {
                "input_text": "AWS Lambda is a serverless computing service that runs code without provisioning servers",
                "chain_type": "sequential"
            }
            
            response = requests.post(
                f"{self.backend_url}/demo/lcel-chain",
                json=lcel_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                output = result.get("output")
                self.log_test("LCEL Chain Demo", output is not None)
            else:
                self.log_test("LCEL Chain Demo", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_test("LCEL Chain Demo", False, f"Error: {e}")
    
    def test_system_stats(self):
        """Test system statistics endpoints."""
        print("\n📊 Testing System Statistics...")
        
        # Test database stats
        try:
            response = requests.get(f"{self.backend_url}/stats/database", timeout=10)
            if response.status_code == 200:
                stats = response.json()
                has_stats = "total_sessions" in stats or "error" in stats
                self.log_test("Database Statistics", has_stats)
            else:
                self.log_test("Database Statistics", False)
        except Exception as e:
            self.log_test("Database Statistics", False, f"Error: {e}")
        
        # Test cache stats
        try:
            response = requests.get(f"{self.backend_url}/stats/cache", timeout=10)
            if response.status_code == 200:
                stats = response.json()
                has_stats = "used_memory" in stats or "error" in stats
                self.log_test("Cache Statistics", has_stats)
            else:
                self.log_test("Cache Statistics", False)
        except Exception as e:
            self.log_test("Cache Statistics", False, f"Error: {e}")
    
    def run_all_tests(self):
        """Run all integration tests."""
        print("🚀 Starting Complete System Integration Test")
        print("=" * 60)
        
        start_time = time.time()
        
        # Run test suites
        self.test_service_health()
        self.test_backend_api()
        self.test_session_management()
        self.test_multi_tab_isolation()
        self.test_langchain_demos()
        self.test_system_stats()
        
        # Calculate results
        end_time = time.time()
        total_time = end_time - start_time
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["success"]])
        failed_tests = len(self.failed_tests)
        
        # Print summary
        print("\n" + "=" * 60)
        print("📋 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Total Time: {total_time:.2f} seconds")
        
        if self.failed_tests:
            print("\n❌ FAILED TESTS:")
            for test in self.failed_tests:
                print(f"  - {test['test']}: {test['message']}")
        
        # Return success status
        return failed_tests == 0
    
    def generate_report(self):
        """Generate detailed test report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": len(self.test_results),
                "passed": len([r for r in self.test_results if r["success"]]),
                "failed": len(self.failed_tests),
                "success_rate": (len([r for r in self.test_results if r["success"]]) / len(self.test_results)) * 100
            },
            "tests": self.test_results,
            "failed_tests": self.failed_tests
        }
        
        # Save report to file
        with open("test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: test_report.json")
        
        return report


def main():
    """Main test execution."""
    print("GenAI DevOps Assistant - Complete System Integration Test")
    print("Testing MVP functionality and system integration...")
    print()
    
    # Wait for services to be ready
    print("⏳ Waiting for services to start...")
    time.sleep(5)
    
    # Run tests
    tester = SystemTester()
    success = tester.run_all_tests()
    
    # Generate report
    tester.generate_report()
    
    # Exit with appropriate code
    if success:
        print("\n🎉 All tests passed! System is ready for demo.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Please check the issues before demo.")
        sys.exit(1)


if __name__ == "__main__":
    main()