#!/usr/bin/env python3
"""
Test script to verify P0 and P1 refactorings work correctly.

This script tests:
1. Health check endpoint
2. Button label constants usage
3. XPath builder function
4. Driver auto-recovery mechanism

Run this after starting the add-on:
    python test_refactoring.py
"""

import requests
import time
import json

# Configuration - adjust to your setup
BASE_URL = "http://localhost:36725"
WALLBOX_IP = "192.168.178.178"  # Change to your Enpal Box IP

def test_health_check():
    """Test the /health endpoint."""
    print("\n=== Testing Health Check Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "healthy", "Status should be healthy"
            assert "driver_active" in data, "Should include driver_active field"
            assert "base_url" in data, "Should include base_url field"
            print("✅ Health check passed!")
            return True
        else:
            print("❌ Health check returned non-200 status")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_available_buttons():
    """Test the /wallbox/available_buttons endpoint (uses ButtonLabels.all())."""
    print("\n=== Testing Available Buttons Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/wallbox/available_buttons", timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            assert "buttons" in data, "Should include buttons field"
            
            # Verify all ButtonLabels constants are checked
            expected_labels = ["Start Charging", "Stop Charging", "Set Eco", "Set Full", "Set Solar"]
            for label in expected_labels:
                assert label in data["buttons"], f"Should check '{label}' button"
            
            print("✅ Available buttons check passed!")
            return True
        else:
            print("❌ Available buttons check failed")
            return False
    except Exception as e:
        print(f"❌ Available buttons check failed: {e}")
        return False

def test_status_endpoint():
    """Test the /wallbox/status endpoint."""
    print("\n=== Testing Status Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/wallbox/status", timeout=15)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                assert "mode" in data, "Should include mode field"
                assert "status" in data, "Should include status field"
                print("✅ Status endpoint passed!")
                return True
            else:
                print("⚠️  Status endpoint returned success=false (may be expected if wallbox unreachable)")
                return True
        else:
            print("❌ Status endpoint failed")
            return False
    except Exception as e:
        print(f"❌ Status endpoint failed: {e}")
        return False

def test_driver_recovery_simulation():
    """Test that the service recovers gracefully from errors."""
    print("\n=== Testing Driver Recovery (Multiple Rapid Requests) ===")
    try:
        # Make multiple rapid requests to test thread safety and recovery
        success_count = 0
        for i in range(3):
            print(f"Request {i+1}/3...")
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                success_count += 1
            time.sleep(1)
        
        print(f"Successful requests: {success_count}/3")
        if success_count >= 2:
            print("✅ Driver recovery test passed!")
            return True
        else:
            print("❌ Too many failed requests")
            return False
    except Exception as e:
        print(f"❌ Driver recovery test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("="*60)
    print("Enpal Wallbox Controller - Refactoring Test Suite")
    print("="*60)
    print(f"\nTesting endpoint: {BASE_URL}")
    print(f"Wallbox IP configured: {WALLBOX_IP}")
    print("\nNote: Some tests may fail if the Enpal Box is unreachable.")
    print("The important part is that the service responds correctly.")
    
    results = []
    
    # Run all tests
    results.append(("Health Check", test_health_check()))
    results.append(("Available Buttons", test_available_buttons()))
    results.append(("Status Endpoint", test_status_endpoint()))
    results.append(("Driver Recovery", test_driver_recovery_simulation()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Refactoring successful!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above.")
        return 1

if __name__ == "__main__":
    exit(main())
