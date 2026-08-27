#include <cstdint>
#include <cstring>
#include <cinttypes>

#include "utils.h"
#include "log.h"

#include "tion-api.h"
#include "tion-api-defines.h"

namespace dentra {
namespace tion {

static const char *const TAG = "tion-api";
#define INVALID_STATE_CALL() TION_LOGW(TAG, "Invalid state call")

void report_errors(uint32_t errors, uint8_t error_min_bit, uint8_t error_max_bit, uint8_t warning_min_bit,
                   uint8_t warning_max_bit) {}

void enum_errors(uint32_t errors, uint8_t min_bit, uint8_t max_bit, const void *param,
                 const std::function<void(uint8_t, const void *)> &fn) {
  for (uint8_t i = min_bit; i <= max_bit; i++) {
    uint32_t mask = 1 << i;
    if ((errors & mask) == mask) {
      fn(i - min_bit + 1, param);
    }
  }
}

std::string decode_errors(uint32_t errors, uint8_t error_min_bit, uint8_t error_max_bit, uint8_t warning_min_bit,
                          uint8_t warning_max_bit) {
  std::string messages;

  auto add_message = [&messages](uint8_t err, const void *param) {
    if (!messages.empty()) {
      messages += ", ";
    }
    messages += static_cast<const char *>(param);
    if (err < 10) {
      messages += '0';
    }
    messages += std::to_string(err);
  };

  enum_errors(errors, error_min_bit, error_max_bit, "EC", add_message);

  if (warning_min_bit != warning_max_bit) {
    enum_errors(errors, warning_min_bit, warning_max_bit, "WS", add_message);
  }

  return messages;
}

void TionState::dump(const char *TAG, const TionTraits &traits) const {
  if (this->errors) {
    if (traits.errors_decode) {
      const auto errors = traits.errors_decode(this->errors);
      TION_LOGW(TAG, "Breezer alert[0x%" PRIx32 "]: %s", this->errors, errors.c_str());
    }
    if (traits.errors_report) {
      traits.errors_report(this->errors);
    }
  }

  TION_DUMP(TAG, "power       : %s", ONOFF(this->power_state));
  TION_DUMP(TAG, "heater      : %s", ONOFF(this->heater_state));
  TION_DUMP(TAG, "filter_warn : %s", ONOFF(this->filter_state));
  TION_DUMP(TAG, "fan_speed   : %d", this->fan_speed);
  TION_DUMP(TAG, "target_temp : %d °C", this->target_temperature);
  TION_DUMP(TAG, "outdoor_temp: %d °C", this->outdoor_temperature);
  TION_DUMP(TAG, "current_temp: %d °C", this->current_temperature);
  TION_DUMP(TAG, "gate_pos    : %s", this->get_gate_position_str(traits));

  if (traits.supports_sound_state) {
    TION_DUMP(TAG, "sound       : %s", ONOFF(this->sound_state));
  }
  if (traits.supports_led_state) {
    TION_DUMP(TAG, "led         : %s", ONOFF(this->led_state));
  }

  TION_DUMP(TAG, "auto        : %s", ONOFF(this->auto_state));
  TION_DUMP(TAG, "comm_source : %s", this->comm_source == CommSource::AUTO ? "AUTO" : "USER");

  if (traits.max_heater_power) {
    TION_DUMP(TAG, "heater_max  : %u W", traits.get_max_heater_power());
  }

  if (traits.supports_heater_var) {
    TION_DUMP(TAG, "heater_var  : %u %%", this->heater_var);
  }

  TION_DUMP(TAG, "productivity: %u m³", this->productivity);

  TION_DUMP(TAG, "filter_time : %" PRIu32 " s", this->filter_time_left);
  if (traits.supports_work_time) {
    TION_DUMP(TAG, "work_time   : %" PRIu32 " s", this->work_time);
  }
  if (traits.supports_fan_time) {
    TION_DUMP(TAG, "fan_time    : %" PRIu32 " s", this->fan_time);
  }
  if (traits.supports_airflow_counter) {
    TION_DUMP(TAG, "airflow     : %.3f m³ (%" PRIu32 ")", this->airflow_m3, this->airflow_counter);
  }

  if (traits.supports_pcb_ctl_temperature) {
    TION_DUMP(TAG, "pcb_ctl_temp: %d °C", this->pcb_ctl_temperature);
  }
  if (traits.supports_pcb_pwr_temperature) {
    TION_DUMP(TAG, "pcb_pwr_temp: %d °C", this->pcb_pwr_temperature);
  }

  if (this->firmware_version) {
    TION_DUMP(TAG, "firmware_ver: %04X", this->firmware_version);
  }
  if (this->hardware_version) {
    TION_DUMP(TAG, "hardware_ver: %04X", this->hardware_version);
  }

  TION_DUMP(TAG, "errors      : 0x%08" PRIX32, this->errors);
}

float TionState::get_heater_power(const TionTraits &traits) const {
  if (traits.supports_heater_var) {
    return (traits.max_heater_power * this->heater_var) * 0.1f;
  }
  return this->is_heating(traits) ? traits.get_max_heater_power() : 0.0f;
}

bool TionState::is_heating(const TionTraits &traits) const {
  if (traits.supports_heater_var) {
    return this->heater_var > 0;
  }
  if (!this->heater_state || traits.max_heater_power == 0) {
    return false;
  }
  // heating detection borrowed from:
  // https://github.com/TionAPI/tion_python/blob/master/tion_btle/tion.py#L177
  // self.heater_temp - self.in_temp > 3 and self.out_temp > self.in_temp
  return (this->target_temperature - this->outdoor_temperature) > 3 &&
         (this->current_temperature > this->outdoor_temperature);
}

const char *TionState::get_gate_position_str(const TionTraits &traits) const {
  if (traits.supports_gate_error && this->gate_error_state) {
    return "error";
  }
  if (traits.supports_gate_position_change_mixed) {
    switch (this->gate_position) {
      case TionGatePosition::OUTDOOR:
        return "outdoor";
      case TionGatePosition::INDOOR:
        return "indoor";
      case TionGatePosition::MIXED:
        return "mixed";
      default:
        return "unknown";
    }

  } else if (traits.supports_gate_position_change) {
    switch (this->gate_position) {
      case TionGatePosition::OUTDOOR:
        return "inflow";
      case TionGatePosition::INDOOR:
        return "recirculation";
      default:
        return "unknown";
    }
  }
  return this->gate_position == TionGatePosition::OPENED ? "opened" : "closed";
}

TionState TionApiBase::make_write_state_(TionStateCall *call) const {
  const auto &cs = this->state_;
  // new state
  auto ns = this->state_;

  if (call->get_auto_state().has_value()) {
    const auto auto_state = *call->get_auto_state();
    if (!auto_state || this->auto_is_valid()) {
      if (cs.auto_state != auto_state) {
        TION_LOGD(TAG, "New auto state %s -> %s", ONOFF(cs.auto_state), ONOFF(auto_state));
        ns.auto_state = auto_state;
      }
    } else {
      TION_LOGW(TAG, "Auto is not configured properly.");
    }
  }

  ns.comm_source = ns.auto_state ? CommSource::AUTO : CommSource::USER;

  if (call->get_fan_speed().has_value()) {
    const auto fan_speed = *call->get_fan_speed();
    // не разрешаем скорость 0, вместо этого выключаем бризер
    if (fan_speed == 0) {
      if (call->get_power_state().value_or(cs.power_state)) {
        // залоггируем только для не авто-режима
        if (!call->get_auto_state().value_or(false)) {
          TION_LOGW(TAG, "Zero fan speed lead to power off");
        }
        call->set_power_state(false);
      }
    } else if (fan_speed > this->traits_.max_fan_speed) {
      TION_LOGW(TAG, "Disallowed fan speed: %u", fan_speed);
    } else if (cs.fan_speed != fan_speed) {
      TION_LOGD(TAG, "New fan speed %u -> %u", cs.fan_speed, fan_speed);
      ns.fan_speed = fan_speed;
      if (!call->get_auto_state().value_or(false)) {
        // если ручное переключение скорости, то выключаем авто-режим
        ns.auto_state = false;
      }
    }
  }

  if (call->get_power_state().has_value()) {
    const auto power_state = *call->get_power_state();
    if (cs.power_state != power_state) {
      TION_LOGD(TAG, "New power state %s -> %s", ONOFF(cs.power_state), ONOFF(power_state));
      ns.power_state = power_state;
      // если выключаем в авто-режиме и это не делает не авто-режим, то отключаем авто-режим
      if (!power_state && !call->get_auto_state().value_or(false)) {
        // TODO восстановить авто-режим при включении
        // возможно необходимо исследовать тему CommSource и применять их совместно
        ns.auto_state = false;
      }
    }
  }

  if (call->get_heater_state().has_value()) {
    const auto heater_state = *call->get_heater_state();
    if (cs.heater_state != heater_state) {
      TION_LOGD(TAG, "New heater state %s -> %s", ONOFF(cs.heater_state), ONOFF(heater_state));
      ns.heater_state = heater_state;
    }
  }

  if (call->get_target_temperature().has_value()) {
    const auto target_temperature = *call->get_target_temperature();
    if (cs.target_temperature != target_temperature) {
      TION_LOGD(TAG, "New target temperature %d -> %d", cs.target_temperature, target_temperature);
      ns.target_temperature = target_temperature;
    }
  }

  if (this->traits_.supports_sound_state) {
    if (call->get_sound_state().has_value()) {
      const auto sound_state = *call->get_sound_state();
      if (cs.sound_state != sound_state) {
        TION_LOGD(TAG, "New sound state %s -> %s", ONOFF(cs.sound_state), ONOFF(sound_state));
        ns.sound_state = sound_state;
      }
    }
  }

  if (this->traits_.supports_led_state) {
    if (call->get_led_state().has_value()) {
      const auto led_state = *call->get_led_state();
      if (cs.led_state != led_state) {
        TION_LOGD(TAG, "New led state %s -> %s", ONOFF(cs.led_state), ONOFF(led_state));
        ns.led_state = led_state;
      }
    }
  }

  if (this->traits_.supports_gate_position_change) {
    if (call->get_gate_position().has_value()) {
      auto gate_position = *call->get_gate_position();
      switch (gate_position) {
        case TionGatePosition::OUTDOOR: {
          break;
        }
        case TionGatePosition::INDOOR: {
          if (ns.heater_state) {
            TION_LOGW(TAG, "Indoor gate position disallow heater");
            ns.heater_state = false;
          }
          break;
        }
        case TionGatePosition::MIXED: {
          if (!this->traits_.supports_gate_position_change_mixed) {
            gate_position = cs.gate_position;
          }
          break;
        }
        default:
          gate_position = cs.gate_position;
          break;
      };
      if (cs.gate_position != gate_position) {
        TION_LOGD(TAG, "New gate position %u -> %u", static_cast<uint8_t>(cs.gate_position),
                  static_cast<uint8_t>(gate_position));
        ns.gate_position = gate_position;
      }
    }
  }

  if (this->traits_.supports_manual_antifreeze) {
    if (ns.power_state && !ns.heater_state && ns.outdoor_temperature < 0) {
      TION_LOGW(TAG, "Antifreeze protection has worked. Heater now enabled.");
      ns.heater_state = true;
    }
  }

  return ns;
}

void TionStateCall::dump() const {
  TION_DUMP(TAG, "TionStateCall:");
  if (this->fan_speed_.has_value()) {
    TION_DUMP(TAG, "  fan     : %u", *this->fan_speed_);
  }
  if (this->target_temperature_.has_value()) {
    TION_DUMP(TAG, "  target T: %d", *this->target_temperature_);
  }
  if (this->gate_position_.has_value()) {
    TION_DUMP(TAG, "  gate pos: %u", static_cast<uint8_t>(*this->gate_position_));
  }
  if (this->power_state_.has_value()) {
    TION_DUMP(TAG, "  power   : %s", ONOFF(*this->power_state_));
  }
  if (this->heater_state_.has_value()) {
    TION_DUMP(TAG, "  heater  : %s", ONOFF(*this->heater_state_));
  }
  if (this->auto_state_.has_value()) {
    TION_DUMP(TAG, "  auto    : %s", ONOFF(*this->auto_state_));
  }
  if (this->sound_state_.has_value()) {
    TION_DUMP(TAG, "  sound   : %s", ONOFF(*this->sound_state_));
  }
  if (this->led_state_.has_value()) {
    TION_DUMP(TAG, "  led     : %s", ONOFF(*this->led_state_));
  }
}

void TionStateCall::perform() {
  if (this->auto_state_.value_or(false)) {
    // сделаем сброс накопленных ошибок
    this->api_->auto_update(0, nullptr);
  }
  if (this->has_changes()) {
    this->api_->write_state(this);
    this->reset();
  }
}

bool TionStateCall::has_changes() const {
  return this->fan_speed_.has_value()              //-//
         || this->power_state_.has_value()         //-//
         || this->heater_state_.has_value()        //-//
         || this->target_temperature_.has_value()  //-//
         || this->sound_state_.has_value()         //-//
         || this->led_state_.has_value()           //-//
         || this->gate_position_.has_value()       //-//
         || this->auto_state_.has_value()          //-//
      ;
}

void TionStateCall::reset() {
  this->fan_speed_.reset();
  this->power_state_.reset();
  this->heater_state_.reset();
  this->target_temperature_.reset();
  this->sound_state_.reset();
  this->led_state_.reset();
  this->gate_position_.reset();
  this->auto_state_.reset();
}

TionApiBase::TionApiBase() : auto_pi_(TION_AUTO_KP, TION_AUTO_TI, TION_AUTO_DB) {
  this->traits_.boost_time = TION_BOOST_TIME;
}

void TionApiBase::notify_state_(uint32_t request_id) {
  TionStateCall *call = nullptr;

  if (this->state_.boost_time_left > 0) {
    // если изменили скорость вентиляции или выключили бризер
    if (this->state_.fan_speed != this->traits_.max_fan_speed || !this->state_.power_state) {
      TION_LOGD(TAG, "Boost canceled by user action");
      // пересохраняем изменившиеся данные, для восстановления
      this->boost_save_state_();
      if (call == nullptr) {
        call = new TionStateCall(this);
      }
      this->boost_cancel_(call);
    } else {
      // только если натив буст не поддерживается
      if (!this->traits_.supports_boost) {
        const auto boost_work_time = this->state_.work_time - this->boost_save_.start_time;
        if (boost_work_time < this->traits_.boost_time) {
          this->state_.boost_time_left = this->traits_.boost_time - boost_work_time;
        } else {
          if (call == nullptr) {
            call = new TionStateCall(this);
          }
          this->boost_cancel_(call);
        }
      }
      TION_DUMP(TAG, "Boost time left %d s", this->state_.boost_time_left);
    }
  }

  if (this->active_preset_ != PRESET_NONE) {
    auto is_preset_modified = [](const PresetData &pr, const TionState &st) -> bool {
      if (pr.power_state >= 0 && pr.power_state != st.power_state) {
        return true;
      }
      if (pr.heater_state >= 0 && pr.heater_state != st.heater_state) {
        return true;
      }
      if (pr.fan_speed > 0 && pr.fan_speed != st.fan_speed) {
        return true;
      }
      if (pr.target_temperature != 0 && pr.target_temperature != st.target_temperature) {
        return true;
      }
      if (pr.gate_position != TionGatePosition::NONE && pr.gate_position != st.gate_position) {
        return true;
      }
      if (pr.auto_state >= 0 && pr.auto_state != st.auto_state) {
        return true;
      }
      return false;
    };
    if (is_preset_modified(this->presets_[this->active_preset_], this->state_)) {
      this->active_preset_ = PRESET_NONE;
    }
  }

  if (this->traits_.supports_manual_antifreeze) {
    const auto &cs = this->state_;
    if (cs.power_state && !cs.heater_state && cs.outdoor_temperature < 0) {
      TION_LOGW(TAG, "Antifreeze protection has worked. Heater now enabled.");
      if (call == nullptr) {
        call = new TionStateCall(this);
      }
      call->set_heater_state(true);
    }
  }

  if (call) {
    call->perform();
    delete call;
  }

  this->on_state_fn.call_if(this->state_, request_id);
}

void TionApiBase::set_boost_time(uint16_t boost_time) {
  TION_LOGD(TAG, "New boost time: %u s", boost_time);
  this->traits_.boost_time = boost_time;
}

void TionApiBase::set_boost_heater_state(bool heater_state) {
  const int8_t st = heater_state ? 1 : 0;
  if (this->traits_.boost_heater_state != st) {
    TION_LOGD(TAG, "New boost heater state: %s", ONOFF(heater_state));
    this->traits_.boost_heater_state = st;
  }
}

void TionApiBase::set_boost_target_temperature(int8_t target_temperature) {
  if (this->traits_.boost_target_temperature != target_temperature) {
    if (target_temperature < this->traits_.min_target_temperature ||
        target_temperature > this->traits_.max_target_temperature) {
      TION_LOGD(TAG, "Boost target temperature is out of range %d:%d °C", this->traits_.min_target_temperature,
                this->traits_.max_target_temperature);
      return;
    }
    TION_LOGD(TAG, "New boost target temperature: %d °C", target_temperature);
    this->traits_.boost_target_temperature = target_temperature;
  }
}

void TionApiBase::enable_boost(bool state, TionStateCall *call) {
  if (call == nullptr) {
    INVALID_STATE_CALL();
    return;
  }

  if (!this->state_.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized.");
    return;
  }

  TION_LOGD(TAG, "Switching boost to %s", ONOFF(state));
  if (this->traits_.supports_boost) {
    this->boost_enable_native_(state);
    return;
  }

  const uint16_t new_boost_time = state ? this->traits_.boost_time : 0U;
  this->enable_boost(new_boost_time, call);
}

void TionApiBase::enable_boost(uint16_t boost_time, TionStateCall *call) {
  if (call == nullptr) {
    INVALID_STATE_CALL();
    return;
  }

  if (!this->state_.is_initialized()) {
    TION_LOGW(TAG, "State was not initialized.");
    return;
  }

  if (boost_time > 0) {
    this->boost_enable_(boost_time, call);
  } else {
    this->boost_cancel_(call);
  }
}

void TionApiBase::boost_enable_(uint16_t boost_time, TionStateCall *call) {
  if (this->state_.boost_time_left > 0) {
    TION_LOGW(TAG, "Boost is already in progress, time left %u s", this->state_.boost_time_left);
    return;
  }

  if (this->state_.fan_speed == this->traits_.max_fan_speed) {
    TION_LOGW(TAG, "Fan is already running at maximum speed");
    return;
  }

  if (boost_time == 0) {
    TION_LOGW(TAG, "Boost time is not configured");
    return;
  }

  this->boost_save_state_();
  TION_LOGD(TAG, "Schedule boost for %d s", boost_time);
  this->state_.boost_time_left = boost_time;

  call->set_power_state(true);
  call->set_fan_speed(this->traits_.max_fan_speed);
  call->set_gate_position(TionGatePosition::OUTDOOR);
  if (this->traits_.boost_heater_state >= 0) {
    call->set_heater_state(this->traits_.boost_heater_state > 0);
  }
  if (this->traits_.boost_target_temperature != 0) {
    call->set_target_temperature(this->traits_.boost_target_temperature);
  }
  // дополнительно оставим авто-режим в текущем положении
  call->set_auto_state(this->state_.auto_state);
}

void TionApiBase::boost_save_state_() {
  this->boost_save_.start_time = this->state_.work_time;
  this->boost_save_.power_state = this->state_.power_state;
  this->boost_save_.heater_state = this->state_.heater_state;
  this->boost_save_.fan_speed = this->state_.fan_speed;
  this->boost_save_.target_temperature = this->state_.target_temperature;
  this->boost_save_.gate_position = this->state_.gate_position;
  this->boost_save_.auto_state = this->state_.auto_state;
}

void TionApiBase::boost_cancel_(TionStateCall *call) {
  if (!(this->state_.boost_time_left > 0)) {
    return;
  }
  TION_LOGD(TAG, "Boost finished");
  this->state_.boost_time_left = 0;
  this->preset_enable_(this->boost_save_, call);
}

void TionApiBase::preset_enable_(const PresetData &preset, TionStateCall *call) {
  if (call == nullptr) {
    INVALID_STATE_CALL();
    return;
  }
  if (preset.power_state >= 0) {
    call->set_power_state(preset.power_state > 0);
  }
  if (preset.heater_state >= 0) {
    call->set_heater_state(preset.heater_state > 0);
  }
  if (preset.fan_speed != 0) {
    call->set_fan_speed(preset.fan_speed);
  }
  if (preset.target_temperature != 0) {
    call->set_target_temperature(preset.target_temperature);
  }
  if (preset.gate_position != TionGatePosition::UNKNOWN) {
    call->set_gate_position(preset.gate_position);
  }
  if (preset.auto_state >= 0) {
    call->set_auto_state(preset.auto_state > 0);
  }
}

void TionApiBase::enable_preset(const std::string &preset, TionStateCall *call) {
  TION_LOGD(TAG, "Activate preset '%s'", preset.c_str());
  if (preset.empty() || strcasecmp(preset.c_str(), PRESET_NONE) == 0) {
    this->active_preset_ = preset;
    return;
  }
  const auto &it = this->presets_.find(preset);
  if (it == this->presets_.end()) {
    TION_LOGD(TAG, "Preset '%s' not found", preset.c_str());
    return;
  }
  this->active_preset_ = preset;
  this->preset_enable_(it->second, call);
}

std::set<std::string> TionApiBase::get_presets() const {
  std::set<std::string> presets;
  presets.emplace(PRESET_NONE);
  for (auto &&preset : this->presets_) {
    presets.emplace(preset.first);
  }
  return presets;
};

TionApiBase::PresetData TionApiBase::get_preset(const std::string &name) const {
  const auto &it = this->presets_.find(name);
  if (it != this->presets_.end()) {
    return it->second;
  }
  return {};
}

void TionApiBase::add_preset(const std::string &name, const PresetData &data) {
  if (name.empty()) {
    TION_LOGW(TAG, "Empty preset name");
    return;
  }
  if (strcasecmp(name.c_str(), PRESET_NONE) == 0) {
    TION_LOGW(TAG, "Skip reserved preset 'none'");
    return;
  }
  if (data.target_temperature == 0 && data.heater_state < 0 && data.power_state < 0 && data.fan_speed == 0 &&
      data.gate_position == TionGatePosition::UNKNOWN && data.auto_state < 0) {
    TION_LOGW(TAG, "Preset '%s' has no data to change", name.c_str());
    return;
  }
  if (data.target_temperature != 0 && (data.target_temperature < this->traits_.min_target_temperature ||
                                       data.target_temperature > this->traits_.max_target_temperature)) {
    TION_LOGW(TAG, "Preset '%s' has invalid target temperature %d", name.c_str(), data.target_temperature);
    return;
  }
  if (data.fan_speed > this->traits_.max_fan_speed) {
    TION_LOGW(TAG, "Preset '%s' has invalid fan speed %u", name.c_str(), data.fan_speed);
    return;
  }
  TION_LOGD(TAG, "Setup preset '%s': power=%d, heat=%d, fan=%u, temp=%d, gate=%u", name.c_str(), data.power_state,
            data.heater_state, data.fan_speed, data.target_temperature, static_cast<uint8_t>(data.gate_position));
  this->presets_.insert_or_assign(name, data);
}

void TionApiBase::set_auto_pi_data(float kp, float ti, int db) {
  if (kp > 0 && ti > 0) {
    this->auto_pi_.reset(kp, ti, db);
  } else {
    TION_LOGW(TAG, "Invalid Kp=%.04f or Ti=%.04f", kp, ti);
  }
}

void TionApiBase::set_auto_min_fan_speed(uint8_t min_fan_speed) {
  if (min_fan_speed > this->traits_.max_fan_speed - 1) {
    TION_LOGW(TAG, "Invalid min fan speed %u", min_fan_speed);
    return;
  }
  this->auto_min_fan_speed_ = min_fan_speed;
  TION_LOGD(TAG, "New auto min fan speed: %u", this->auto_min_fan_speed_);

  if (min_fan_speed >= this->auto_max_fan_speed_) {
    this->auto_max_fan_speed_ = min_fan_speed + 1;
    TION_LOGD(TAG, "Fix auto max fan speed: %u", this->auto_max_fan_speed_);
  }

  this->auto_update_fan_speed_();
}

void TionApiBase::set_auto_max_fan_speed(uint8_t max_fan_speed) {
  if (max_fan_speed < 1 || max_fan_speed > this->traits_.max_fan_speed) {
    TION_LOGW(TAG, "Invalid max fan speed %u", max_fan_speed);
    return;
  }

  this->auto_max_fan_speed_ = max_fan_speed;
  TION_LOGD(TAG, "New auto max fan speed: %u", this->auto_max_fan_speed_);

  if (max_fan_speed <= this->auto_min_fan_speed_) {
    this->auto_min_fan_speed_ = max_fan_speed - 1;
    TION_LOGD(TAG, "Fix auto min fan speed: %u", this->auto_min_fan_speed_);
  }

  this->auto_update_fan_speed_();
}

void TionApiBase::auto_update_fan_speed_() {
  this->auto_pi_.set_min(this->traits_.auto_prod[this->auto_min_fan_speed_]);
  this->auto_pi_.set_max(this->traits_.auto_prod[this->auto_max_fan_speed_]);
  this->on_state_fn.call_if(this->state_, 0);
}

bool TionApiBase::auto_update(uint16_t current, TionStateCall *call) {
  TION_LOGV(TAG, "Auto update to %u", current);
  // спец обработка для сброса
  if (current == 0) {
    if (!this->auto_update_func_) {
      this->auto_pi_.reset();
    }
    return false;
  }

  if (!this->state_.auto_state) {
    return false;
  }

  if (call == nullptr) {
    INVALID_STATE_CALL();
    return false;
  }

  uint8_t fan_speed = this->state_.fan_speed;

  if (this->auto_update_func_) {
    fan_speed = this->auto_update_func_(current);
    if (fan_speed < this->auto_min_fan_speed_) {
      fan_speed = this->auto_min_fan_speed_;

    } else if (fan_speed > this->auto_max_fan_speed_) {
      fan_speed = this->auto_max_fan_speed_;
    }
  } else {
    fan_speed = this->auto_pi_update_(current);
  }
  if (fan_speed == this->state_.fan_speed) {
    return false;
  }
  if (this->state_.boost_time_left > 0) {
    return false;
  }
  TION_LOGV(TAG, "Auto new fan speed %u", fan_speed);
  // для понимания, что переключение было из авто-режима, всегда выставляем авто
  call->set_auto_state(true);
  call->set_fan_speed(fan_speed);
  return true;
}

uint8_t TionApiBase::auto_pi_update_(uint16_t current) {
  int rate = this->auto_pi_.update(this->auto_setpoint_, current);
  TION_LOGV(TAG, "Auto PI rate: %d", rate);
  if (rate > 0) {
    // приводим m^3/h в скорость вентиляции
    for (auto i = this->traits_.max_fan_speed; i > 0; i--) {
      int test = this->traits_.auto_prod[i - 1];
      if (rate > test) {
        // отсечем нижний предел
        if (i < this->auto_min_fan_speed_) {
          return this->auto_min_fan_speed_;
        }
        // отсечем верхний предел
        if (i > this->auto_max_fan_speed_) {
          return this->auto_max_fan_speed_;
        }
        // gotcha
        return i;
      }
    }
  }
  // не нашли подходящего значения, работаем по-минимуму
  return this->auto_min_fan_speed_;
}

bool TionApiBase::auto_is_valid() const {
  return !!this->auto_update_func_ ||
         (this->auto_setpoint_ > 400 && this->auto_min_fan_speed_ < this->auto_max_fan_speed_);
}

}  // namespace tion
}  // namespace dentra
