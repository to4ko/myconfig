#pragma once

#include <string>
#include <cstdint>

namespace esphome {
namespace ups_hid {

struct TestStatus {
  // Test result information
  std::string ups_test_result{};       // Current test result text
  std::string last_test_result{};      // Last completed test result
  
  // Test timing information
  int16_t timer_reboot{-1};            // Reboot timer (seconds, -1 = not set)
  int16_t timer_shutdown{-1};          // Shutdown timer (seconds, -1 = not set)
  int16_t timer_start{-1};             // Start timer (seconds, -1 = not set)
  
  // Test progress tracking
  enum TestState {
    TEST_STATE_IDLE = 0,
    TEST_STATE_BATTERY_QUICK_RUNNING,
    TEST_STATE_BATTERY_DEEP_RUNNING,
    TEST_STATE_UPS_TEST_RUNNING,
    TEST_STATE_PANEL_TEST_RUNNING,
    TEST_STATE_COMPLETED,
    TEST_STATE_FAILED,
    TEST_STATE_ABORTED
  };
  
  TestState current_test_state{TEST_STATE_IDLE};
  uint32_t test_start_time{0};         // Test start time (millis)
  uint32_t test_duration_ms{0};        // Current test duration
  
  // Test results enumeration (NUT compatible)
  enum TestResult {
    TEST_RESULT_UNKNOWN = 0,
    TEST_RESULT_NO_TEST,
    TEST_RESULT_PASSED,
    TEST_RESULT_FAILED,
    TEST_RESULT_IN_PROGRESS,
    TEST_RESULT_NOT_SUPPORTED,
    TEST_RESULT_ABORTED,
    TEST_RESULT_BATTERY_GOOD,
    TEST_RESULT_BATTERY_BAD,
    TEST_RESULT_BATTERY_REPLACE
  };
  
  TestResult last_battery_test_result{TEST_RESULT_UNKNOWN};
  TestResult last_ups_test_result{TEST_RESULT_UNKNOWN};
  
  // Test type tracking
  enum TestType {
    TEST_TYPE_NONE = 0,
    TEST_TYPE_BATTERY_QUICK,
    TEST_TYPE_BATTERY_DEEP,
    TEST_TYPE_UPS_SELF_TEST,
    TEST_TYPE_PANEL_TEST
  };
  
  TestType current_test_type{TEST_TYPE_NONE};
  
  // Validation and utility methods
  bool is_test_running() const {
    return current_test_state == TEST_STATE_BATTERY_QUICK_RUNNING ||
           current_test_state == TEST_STATE_BATTERY_DEEP_RUNNING ||
           current_test_state == TEST_STATE_UPS_TEST_RUNNING ||
           current_test_state == TEST_STATE_PANEL_TEST_RUNNING;
  }
  
  bool is_battery_test_running() const {
    return current_test_state == TEST_STATE_BATTERY_QUICK_RUNNING ||
           current_test_state == TEST_STATE_BATTERY_DEEP_RUNNING;
  }
  
  bool has_test_results() const {
    return !ups_test_result.empty() || !last_test_result.empty();
  }
  
  bool has_timers() const {
    return timer_reboot != -1 || timer_shutdown != -1 || timer_start != -1;
  }
  
  std::string get_test_state_name() const {
    switch (current_test_state) {
      case TEST_STATE_IDLE: return "Idle";
      case TEST_STATE_BATTERY_QUICK_RUNNING: return "Battery Quick Test";
      case TEST_STATE_BATTERY_DEEP_RUNNING: return "Battery Deep Test";
      case TEST_STATE_UPS_TEST_RUNNING: return "UPS Self Test";
      case TEST_STATE_PANEL_TEST_RUNNING: return "Panel Test";
      case TEST_STATE_COMPLETED: return "Test Completed";
      case TEST_STATE_FAILED: return "Test Failed";
      case TEST_STATE_ABORTED: return "Test Aborted";
      default: return "Unknown";
    }
  }
  
  std::string get_test_result_name(TestResult result) const {
    switch (result) {
      case TEST_RESULT_NO_TEST: return "No test";
      case TEST_RESULT_PASSED: return "Passed";
      case TEST_RESULT_FAILED: return "Failed";
      case TEST_RESULT_IN_PROGRESS: return "In progress";
      case TEST_RESULT_NOT_SUPPORTED: return "Not supported";
      case TEST_RESULT_ABORTED: return "Aborted";
      case TEST_RESULT_BATTERY_GOOD: return "Battery good";
      case TEST_RESULT_BATTERY_BAD: return "Battery bad";
      case TEST_RESULT_BATTERY_REPLACE: return "Replace battery";
      default: return "Unknown";
    }
  }
  
  void start_test(TestType type, uint32_t start_time) {
    current_test_type = type;
    test_start_time = start_time;
    test_duration_ms = 0;
    
    switch (type) {
      case TEST_TYPE_BATTERY_QUICK:
        current_test_state = TEST_STATE_BATTERY_QUICK_RUNNING;
        break;
      case TEST_TYPE_BATTERY_DEEP:
        current_test_state = TEST_STATE_BATTERY_DEEP_RUNNING;
        break;
      case TEST_TYPE_UPS_SELF_TEST:
        current_test_state = TEST_STATE_UPS_TEST_RUNNING;
        break;
      case TEST_TYPE_PANEL_TEST:
        current_test_state = TEST_STATE_PANEL_TEST_RUNNING;
        break;
      default:
        current_test_state = TEST_STATE_IDLE;
        break;
    }
  }
  
  void update_test_progress(uint32_t current_time) {
    if (is_test_running() && test_start_time > 0) {
      test_duration_ms = current_time - test_start_time;
    }
  }
  
  void complete_test(TestResult result) {
    current_test_state = TEST_STATE_COMPLETED;
    
    if (current_test_type == TEST_TYPE_BATTERY_QUICK || current_test_type == TEST_TYPE_BATTERY_DEEP) {
      last_battery_test_result = result;
    } else {
      last_ups_test_result = result;
    }
    
    // Move current result to last result
    if (!ups_test_result.empty()) {
      last_test_result = ups_test_result;
    }
  }
  
  void abort_test() {
    current_test_state = TEST_STATE_ABORTED;
    ups_test_result = "Test aborted";
  }
  
  bool is_valid() const {
    return has_test_results() || is_test_running() || has_timers();
  }
  
  void reset() { 
    *this = TestStatus{}; 
  }
  
  // Copy constructor and assignment for safe copying
  TestStatus() = default;
  TestStatus(const TestStatus&) = default;
  TestStatus& operator=(const TestStatus&) = default;
  TestStatus(TestStatus&&) = default;
  TestStatus& operator=(TestStatus&&) = default;
};

}  // namespace ups_hid
}  // namespace esphome