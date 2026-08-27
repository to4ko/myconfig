#include "esphome/core/log.h"

#include "tion_climate_helpers.h"
#include "tion_climate.h"

namespace esphome {
namespace tion {

static const char *const TAG = "tion_climate";

int find_climate_preset(const std::string &preset) {
#ifndef USE_ARDUINO
  const auto preset_upper = str_upper_case(preset);
  for (uint8_t i = climate::CLIMATE_PRESET_NONE; i <= climate::CLIMATE_PRESET_ACTIVITY; i++) {
    const auto preset_climate_index = static_cast<climate::ClimatePreset>(i);
    const auto preset_climate = LOG_STR_ARG(climate::climate_preset_to_string(preset_climate_index));
    if (preset_upper == preset_climate) {
      return preset_climate_index;
    }
  }
#endif
  return -1;
}

void TionClimate::setup() {
  ESP_LOGD(TAG, "Setting up %s...", this->get_name().c_str());

  // climate::ClimateTraits больше не хранит кастомные режимы вентилятора и
  // пресеты сама (ESPHome >= 2026.x); теперь это делает climate::Climate
  // через set_supported_custom_fan_modes()/set_supported_custom_presets(),
  // которые сохраняют не копии строк, а голые const char*, обязанные жить
  // вечно - поэтому исходные строки держим в custom_fan_modes_/custom_presets_
  // (члены класса, живут всё время жизни компонента), а не во временных
  // объектах. TionApiBase::get_presets() возвращает std::set<std::string> ПО
  // ЗНАЧЕНИЮ (проверено в tion-api.h) - использовать c_str() строк из этого
  // временного набора напрямую было бы небезопасно, поэтому копируем их.
  const auto max_fan_speed = this->parent_->traits().max_fan_speed;
  for (uint8_t i = 1, max = i + max_fan_speed; i < max; i++) {
    this->custom_fan_modes_.push_back(fan_speed_to_mode(i));
  }
  if (!this->custom_fan_modes_.empty()) {
    std::vector<const char *> modes;
    modes.reserve(this->custom_fan_modes_.size());
    for (const auto &mode : this->custom_fan_modes_) {
      modes.push_back(mode.c_str());
    }
    this->set_supported_custom_fan_modes(modes);
  }

  if (this->parent_->api()->has_presets()) {
    for (auto &&preset : this->parent_->api()->get_presets()) {
      // Пресеты, совпадающие со стандартными climate::ClimatePreset,
      // регистрируются в traits() через add_supported_preset(), а не здесь -
      // find_climate_preset() определяет, какие это.
      if (find_climate_preset(preset) < 0) {
        this->custom_presets_.push_back(preset);
      }
    }
    if (!this->custom_presets_.empty()) {
      std::vector<const char *> presets;
      presets.reserve(this->custom_presets_.size());
      for (const auto &preset : this->custom_presets_) {
        presets.push_back(preset.c_str());
      }
      this->set_supported_custom_presets(presets);
    }
  }

  this->parent_->add_on_state_callback([this](const TionState *state) {
    if (state) {
      this->on_state_(*state);
    }
  });
}

climate::ClimateTraits TionClimate::traits() {
  auto traits = climate::ClimateTraits();
  // set_supports_current_temperature()/set_supports_action() убраны из
  // ClimateTraits в ESPHome >= 2026.x, заменены на feature flags
  // (см. esphome/components/climate/climate_mode.h).
  traits.add_feature_flags(climate::CLIMATE_SUPPORTS_CURRENT_TEMPERATURE | climate::CLIMATE_SUPPORTS_ACTION);
  traits.set_visual_min_temperature(this->parent_->traits().min_target_temperature);
  traits.set_visual_max_temperature(this->parent_->traits().max_target_temperature);
  traits.set_visual_temperature_step(1.0f);
  traits.set_supported_modes({
      climate::CLIMATE_MODE_OFF,
      climate::CLIMATE_MODE_HEAT,
      climate::CLIMATE_MODE_FAN_ONLY,
  });
  if (this->enable_heat_cool_) {
    traits.add_supported_mode(climate::CLIMATE_MODE_HEAT_COOL);
  }
  if (this->parent_->traits().supports_kiv) {
    traits.add_supported_fan_mode(climate::CLIMATE_FAN_OFF);
  }
  if (this->enable_fan_auto_) {
    traits.add_supported_fan_mode(climate::CLIMATE_FAN_AUTO);
  }

  if (this->parent_->api()->has_presets()) {
    for (auto &&preset : this->parent_->api()->get_presets()) {
      const auto preset_index = find_climate_preset(preset);
      if (preset_index >= 0) {
        traits.add_supported_preset(static_cast<climate::ClimatePreset>(preset_index));
      }
      // Кастомные (не стандартные) пресеты регистрируются один раз в setup()
      // через this->set_supported_custom_presets() - Climate::get_traits()
      // сам подключает их сюда через ClimateTraits::set_supported_custom_presets_().
    }
  }
  // Кастомные режимы вентилятора аналогично регистрируются в setup() через
  // this->set_supported_custom_fan_modes().
  return traits;
}

void TionClimate::dump_config() {
  LOG_CLIMATE("", "Tion Climate", this);
  this->dump_traits_(TAG);
}

void TionClimate::control(const climate::ClimateCall &call) {
  auto *tion = this->parent_->make_call();

  if (this->parent_->api()->has_presets()) {
#ifndef USE_ARDUINO
    if (call.get_preset().has_value()) {
      const auto preset_climate = LOG_STR_ARG(climate::climate_preset_to_string(*call.get_preset()));
      for (auto &&preset : this->parent_->api()->get_presets()) {
        const auto preset_upper = str_upper_case(preset);
        if (preset_upper == preset_climate) {
          ESP_LOGD(TAG, "Set preset %s", preset.c_str());
          this->parent_->api()->enable_preset(preset, tion);
          break;
        }
      }
    }
#endif

    if (call.has_custom_preset()) {
      // ClimateCall::get_custom_preset() в ESPHome >= 2026.x возвращает
      // StringRef (не optional<std::string>): нет has_value()/operator*,
      // вместо этого has_custom_preset()/get_custom_preset().
      const auto preset = call.get_custom_preset();
      ESP_LOGD(TAG, "Set custom preset %s", preset.c_str());
      this->parent_->api()->enable_preset(preset.str(), tion);
    }
  }

  if (call.get_mode().has_value()) {
    const auto mode = *call.get_mode();
    ESP_LOGD(TAG, "Set mode %s", LOG_STR_ARG(climate::climate_mode_to_string(mode)));
    if (mode == climate::CLIMATE_MODE_OFF) {
      tion->set_power_state(false);
    } else {
      tion->set_power_state(true);
      if (mode != climate::CLIMATE_MODE_HEAT_COOL) {
        tion->set_heater_state(mode == climate::CLIMATE_MODE_HEAT);
      }
    }
  }

  if (call.get_fan_mode().has_value()) {
    const auto fan_mode = *call.get_fan_mode();
    if (this->enable_fan_auto_ && fan_mode == climate::CLIMATE_FAN_AUTO) {
      ESP_LOGD(TAG, "Set auto fan mode");
      tion->set_auto_state(true);
    }
    if (this->parent_->traits().supports_kiv && fan_mode == climate::CLIMATE_FAN_OFF) {
      ESP_LOGD(TAG, "Stopping fan");
      tion->set_fan_speed(0);
    }
  }

  if (call.has_custom_fan_mode()) {
    // Аналогично get_custom_preset(): get_custom_fan_mode() теперь StringRef.
    const auto fan_mode = call.get_custom_fan_mode();
    const auto fan_speed = fan_mode_to_speed(fan_mode);
    ESP_LOGD(TAG, "Set fan speed %u", fan_speed);
    tion->set_fan_speed(fan_speed);
  }

  if (call.get_target_temperature().has_value()) {
    const int8_t target_temperature = *call.get_target_temperature();
    ESP_LOGD(TAG, "Set target temperature %d °C", target_temperature);
    tion->set_target_temperature(target_temperature);
  }

  tion->perform();
}

void TionClimate::on_state_(const TionState &state) {
  bool has_changes = false;

  climate::ClimateMode mode;
  climate::ClimateAction action;
  if (!state.power_state) {
    mode = climate::CLIMATE_MODE_OFF;
    action = this->enable_fan_auto_ && state.auto_state && this->parent_->api()->get_auto_min_fan_speed() == 0
                 ? climate::CLIMATE_ACTION_IDLE
                 : climate::CLIMATE_ACTION_OFF;
  } else if (state.heater_state) {
    mode = climate::CLIMATE_MODE_HEAT;
    action = state.is_heating(this->parent_->traits())  //-//
                 ? climate::CLIMATE_ACTION_HEATING
                 : climate::CLIMATE_ACTION_FAN;
  } else {
    mode = climate::CLIMATE_MODE_FAN_ONLY;
    action = climate::CLIMATE_ACTION_FAN;
  }

  if (this->mode != mode) {
    this->mode = mode;
    has_changes = true;
  }
  if (this->action != action) {
    this->action = action;
    has_changes = true;
  }
  if (int8_t(this->current_temperature) != state.current_temperature) {
    this->current_temperature = state.current_temperature;
    has_changes = true;
  }
  if (int8_t(this->target_temperature) != state.target_temperature) {
    this->target_temperature = state.target_temperature;
    has_changes = true;
  }

  if (this->enable_fan_auto_ && state.auto_state) {
    if (this->set_fan_speed_(-1)) {
      has_changes = true;
    }
  } else if (this->set_fan_speed_(state.fan_speed)) {
    has_changes = true;
  }

  if (this->parent_->api()->has_presets()) {
    const auto active_preset = this->parent_->api()->get_active_preset();
#ifndef USE_ARDUINO
    const auto climate_preset = find_climate_preset(active_preset);
    if (climate_preset >= 0) {
      if (this->preset.value_or(static_cast<climate::ClimatePreset>(-1)) != climate_preset) {
        this->preset = static_cast<climate::ClimatePreset>(climate_preset);
        // custom_preset_ приватен в ESPHome >= 2026.x, сброс через clear_custom_preset_().
        this->clear_custom_preset_();
        has_changes = true;
      }
    } else
#endif
        if (this->get_custom_preset() != active_preset) {
      // set_custom_preset_() ищет active_preset среди строк, зарегистрированных
      // в setup() через set_supported_custom_presets(), и молча ничего не
      // делает, если совпадения нет (защита от висячих указателей на стороне
      // ESPHome) - в норме active_preset всегда входит в get_presets().
      if (this->set_custom_preset_(active_preset.c_str())) {
        this->preset.reset();
        has_changes = true;
      }
    }
  }

  if (this->parent_->get_force_update() || has_changes) {
    this->publish_state();
  }
}

bool TionClimate::set_fan_speed_(int8_t fan_speed) {
  // custom_fan_mode_ приватен в ESPHome >= 2026.x: чтение через
  // get_custom_fan_mode() (StringRef), сброс через clear_custom_fan_mode_(),
  // установка через set_custom_fan_mode_().
  if (fan_speed < 0) {
    if (!this->fan_mode.has_value() || *this->fan_mode != climate::CLIMATE_FAN_AUTO) {
      this->clear_custom_fan_mode_();
      this->fan_mode = climate::CLIMATE_FAN_AUTO;
      return true;
    }
    return false;
  }

  if (fan_speed == 0) {
    if (this->parent_->traits().supports_kiv) {
      if (!this->fan_mode.has_value() || *this->fan_mode != climate::CLIMATE_FAN_OFF) {
        this->clear_custom_fan_mode_();
        this->fan_mode = climate::CLIMATE_FAN_OFF;
        return true;
      }
    }
    if (this->mode != climate::CLIMATE_MODE_OFF) {
      ESP_LOGW(TAG, "Unsupported zero fan speed");
    }
    return false;
  }

  if (fan_speed <= this->parent_->traits().max_fan_speed) {
    if (fan_mode_to_speed(this->get_custom_fan_mode()) != fan_speed) {
      this->fan_mode.reset();
      // fan_speed_to_mode(fan_speed) должен совпадать с одной из строк,
      // зарегистрированных в setup() через set_supported_custom_fan_modes()
      // (те же "1".."N"), иначе set_custom_fan_mode_() молча не применится.
      this->set_custom_fan_mode_(fan_speed_to_mode(fan_speed).c_str());
      return true;
    }
    return false;
  }

  ESP_LOGW(TAG, "Unsupported fan speed: %u (max: %u)", fan_speed, this->parent_->traits().max_fan_speed);

  return false;
}

}  // namespace tion
}  // namespace esphome
