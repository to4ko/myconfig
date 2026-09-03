#include "protocol_megatec.h"
#include "constants_hid.h"
#include "constants_ups.h"
#include "esphome/core/log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <vector>
#include <algorithm>

namespace esphome {
namespace ups_hid {

static const char *const MEGATEC_TAG = "ups_hid.megatec";

// The Cypress bridge exchanges data in fixed 8-byte HID reports on report
// ID 0 (Output for commands, interrupt IN for responses), regardless of
// how long the actual command/response text is.
static constexpr uint8_t MEGATEC_REPORT_ID = 0x00;
static constexpr size_t MEGATEC_CHUNK_SIZE = 8;

// Response can legitimately run past 46 bytes on some firmwares (extra
// whitespace, longer temperature field, etc.); bound the read loop well
// above that so we don't spin forever on a device that never sends '\r'.
static constexpr size_t MEGATEC_MAX_RESPONSE_BYTES = 128;

// Empirically, cheap Cypress-based UPS firmwares need a short beat between
// the command SET_REPORT and the first interrupt-read poll, or the first
// poll comes back empty/stale. This matches NUT's cypress_command() behavior.
static constexpr uint32_t MEGATEC_RESPONSE_SETTLE_MS = 50;

// Per-chunk timeout for interrupt reads while draining a response. This is
// intentionally much shorter than the overall protocol timeout: a healthy
// device answers within milliseconds, and capping each individual read
// bounds the worst-case blocking time in the (up to ~16-iteration) drain
// loop below to a few seconds total instead of minutes, even if something
// about the transport misbehaves again in the future.
static constexpr uint32_t MEGATEC_INTERRUPT_READ_TIMEOUT_MS = 2000;

MegatecProtocol::MegatecProtocol(UpsHidComponent *parent) : UpsProtocolBase(parent) {}

// Q1 doesn't report a charge percentage directly, only battery voltage - so
// we estimate it via linear interpolation between an "empty" and "full"
// voltage for the battery string. Two ways to get those two points:
//
//   1. Manual calibration (override_low/override_high) - set via the
//      "battery_voltage_low"/"battery_voltage_high" YAML options on the
//      ups_hid: component. This matches real NUT's
//      override.battery.voltage.low/high ups.conf directives for
//      blazer_usb/nutdrv_qx devices, and is the accurate option once
//      you've actually characterized your specific battery.
//   2. Automatic fallback (used when either override is NAN/unset): scale
//      generic 12V lead-acid assumptions (~10.5V empty, ~13.7V float
//      charge) by the reported (or assumed 12V) nominal voltage. This is
//      necessarily approximate - a lead-acid voltage-to-charge curve isn't
//      perfectly linear - but far better than reporting nothing.
static float estimate_battery_level_percent(float voltage, float nominal_voltage, float override_low,
                                              float override_high) {
  if (std::isnan(voltage)) {
    return NAN;
  }

  float low, high;
  if (!std::isnan(override_low) && !std::isnan(override_high) && override_high > override_low) {
    low = override_low;
    high = override_high;
  } else {
    float base = (!std::isnan(nominal_voltage) && nominal_voltage > 0.0f) ? nominal_voltage : 12.0f;
    // For a 12V lead-acid string: ~10.5V unloaded = empty, ~13.7V float
    // charge = full. Scale proportionally for other nominal voltages (e.g.
    // 24V, 36V battery banks on larger units).
    low = base * (10.5f / 12.0f);
    high = base * (13.7f / 12.0f);
  }

  if (high <= low) {
    return NAN;
  }
  float pct = (voltage - low) / (high - low) * 100.0f;
  if (pct < 0.0f) pct = 0.0f;
  if (pct > 100.0f) pct = 100.0f;
  return pct;
}

bool MegatecProtocol::query(const std::string &command, std::string &response, uint32_t timeout_ms) {
  response.clear();

  if (!parent_->is_connected()) {
    ESP_LOGD(MEGATEC_TAG, "Device not connected, skipping query '%s'", command.c_str());
    return false;
  }

  // Command is sent as a single 8-byte Output report (report ID 0),
  // zero-padded/truncated. This matches NUT's cypress_command(): wValue =
  // 0x0200 = (report_type=OUTPUT(0x02) << 8) | report_id(0). Earlier
  // versions of this code used report_type=FEATURE here, which some
  // Cypress-bridge firmwares silently ignore or mishandle.
  uint8_t out_buf[MEGATEC_CHUNK_SIZE] = {0};
  size_t copy_len = std::min(command.size(), MEGATEC_CHUNK_SIZE);
  std::memcpy(out_buf, command.data(), copy_len);

  esp_err_t ret =
      parent_->hid_set_report(HID_REPORT_TYPE_OUTPUT, MEGATEC_REPORT_ID, out_buf, sizeof(out_buf), timeout_ms);
  if (ret != ESP_OK) {
    ESP_LOGD(MEGATEC_TAG, "SET_REPORT failed for command '%s': %s", command.c_str(), esp_err_to_name(ret));
    return false;
  }

  vTaskDelay(pdMS_TO_TICKS(MEGATEC_RESPONSE_SETTLE_MS));

  // IMPORTANT: the response is read from the device's interrupt IN
  // endpoint, NOT via a HID GET_REPORT control transfer. This mirrors
  // NUT's cypress_command(), which uses usb_interrupt_read() for the
  // response half of the exchange. An earlier version of this code used
  // hid_get_report() here; against real Cypress-bridge hardware that
  // control transfer either goes unanswered or is handled badly enough to
  // stall the ESP32 USB host stack for tens of seconds and trip the task
  // watchdog, crashing and rolling back the firmware. Do not change this
  // back to hid_get_report() without testing against real hardware.
  while (response.size() < MEGATEC_MAX_RESPONSE_BYTES) {
    if (!parent_->is_connected()) {
      ESP_LOGD(MEGATEC_TAG, "Device disconnected while reading response to '%s'", command.c_str());
      return false;
    }

    uint8_t in_buf[MEGATEC_CHUNK_SIZE] = {0};
    size_t in_len = sizeof(in_buf);
    ret = parent_->hid_interrupt_read(in_buf, &in_len, MEGATEC_INTERRUPT_READ_TIMEOUT_MS);
    if (ret != ESP_OK || in_len == 0) {
      ESP_LOGD(MEGATEC_TAG, "Interrupt read failed while reading response to '%s': %s", command.c_str(),
                esp_err_to_name(ret));
      return false;
    }

    bool found_terminator = false;
    for (size_t i = 0; i < in_len; i++) {
      char c = static_cast<char>(in_buf[i]);
      if (c == '\r') {
        found_terminator = true;
        break;
      }
      // Trailing zero-padding in the final chunk isn't part of the payload.
      if (c != '\0') {
        response.push_back(c);
      }
    }
    if (found_terminator) {
      return true;
    }
  }

  ESP_LOGD(MEGATEC_TAG, "Response to '%s' exceeded %zu bytes without a terminator", command.c_str(),
            MEGATEC_MAX_RESPONSE_BYTES);
  return false;
}

bool MegatecProtocol::detect() {
  ESP_LOGD(MEGATEC_TAG, "Detecting Megatec/Q1 protocol...");

  if (!parent_->is_connected()) {
    ESP_LOGD(MEGATEC_TAG, "Device not connected, skipping protocol detection");
    return false;
  }

  std::string response;
  if (!query("Q1\r", response, parent_->get_protocol_timeout())) {
    ESP_LOGD(MEGATEC_TAG, "No response to Q1 status query");
    return false;
  }

  // A valid Q1 response starts with '(' and has enough fields to be
  // meaningful; reject anything that's just noise from a device that
  // doesn't understand this command at all.
  if (response.empty() || response.front() != '(' || response.size() < 30) {
    ESP_LOGD(MEGATEC_TAG, "Response to Q1 doesn't look like Megatec status: '%s'", response.c_str());
    return false;
  }

  ESP_LOGI(MEGATEC_TAG, "Megatec/Q1 device detected, Q1 response: '%s'", response.c_str());
  return true;
}

bool MegatecProtocol::initialize() {
  ESP_LOGD(MEGATEC_TAG, "Initializing Megatec/Q1 protocol...");
  // Nothing stateful to set up beyond what detect() already confirmed;
  // device info / ratings are fetched lazily on the first read_data() call
  // so a slow or non-responding "F"/"I" command can't block startup.
  return true;
}

bool MegatecProtocol::read_data(UpsData &data) {
  if (!device_info_queried_) {
    query_device_info(data);
    query_ratings(data);
    device_info_queried_ = true;
  }

  std::string response;
  if (!query("Q1\r", response, parent_->get_protocol_timeout())) {
    ESP_LOGW(MEGATEC_TAG, "Failed to read Q1 status");
    return false;
  }

  return parse_status_response(response, data);
}

bool MegatecProtocol::parse_status_response(const std::string &response, UpsData &data) {
  // Expected: "(MMM.M NNN.N PPP.P QQQ RR.R S.SS TT.T bbbbbbbb"
  // (leading '(' already stripped of by sscanf's literal match below; the
  // trailing '\r' was already consumed by query()).
  float input_voltage = NAN;
  float input_fault_voltage = NAN;
  float output_voltage = NAN;
  float load_percent = NAN;
  float frequency = NAN;
  float battery_voltage = NAN;
  float temperature = NAN;
  char status_bits[16] = {0};

  int matched = std::sscanf(response.c_str(), "(%f %f %f %f %f %f %f %15s", &input_voltage, &input_fault_voltage,
                             &output_voltage, &load_percent, &frequency, &battery_voltage, &temperature,
                             status_bits);

  if (matched < 7) {
    ESP_LOGW(MEGATEC_TAG, "Could not parse Q1 response (got %d/8 fields): '%s'", matched, response.c_str());
    return false;
  }

  data.power.input_voltage = input_voltage;
  data.power.output_voltage = output_voltage;
  data.power.load_percent = load_percent;
  data.power.frequency = frequency;
  data.battery.voltage = battery_voltage;
  data.battery.level = estimate_battery_level_percent(
      battery_voltage, data.battery.voltage_nominal,
      parent_->get_battery_voltage_low_override(), parent_->get_battery_voltage_high_override());
  // Q1 doesn't report a fault-voltage-vs-nominal distinction we can use
  // directly for input_transfer_low/high; leave those as NAN (unknown)
  // rather than guessing.
  (void) input_fault_voltage;
  data.power.temperature = temperature;

  bool have_status_bits = (matched == 8) && (std::strlen(status_bits) >= 8);

  if (have_status_bits) {
    // Bits are transmitted b7..b0, left to right.
    bool on_battery = status_bits[0] == '1';       // b7: Utility Fail (Immediate)
    bool battery_low = status_bits[1] == '1';       // b6: Battery Low
    bool boost_or_buck = status_bits[2] == '1';      // b5: Bypass/Boost or Buck Active
    bool ups_failed = status_bits[3] == '1';         // b4: UPS Failed
    bool test_in_progress = status_bits[5] == '1';   // b2: Test in Progress
    bool beeper_on = status_bits[7] == '1';          // b0: Beeper On

    last_beeper_bit_ = beeper_on ? 1 : 0;

    data.power.status = on_battery ? status::ON_BATTERY : status::ONLINE;
    data.power.on_battery_known = true;
    data.power.on_battery = on_battery;

    if (ups_failed) {
      data.battery.status = battery_status::FAULT;
    } else if (battery_low) {
      data.battery.status = battery_status::LOW;
    } else if (on_battery) {
      data.battery.status = battery_status::DISCHARGING;
    } else {
      data.battery.status = battery_status::NORMAL;
    }

    data.config.beeper_status = beeper_on ? "enabled" : "disabled";
    data.config.parse_beeper_status(data.config.beeper_status);

    data.test.current_test_state =
        test_in_progress ? TestStatus::TEST_STATE_UPS_TEST_RUNNING : TestStatus::TEST_STATE_IDLE;

    (void) boost_or_buck;  // Not currently surfaced as a sensor.
  } else {
    // Still usable without the status byte, just less informative: derive
    // online/offline the same way the rest of the component does elsewhere
    // (valid input voltage => online), via power.input_voltage_valid().
    data.power.status = data.power.input_voltage_valid() ? status::ONLINE : status::ON_BATTERY;
  }

  return true;
}

void MegatecProtocol::query_ratings(UpsData &data) {
  std::string response;
  if (!query("F\r", response, parent_->get_protocol_timeout())) {
    ESP_LOGD(MEGATEC_TAG, "No response to ratings ('F') query, skipping");
    return;
  }

  // Expected: "#MMM.M QQQ SS.SS RR.R"
  float nominal_input_voltage = NAN;
  float nominal_input_current = NAN;
  float nominal_battery_voltage = NAN;
  float nominal_frequency = NAN;

  int matched = std::sscanf(response.c_str(), "#%f %f %f %f", &nominal_input_voltage, &nominal_input_current,
                             &nominal_battery_voltage, &nominal_frequency);
  if (matched < 1) {
    ESP_LOGD(MEGATEC_TAG, "Could not parse ratings response: '%s'", response.c_str());
    return;
  }

  if (!std::isnan(nominal_input_voltage)) {
    data.power.input_voltage_nominal = nominal_input_voltage;
    data.power.output_voltage_nominal = nominal_input_voltage;
  }
  if (matched >= 3 && !std::isnan(nominal_battery_voltage)) {
    data.battery.voltage_nominal = nominal_battery_voltage;
  }
  (void) nominal_input_current;  // No dedicated nominal-current sensor field yet.

  ESP_LOGI(MEGATEC_TAG, "Ratings: nominal input %.1fV, nominal battery %.2fV", nominal_input_voltage,
           nominal_battery_voltage);
}

void MegatecProtocol::query_device_info(UpsData &data) {
  std::string response;
  if (!query("I\r", response, parent_->get_protocol_timeout())) {
    ESP_LOGD(MEGATEC_TAG, "No response to identification ('I') query, skipping");
    return;
  }

  // Expected: "#Manufacturer, Product, Version" (commas may or may not have
  // surrounding spaces depending on firmware).
  if (response.empty() || response.front() != '#') {
    ESP_LOGD(MEGATEC_TAG, "Unexpected identification response: '%s'", response.c_str());
    return;
  }

  std::string fields = response.substr(1);
  std::vector<std::string> parts;
  size_t start = 0;
  while (start <= fields.size()) {
    size_t comma = fields.find(',', start);
    std::string part = (comma == std::string::npos) ? fields.substr(start) : fields.substr(start, comma - start);
    // Trim surrounding whitespace.
    size_t first = part.find_first_not_of(" \t");
    size_t last = part.find_last_not_of(" \t");
    if (first != std::string::npos) {
      parts.push_back(part.substr(first, last - first + 1));
    } else {
      parts.push_back("");
    }
    if (comma == std::string::npos) break;
    start = comma + 1;
  }

  if (parts.size() >= 1 && !parts[0].empty()) data.device.manufacturer = parts[0];
  if (parts.size() >= 2 && !parts[1].empty()) data.device.model = parts[1];
  if (parts.size() >= 3 && !parts[2].empty()) data.device.firmware_version = parts[2];

  ESP_LOGI(MEGATEC_TAG, "Device info: manufacturer='%s' model='%s' firmware='%s'", data.device.manufacturer.c_str(),
           data.device.model.c_str(), data.device.firmware_version.c_str());
}

bool MegatecProtocol::set_beeper(bool want_on) {
  if (last_beeper_bit_ == (want_on ? 1 : 0)) {
    ESP_LOGD(MEGATEC_TAG, "Beeper already %s, not sending toggle", want_on ? "on" : "off");
    return true;
  }

  std::string response;
  if (!query("Q\r", response, parent_->get_protocol_timeout())) {
    ESP_LOGW(MEGATEC_TAG, "Beeper toggle: no response to 'Q' command");
    return false;
  }

  // NUT's blazer.c treats a leading "ACK" or "(ACK" as success for this
  // family of instant commands; anything else (typically the command
  // echoed back unchanged) means the device rejected/didn't understand it.
  bool ack = (response.rfind("ACK", 0) == 0) || (response.rfind("(ACK", 0) == 0);
  if (!ack) {
    ESP_LOGW(MEGATEC_TAG, "Beeper toggle: unexpected response '%s' (expected ACK)", response.c_str());
    return false;
  }

  last_beeper_bit_ = want_on ? 1 : 0;
  ESP_LOGI(MEGATEC_TAG, "Beeper toggled %s", want_on ? "on" : "off");
  return true;
}

// Creator function used by the protocol factory.
std::unique_ptr<UpsProtocolBase> create_megatec_protocol(UpsHidComponent *parent) {
  return std::make_unique<MegatecProtocol>(parent);
}

// See protocol_megatec.h for why this exists: it gives the linker a real
// reason to keep this translation unit (and therefore the static registrar
// below) when building with --gc-sections.
void ensure_megatec_protocol_linked() {}

}  // namespace ups_hid
}  // namespace esphome

// Register Megatec/Q1 for the Cypress USB-to-serial vendor ID. If a device
// with this VID turns out not to actually be a Megatec device (detect()
// returns false), the factory falls through to the generic HID fallback
// protocol automatically, so this is safe to register unconditionally.
REGISTER_UPS_PROTOCOL_FOR_VENDOR(0x0665, megatec_q1_protocol, esphome::ups_hid::create_megatec_protocol,
                                  "Megatec/Q1 HID Protocol",
                                  "Megatec/Q1 ASCII protocol over Cypress USB-to-serial HID bridge, used by many "
                                  "Ippon and similar offline/line-interactive UPS units",
                                  50);
