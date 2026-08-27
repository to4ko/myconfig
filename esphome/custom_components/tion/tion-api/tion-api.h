#pragma once

#include <cstddef>
#include <map>
#include <set>
#include <vector>
#include <type_traits>

#include <etl/delegate.h>

#include "tion-api-defines.h"
#include "utils.h"
#include "pi_controller.h"

namespace dentra {
namespace tion {

enum class CommSource : uint8_t { AUTO = 0, USER = 1 };

struct TionTraits {
  struct {
    bool supports_led_state : 1;
    bool supports_sound_state : 1;
    // supports set gate position. at least outdoor/indoor
    bool supports_gate_position_change : 1;
    // supports set gate position. outdoor/indoor/mixed
    bool supports_gate_position_change_mixed : 1;
    bool supports_heater_var : 1;
    bool supports_work_time : 1;
    bool supports_fan_time : 1;
    bool supports_airflow_counter : 1;
    bool supports_gate_error : 1;
    bool supports_pcb_ctl_temperature : 1;
    bool supports_pcb_pwr_temperature : 1;
    // true means manual antifreeze support
    bool supports_manual_antifreeze : 1;
    // true means native boost support
    bool supports_boost : 1;
    bool supports_reset_filter : 1;
    bool supports_kiv : 1;
  };

  using ErrorsDecodePtr = std::add_pointer_t<std::string(uint32_t errors)>;
  ErrorsDecodePtr errors_decode{};
  using ErrorsReportPtr = std::add_pointer_t<void(uint32_t errors)>;
  ErrorsReportPtr errors_report{};

  // Время работы режима "Турбо" в секундах.
  uint16_t boost_time;
  // <0 - текущий режим работы, =0 - обогрев выключен, >0 - обогрев включен.
  int8_t boost_heater_state;
  // 0 - используем текущую целевую температуру.
  int8_t boost_target_temperature;

  // Максимальная скорость вентиляции.
  uint8_t max_fan_speed;
  // Минимальная целевая температура.
  int8_t min_target_temperature;
  // Максимальная целевая температура.
  int8_t max_target_temperature;

  // Мощность тэна в Вт * 0.1. Например, для 3S, значение будет 145.
  // Может быть 0, если тэн отсутствует, актуально для моделей с индексом ECO.
  // 4s: 1000 и 1400, по паспорту 1000 и 800 (EU)
  // lt: 1000, по паспорту 850
  // 3s: 1450
  // o2: 1450
  uint8_t max_heater_power;
  // Потребление энергии без обогревателя для всех скоростей в Вт * 100,
  // включая 0 - режим ожидания (standby), 1 - первая скорость и т.д.
  uint16_t max_fan_power[7];

  uint16_t get_max_heater_power() const { return TION__HEAT_CONST_TO_POWER(this->max_heater_power); }
  float get_max_fan_power(size_t fan_speed) const { return TION__FAN_CONST_TO_POWER(this->max_fan_power[fan_speed]); }

  /// Массив производительностей бризера для каждой скорости, включая 0.
  const uint8_t *auto_prod;
};

enum class TionGatePosition : uint8_t {
  OUTDOOR = 0,
  INDOOR = 1,
  MIXED = 2,
  UNKNOWN = 0xF,
  OPENED = OUTDOOR,
  CLOSED = INDOOR,
  NONE = UNKNOWN,
};

class TionState {
 public:
  struct {
    // Состояние вкл/выкл.
    bool power_state : 1;
    // Состояние обогревателя вкл/выкл.
    bool heater_state : 1;
    // Состояние звуковых оповещений.
    bool sound_state : 1;
    // Состояние световых оповещений.
    bool led_state : 1;
    // Автоматическое управление.
    bool auto_state : 1;
    // Предупреждение о необходимости замены фильтра.
    bool filter_state : 1;
    // Ошибка заслонки.
    bool gate_error_state : 1;
    // Источник изменений.
    CommSource comm_source : 1;
  };

  struct {
    bool initialized : 1;
    // Скорость вентиляции.
    // 4s, 3s, lt: [1-6]
    // o2: [1-4]
    uint8_t fan_speed : 3;
    // Позиция заслонки. 0 - закрыто, 1 - открыто, 2 - открыто частично
    // 4s: 0 - рециркуляция, 1 - забор воздуха
    // lt: 0 - закрыто, 1 - открыто
    // 3s: 0 - рециркуляция, 1 - забор воздуха, 2 - смешанный режим
    // o2: 0 - закрыто, 1 - открыто
    TionGatePosition gate_position : 4;
  };

