#include "esphome.h"

#include "CG_RadSens.h"

#include <CountsPerMinute.h>

#define SECONDS_PER_INTERVAL 5

using namespace esphome;
class MyRadSens: public PollingComponent, public CustomAPIDevice {
  public: Sensor * IntensityDynamic_Sensor = new Sensor();
  Sensor * IntensityStatic_Sensor = new Sensor();
  Sensor * CurrentCPM_Sensor = new Sensor();
  Sensor * MaxCPM_Sensor = new Sensor();
  Sensor * Sensivity_Sensor = new Sensor();
  CG_RadSens myself {
    RS_DEFAULT_I2C_ADDRESS
  };
  CountsPerMinute cpm;
  MyRadSens(): PollingComponent(SECONDS_PER_INTERVAL * 1000) {}

  uint32_t pulsesPrev = 0;
  int current_sensivity = 0;

  void on_set_sensivity(int sensivity) {
    myself.setSensitivity(sensivity);
    ESP_LOGD("Sensivity", "Set to %d", sensivity);
  }

  void setup() override {
    myself.init();
    myself.setLedState(true);
    myself.setSensitivity(105);
    cpm.init(60 / SECONDS_PER_INTERVAL);
    register_service( & MyRadSens::on_set_sensivity, "set_sensivity", {
      "sensivity"
    });
  }

  void update() override {
    float IntensityDynamic = myself.getRadIntensyDynamic();
    float IntensityStatic = myself.getRadIntensyStatic();
    int Sensivity = myself.getSensitivity();
    int Pulses = myself.getNumberOfPulses();
    if (Pulses > pulsesPrev) {
      cpm.add(Pulses - pulsesPrev);
    }
    if (cpm.isReady()) {
      CurrentCPM_Sensor -> publish_state(cpm.getCurrentCpm());
      MaxCPM_Sensor -> publish_state(cpm.getMaximumCpm());
    }
    if (IntensityDynamic != 0) {
      IntensityDynamic_Sensor -> publish_state(IntensityDynamic);
    }
    if (IntensityStatic != 0) {
      IntensityStatic_Sensor -> publish_state(IntensityStatic);
    }
    if (current_sensivity != Sensivity) {
      Sensivity_Sensor -> publish_state(Sensivity);
    }
    pulsesPrev = Pulses;
    current_sensivity = Sensivity;
  }
};
