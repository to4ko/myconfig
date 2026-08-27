#include <cinttypes>
#include <ctime>

#include "esphome/core/log.h"
#include "tion_component.h"

namespace esphome {
namespace tion {

static const char *const TAG = "tion_api_component";
static const char *const STATE_TIMEOUT = "state_timeout";
static const char *const BATCH_TIMEOUT = "batch_timeout";

void TionApiComponent::BatchStateCall::perform() {
  this->start_time_ = millis();
  if (this->c_->batch_timeout_) {
    this->c_->set_timeout(BATCH_TIMEOUT, this->c_->batch_timeout_, [this]() { this->perform_(); });
  } else {
    this->perform_();
  }
}

void TionApiComponent::BatchStateCall::perform_() {
  ESP_LOGD(TAG, "Write out batch changes");
#ifdef TION_ENABLE_API_CONTROL_CALLBACK
  this->c_->control_callback_.call(this);
#endif
  dentra::tion::TionStateCall::perform();
  this->start_time_ = 0;
  this->c_->state_check_schedule_();
}

void TionApiComponent::call_setup() {
  PollingComponent::call_setup();
  if (this->state_timeout_ >= this->get_update_interval()) {
    ESP_LOGW(TAG, "Invalid state timeout: %.1f s", this->state_timeout_ * 0.001f);
    this->state_timeout_ = 0;
  }
}

// call_loop() был убран из esphome/core/component.h в ESPHome 2026.x:
// PollingComponent больше не переопределяет его (только virtual void loop()),
// а агрегация App.app_state_ / status LED теперь не зависит от того, что
// компонент переопределяет именно call_loop/loop - этот метод был чистым
// passthrough без собственной логики, поэтому просто убран как более не нужный.
void TionApiComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "%s:", LOG_STR_ARG(this->get_component_log_str()));
  LOG_UPDATE_INTERVAL(this);
  ESP_LOGCONFIG(TAG, "  Force update: %s", ONOFF(this->force_update_));
  ESP_LOGCONFIG(TAG, "  State timeout: %.1f s", this->state_timeout_ * 0.001f);
  ESP_LOGCONFIG(TAG, "  Batch timeout: %.1f s", this->batch_timeout_ * 0.001f);
  if (this->traits().supports_manual_antifreeze) {
    ESP_LOGCONFIG(TAG, "  Manual antifreeze: enabled");
  }
}

void TionApiComponent::update() {
  this->api_->request_state();
  this->state_check_schedule_();
}

void TionApiComponent::on_state_(const TionState &state, const uint32_t request_id) {
  ESP_LOGV(TAG, "State received, request_id: %" PRIu32, request_id);
  // clear error reporting
  this->status_clear_error();
  this->cancel_timeout(STATE_TIMEOUT);
  // notify state
  this->defer([this]() { this->state_callback_.call(&this->state()); });
}

void TionApiComponent::state_check_schedule_() {
  this->set_timeout(STATE_TIMEOUT, this->state_timeout_, [this]() {
    // error reporting
    if (this->status_has_error()) {
      ESP_LOGW(TAG, "State was not received in %.1f s", this->state_timeout_ * 0.001f);
    } else {
      // status_set_error() в ESPHome 2026.x принимает только const LogString*
      // (не const char*), и этот указатель сохраняется на будущее (см.
      // store_component_error_message() в esphome/core/component.cpp) -
      // передавать туда указатель на временную str_sprintf(...).c_str()
      // небезопасно (dangling pointer после конца выражения). Поэтому полное
      // сообщение с деталями логируем отдельно через ESP_LOGW (лог печатается
      // немедленно, временная строка тут безопасна), а в status_set_error
      // передаём только статический литерал через LOG_STR().
      ESP_LOGW(TAG, "State was not received in %.1f s", this->state_timeout_ * 0.001f);
      this->status_set_error(LOG_STR("State was not received"));
    }
    // notify subscribers
    this->state_callback_.call(nullptr);
  });
}

dentra::tion::TionStateCall *TionApiComponent::make_call() {
  const auto batch_start_time = this->batch_call_.get_start_time();
  if (batch_start_time != 0) {
    ESP_LOGD(TAG, "Continue batch update: %" PRIu32 " ms", millis() - batch_start_time);
  } else {
    ESP_LOGD(TAG, "Starting batch update: %" PRIu32 " ms", this->batch_timeout_);
  }
  return &this->batch_call_;
}

#ifdef TION_ENABLE_SCHEDULER

void Tion4sApiComponent::on_time(time_t time, uint32_t request_id) {
  auto *c_tm = std::gmtime(&time);
  char buf[20] = {};
  std::strftime(buf, sizeof(buf), "%F %T", c_tm);
  ESP_LOGI(TAG, "Device UTC time: %s", buf);
  c_tm = std::localtime(&time);
  std::strftime(buf, sizeof(buf), "%F %T", c_tm);
  ESP_LOGI(TAG, "Device local time: %s", buf);
}

void Tion4sApiComponent::on_timer(uint8_t timer_id, const dentra::tion_4s::tion4s_timer_t &timer, uint32_t request_id) {
  std::string schedule;
  if (timer.schedule.monday && timer.schedule.tuesday && timer.schedule.wednesday && timer.schedule.thursday &&
      timer.schedule.friday && timer.schedule.saturday && timer.schedule.sunday) {
    schedule = "MON-SUN";
  } else {
    auto add_timer_week_day = [](std::string &s, bool day, const char *day_name) {
      if (day) {
        if (!s.empty()) {
          s.append(", ");
        }
        s.append(day_name);
      }
    };
    add_timer_week_day(schedule, timer.schedule.monday, "MON");
    add_timer_week_day(schedule, timer.schedule.tuesday, "TUE");
    add_timer_week_day(schedule, timer.schedule.wednesday, "WED");
    add_timer_week_day(schedule, timer.schedule.thursday, "THU");
    add_timer_week_day(schedule, timer.schedule.friday, "FRI");
    add_timer_week_day(schedule, timer.schedule.saturday, "SAT");
    add_timer_week_day(schedule, timer.schedule.sunday, "SUN");
  }

  ESP_LOGI(TAG, "Timer[%u] %s at %02u:%02u is %s", timer_id, schedule.c_str(), timer.schedule.hours,
           timer.schedule.minutes, ONOFF(timer.timer_state));
}

void Tion4sApiComponent::on_timers_state(const dentra::tion_4s::tion4s_timers_state_t &timers_state,
                                         uint32_t request_id) {
  for (int i = 0; i < dentra::tion_4s::tion4s_timers_state_t::TIMERS_COUNT; i++) {
    ESP_LOGI(TAG, "Timer[%d] state %s", i, ONOFF(timers_state.timers[i].active));
  }
}

void Tion4sApiComponent::dump_timers() {
  this->typed_api()->request_time();
  for (uint8_t timer_id = 0; timer_id < dentra::tion_4s::tion4s_timers_state_t::TIMERS_COUNT; timer_id++) {
    this->typed_api()->request_timer(timer_id);
  }
  this->typed_api()->request_timers_state();
}

void Tion4sApiComponent::reset_timers() {
  const dentra::tion_4s::tion4s_timer_t timer{};
  for (uint8_t timer_id = 0; timer_id < dentra::tion_4s::tion4s_timers_state_t::TIMERS_COUNT; timer_id++) {
    this->typed_api()->write_timer(timer_id, timer);
  }
}
#endif  // TION_ENABLE_SCHEDULER

}  // namespace tion
}  // namespace esphome
