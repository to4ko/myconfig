#pragma once

#include "ups_hid.h"

// Forces the linker to keep this translation unit (and its static vendor-protocol
// registrar in protocol_megatec.cpp) even when building with --gc-sections. Without
// a real cross-TU symbol reference, nothing else in the codebase calls into this
// file directly (registration happens purely as a static-initializer side effect),
// so an aggressively size-optimized ESP-IDF link can drop the whole object file and
// this protocol silently never registers itself. Call this once, e.g. from
// UpsHidComponent::setup(), before any protocol auto-detection happens. See the
// identical pattern (and the bug it was added to work around) in protocol_generic.h.
namespace esphome {
namespace ups_hid {
void ensure_megatec_protocol_linked();
}  // namespace ups_hid
}  // namespace esphome

namespace esphome {
namespace ups_hid {

/**
 * Megatec/Q1 protocol implementation ("Cypress" flavor).
 *
 * A large family of cheap offline/line-interactive UPS units (many Ippon
 * models among them) do NOT speak the standard USB HID Power Device Class
 * that ApcHidProtocol/CyberPowerProtocol/GenericHidProtocol expect. Instead
 * they use a USB-to-serial bridge (commonly a Cypress chip, USB VID 0x0665)
 * that tunnels the old Megatec/Q1 *ASCII* protocol through plain 8-byte HID
 * reports:
 *
 *   - Host -> UPS: SET_REPORT(Output, id=0, 8 bytes), command text
 *     zero-padded/truncated to 8 bytes, e.g. "Q1\r\0\0\0\0\0".
 *   - UPS -> Host: repeated interrupt IN transfers (8 bytes each) on the
 *     device's interrupt endpoint; the host concatenates chunks until it
 *     sees a '\r' terminator.
 *
 * This mirrors NUT's blazer_usb driver with subdriver=cypress exactly,
 * including the report type used for SET_REPORT (Output, not Feature) and,
 * critically, reading the response via an interrupt transfer rather than a
 * GET_REPORT control transfer - the latter was tried first in an earlier
 * version of this file and reliably stalled the ESP32 USB host stack
 * against real hardware (bad enough to trip the task watchdog and force a
 * firmware rollback). Reference:
 * https://github.com/networkupstools/nut (drivers/blazer_usb.c, cypress_command())
 *
 * Known commands used here:
 *   "Q1\r" - status query, returns:
 *     "(MMM.M NNN.N PPP.P QQQ RR.R S.SS TT.T b7b6b5b4b3b2b1b0\r"
 *       MMM.M = input voltage           NNN.N = input fault voltage
 *       PPP.P = output voltage          QQQ   = load percent
 *       RR.R  = input frequency         S.SS  = battery voltage
 *       TT.T  = UPS temperature         b7..b0 = status bits (see .cpp)
 *   "F\r"  - ratings query, returns:
 *     "#MMM.M QQQ SS.SS RR.R\r"
 *       MMM.M = nominal input voltage, QQQ = nominal input current,
 *       SS.SS = nominal battery voltage, RR.R = nominal frequency
 *   "I\r"  - device identification, returns:
 *     "#Manufacturer, Product, Version\r"
 *
 * This is intentionally read-only in this first version: Megatec write
 * commands (shutdown/test/beeper toggle) vary more between vendors than the
 * Q1 status query does, and sending the wrong one on an unfamiliar device
 * risks an unwanted shutdown. Beeper/test control can be added later once
 * confirmed against a real device log.
 */
class MegatecProtocol : public UpsProtocolBase {
public:
  explicit MegatecProtocol(UpsHidComponent *parent);

  bool detect() override;
  bool initialize() override;
  bool read_data(UpsData &data) override;
  DeviceInfo::DetectedProtocol get_protocol_type() const override { return DeviceInfo::PROTOCOL_MEGATEC_Q1; }
  std::string get_protocol_name() const override { return "Megatec/Q1 HID Protocol"; }

  // Megatec/Q1 (and NUT's blazer_usb driver, which this mirrors) only
  // exposes a single "beeper.toggle" instant command ("Q\r") - there is no
  // separate enable/disable wire command. These two therefore check the
  // last known beeper state (from the most recent Q1 status parse) and
  // only send the toggle if the device isn't already in the requested
  // state, so calling beeper_enable() twice in a row is a safe no-op the
  // second time rather than toggling back off.
  bool beeper_enable() override { return set_beeper(true); }
  bool beeper_disable() override { return set_beeper(false); }

private:
  // Sends a Megatec ASCII command (e.g. "Q1\r") via HID SET_REPORT and reads
  // the ASCII response back via repeated HID GET_REPORT calls until a '\r'
  // terminator is seen or the response grows implausibly long. Returns false
  // on any transport error or on timeout without a terminator.
  bool query(const std::string &command, std::string &response, uint32_t timeout_ms);

  // Parses a "(....status...\r" Q1 response into the shared UpsData model.
  bool parse_status_response(const std::string &response, UpsData &data);

  // Best-effort, non-fatal: nominal ratings ("F") and device identification
  // ("I"). Failures here don't prevent read_data() from working, since not
  // every Megatec device implements these two commands.
  void query_ratings(UpsData &data);
  void query_device_info(UpsData &data);

  // Sends the "Q\r" beeper.toggle command if (and only if) the last known
  // beeper state (from parse_status_response) differs from want_on.
  // Returns true if the device ends up in the requested state (either it
  // already was, or the toggle was sent and acknowledged); false if the
  // toggle was sent but not acknowledged, or if state is unknown and the
  // toggle couldn't be confirmed.
  bool set_beeper(bool want_on);

  bool device_info_queried_{false};

  // -1 = unknown (no Q1 status parsed yet), 0 = off, 1 = on. Updated every
  // time parse_status_response() reads the status byte.
  int last_beeper_bit_{-1};
};

}  // namespace ups_hid
}  // namespace esphome