  // Температура до нагревателя.
  int8_t outdoor_temperature;
  // Температура после нагревателя.
  int8_t current_temperature;
  // Целевая температура.
  int8_t target_temperature;
  // Производительность бризера в m3.
  uint8_t productivity;

  // Текущая потребляемая мощность тэна.
  uint8_t heater_var;

  // Время наработки бризера в секундах.
  uint32_t work_time;
  // Время наработки вентилятора в секундах.
  uint32_t fan_time;
  // Остаточный ресурс фильтра в секундах.
  uint32_t filter_time_left;
  // Счетчик воздуха прошедшего через бризер.
  uint32_t airflow_counter;
  // Счетчик воздуха прошедшего через бризер m3.
  float airflow_m3;

  // Оставшееся время работы режима "турбо" в секундах или 0 если он выключен.
  uint16_t boost_time_left;

  uint16_t firmware_version;
  uint16_t hardware_version;

  // Температура платы управления (4s/lt only).
  int8_t pcb_ctl_temperature;
  // Температура силовой платы (4s only).
  int8_t pcb_pwr_temperature;

  //////////// 4S/LT
  // 4s: EC01,02,03 - ошибка заслонки
  // o2: EC05 - ошибка заслонки
  // 3s: EC05 - ошибка заслонки
  uint32_t errors;

  bool get_gate_state() const { return this->gate_position == TionGatePosition::OPENED; }

  // Текущая потребляемая мощность в Вт.
  float get_heater_power(const TionTraits &traits) const;
  // Потребляет ли сейчас обогреватель энергию.
  bool is_heating(const TionTraits &traits) const;

  // backward compatibility methods
  bool is_initialized() const { return this->initialized || this->fan_speed > 0; }
  const char *get_gate_position_str(const TionTraits &traits) const;
  void dump(const char *tag, const TionTraits &traits) const;
};

class TionApiBase;
class TionStateCall {
 public:
  TionStateCall(TionApiBase *api) : api_(api) {}
  virtual ~TionStateCall() {}

  void set_fan_speed(uint8_t fan_speed) { this->fan_speed_ = fan_speed; }
  void set_target_temperature(int8_t target_temperature) { this->target_temperature_ = target_temperature; }
  void set_power_state(bool power_state) { this->power_state_ = power_state; }
  void set_heater_state(bool heater_state) { this->heater_state_ = heater_state; }
  void set_led_state(bool led_state) { this->led_state_ = led_state; }
  void set_sound_state(bool sound_state) { this->sound_state_ = sound_state; }
  void set_gate_position(TionGatePosition gate_position) { this->gate_position_ = gate_position; }
  void set_auto_state(bool auto_state) { this->auto_state_ = auto_state; }

  const optional<uint8_t> &get_fan_speed() const { return this->fan_speed_; }
  const optional<bool> &get_power_state() const { return this->power_state_; }
  const optional<bool> &get_heater_state() const { return this->heater_state_; }
  const optional<int8_t> &get_target_temperature() const { return this->target_temperature_; }
  const optional<bool> &get_sound_state() const { return this->sound_state_; }
  const optional<bool> &get_led_state() const { return this->led_state_; }
  const optional<TionGatePosition> &get_gate_position() const { return this->gate_position_; }
  const optional<bool> &get_auto_state() const { return this->auto_state_; }

  // additional helper.
  void set_gate_state(bool gate_state) {
    this->gate_position_ = gate_state ? TionGatePosition::OPENED : TionGatePosition::CLOSED;
  }

  virtual void perform();

  bool has_changes() const;
  void reset();

  void dump() const;

 protected:
  TionApiBase *api_;
  optional<uint8_t> fan_speed_;
  optional<bool> power_state_;
  optional<bool> heater_state_;
  optional<int8_t> target_temperature_;
  optional<bool> sound_state_;
  optional<bool> led_state_;
  optional<TionGatePosition> gate_position_;
  optional<bool> auto_state_;
};

#define TION_REPORT_EC(tag, code, msg) TION_LOGW(tag, "EC%02u: %s", err, msg);
#define TION_REPORT_WS(tag, code, msg) TION_LOGW(tag, "WS%02u: %s", err, msg);
#define TION_REPORT_EC_UNK(tag, code) TION_REPORT_EC(tag, code, "Неизвестная ошибка")
#define TION_REPORT_WS_UNK(tag, code) TION_REPORT_WS(tag, code, "Неизвестное предупреждение")

void enum_errors(uint32_t errors, uint8_t min_bit, uint8_t max_bit, const void *param,
                 const std::function<void(uint8_t, const void *)> &fn);

std::string decode_errors(uint32_t errors, uint8_t error_min_bit, uint8_t error_max_bit, uint8_t warning_min_bit,
                          uint8_t warning_max_bit);

class TionApiBase {
  /// Callback listener for response to request_state command request.
  using on_state_type = etl::delegate<void(const TionState &state, uint32_t request_id)>;
  /// Callback listener for response to send_heartbeat command request.
  using on_heartbeat_type = etl::delegate<void(uint8_t work_mode)>;

