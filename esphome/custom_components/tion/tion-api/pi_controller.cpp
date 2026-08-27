#include "log.h"
#include "pi_controller.h"

namespace dentra {
namespace tion {
namespace auto_co2 {

static const char *const TAG = "pi_controller";

void PIController::reset(float kp, float ti, int db) {
  this->kp_ = kp;
  this->ti_ = ti;
  this->db_ = db;
  this->reset();
}

void PIController::reset(float kp, float ti, int db, float min, float max) {
  this->kp_ = kp;
  this->ti_ = ti;
  this->db_ = db;
  this->v_oa_min_ = min;
  this->v_oa_max_ = max;
  this->reset();
}

float PIController::update(int setpoint, int current) {
  // 7: error from setpoint [ppm]
  const auto e = setpoint - current;

  // 8: error from setpoint, including dead band [ppm]
  const auto e_db =  //
      /**/ current < setpoint - this->db_ ? e - this->db_ :
      /**/ current > setpoint + this->db_ ? e + this->db_
                                          : 0;

  // 9: integral error [min.ppm-CO2]
  const float i = this->ib_ + (this->dt_s_() / 60.0f) * e_db;

  // 10: candidate outdoor airflow rate [L/s]
  const float v_oa_c = -this->kp_ * (e_db + (i / this->ti_));

  // 11: integral error with anti-integral windup [min.ppm-CO2]
  if (v_oa_c < this->v_oa_min_) {
    this->ib_ = -this->ti_ * (e_db + (this->v_oa_min_ / this->kp_));
  } else if (v_oa_c > this->v_oa_max_) {
    this->ib_ = -this->ti_ * (e_db + (this->v_oa_max_ / this->kp_));
  } else {
    this->ib_ = i;
  }

  // 12: outdoor airflow rate [L/s]
  const float v_oa = -this->kp_ * (e_db + (this->ib_ / this->ti_));

  return v_oa;
}

}  // namespace auto_co2
}  // namespace tion
}  // namespace dentra