 public:
  TionApiBase();

  constexpr static const char *PRESET_NONE = "none";

  struct PresetData {
    // =0 - без изменений
    int8_t target_temperature;
    // <0 - без изменений, =0 - выкл, >0 - вкл
    int8_t heater_state;
    // <0 - без изменений, =0 - выкл, >0 - вкл
    int8_t power_state;
    // =0 - без изменений, >0 - вкл
    uint8_t fan_speed;
    // =UNKNOWN - без изменений
    TionGatePosition gate_position;
    // <0 - без изменений, =0 - выкл, >0 - вкл
    int8_t auto_state;
  };

  using on_ready_type = etl::delegate<void()>;
  /// Set callback listener for monitoring ready state
  void set_on_ready(on_ready_type &&on_ready) { this->on_ready_fn = on_ready; }

  on_ready_type on_ready_fn{};
  on_state_type on_state_fn{};
#ifdef TION_ENABLE_HEARTBEAT
  on_heartbeat_type on_heartbeat_fn{};
#endif

  // Returns last received state.
  const TionState &get_state() const { return this->state_; }
  const TionTraits &get_traits() const { return this->traits_; }

  virtual void request_state() = 0;
  virtual void write_state(TionStateCall *call) = 0;
  virtual void reset_filter() = 0;

  // Вызывающая сторона ответственна за вызов perform..
  void enable_boost(bool state, TionStateCall *call);
  void enable_boost(uint16_t boost_time, TionStateCall *call);
  void set_boost_time(uint16_t boost_time);
  void set_boost_heater_state(bool heater_state);
  void set_boost_target_temperature(int8_t target_temperature);
  // Вызывающая сторона ответственна за вызов perform.
  void enable_preset(const std::string &preset, TionStateCall *call);
  std::set<std::string> get_presets() const;
  bool has_presets() const { return !this->presets_.empty(); }
  void add_preset(const std::string &name, const PresetData &data);
  PresetData get_preset(const std::string &name) const;
  const std::string &get_active_preset() const { return this->active_preset_; }
  /// Вызывающая сторона ответственна за вызов perform.
  /// @return true если были изменения и требуются выполнить perform
  bool auto_update(uint16_t current, TionStateCall *call);
  void set_auto_pi_data(float kp, float ti, int db);
  void set_auto_setpoint(uint16_t setpoint) { this->auto_setpoint_ = setpoint; }
  void set_auto_min_fan_speed(uint8_t min_fan_speed);
  void set_auto_max_fan_speed(uint8_t max_fan_speed);
  uint16_t get_auto_setpoint() const { return this->auto_setpoint_; }
  uint8_t get_auto_min_fan_speed() const { return this->auto_min_fan_speed_; }
  uint8_t get_auto_max_fan_speed() const { return this->auto_max_fan_speed_; }
  void set_auto_update_func(std::function<uint8_t(uint16_t current)> &&func) {
    this->auto_update_func_ = std::move(func);
  }
  bool auto_is_valid() const;

 protected:
  TionTraits traits_{};
  TionState state_{};
  uint32_t request_id_{};

  TionState make_write_state_(TionStateCall *call) const;

  struct : public PresetData {
    uint32_t start_time;
  } boost_save_{};

  std::map<std::string, PresetData> presets_;
  std::string active_preset_{PRESET_NONE};

  auto_co2::PIController auto_pi_;
  int16_t auto_setpoint_{};
  uint8_t auto_min_fan_speed_{};
  uint8_t auto_max_fan_speed_{};
  std::function<uint8_t(uint16_t current)> auto_update_func_;

  void notify_state_(uint32_t request_id);
  virtual void boost_enable_native_(bool state) {}
  void boost_enable_(uint16_t boost_time, TionStateCall *call);
  void boost_cancel_(TionStateCall *call);
  void boost_save_state_();
  void preset_enable_(const PresetData &preset, TionStateCall *call);
  void auto_update_fan_speed_();
  uint8_t auto_pi_update_(uint16_t current);
};

}  // namespace tion
}  // namespace dentra
