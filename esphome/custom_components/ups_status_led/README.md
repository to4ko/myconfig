# UPS Status LED Component

A smart LED status indicator for UPS monitoring that uses the UPS HID component's data provider.

## Features

- **🎨 Automatic Status Display**: Priority-based patterns for different UPS states
- **🌙 Night Mode**: Automatic brightness dimming during specified hours
- **🏠 Home Assistant Integration**: Control LED, night mode, and brightness from HA
- **🔌 Hardware Agnostic**: Works with any ESPHome light component

## LED Patterns

The component automatically displays these solid color patterns based on UPS status (priority order):

1. **🔴 Critical Alert** (Solid red) - Low battery, fault, or overload
2. **🟠 Battery Power** (Solid orange) - Running on battery
3. **🟡 Charging** (Solid yellow) - Battery charging while online
4. **🟢 Normal** (Solid green) - Normal operation
5. **🔵 UPS Offline** (Solid blue) - UPS disconnected
6. **🟣 No Data** (Solid purple) - Component connected but no data
7. **⚪ Error** (Solid white) - Component error

## Configuration

### Basic Example

```yaml
# Time component (required for night mode)
time:
  - platform: sntp
    id: sntp_time

# Physical LED (any light component)
light:
  - platform: esp32_rmt_led_strip
    pin: GPIO48
    num_leds: 1
    id: my_led
    internal: true  # Hide from HA

# UPS Status LED Controller
ups_status_led:
  ups_hid_id: ups_monitor      # UPS data provider
  light_id: my_led             # Physical LED
  time_id: sntp_time           # Time source
```

### Full Configuration

```yaml
ups_status_led:
  id: ups_led_controller
  ups_hid_id: ups_monitor        # Required: UPS HID component ID
  light_id: status_led           # Required: Light component ID
  time_id: sntp_time             # Optional: Time component for night mode
  
  enabled: true                  # Enable/disable LED (default: true)
  brightness: 80%                # Base brightness 10-100% (default: 80%)
  
  # Battery color behavior
  battery_color_mode: gradient   # discrete or gradient (default: discrete)
  battery_low_threshold: 20      # Critical threshold % (default: 20)
  battery_warning_threshold: 50  # Warning threshold % (default: 50)
  
  # Night mode settings
  night_mode:
    enabled: true               # Enable night mode (default: true)
    brightness: 15%             # Night brightness (default: 15%)
    start_time: "22:00"        # Start time HH:MM (default: 22:00)
    end_time: "07:00"          # End time HH:MM (default: 07:00)
```

## Home Assistant Entities

The component automatically creates these entities (via `ups_led_controls.yaml`):

| Entity | Type | Description |
|--------|------|-------------|
| `switch.ups_status_led` | Switch | Enable/disable the LED |
| `switch.ups_led_night_mode` | Switch | Enable/disable night mode |
| `number.ups_led_brightness` | Number | Adjust brightness (10-100%) |
| `number.ups_led_night_brightness` | Number | Adjust night mode brightness (5-50%) |
| `number.ups_led_night_start_hour` | Number | Night mode start hour (0-23) |
| `number.ups_led_night_start_minute` | Number | Night mode start minute (0,15,30,45) |
| `number.ups_led_night_end_hour` | Number | Night mode end hour (0-23) |
| `number.ups_led_night_end_minute` | Number | Night mode end minute (0,15,30,45) |
| `text_sensor.ups_led_pattern` | Text | Current pattern being displayed |

## Performance

- **Update Rate**: 20Hz (50ms intervals)

## Data Provider Pattern

This component demonstrates the UPS HID data provider pattern:

```cpp
// Direct access to UPS data - no sensor entities needed!
if (ups_hid_->is_low_battery()) {
  // Show critical pattern
}

float battery = ups_hid_->get_battery_level();
// Adjust color based on battery level
```

## Supported Light Types

Works with any ESPHome light component:
- WS2812/NeoPixel strips
- RGB LEDs
- Single color LEDs (patterns only, no color)
- PWM LEDs
- FastLED compatible strips

## Example Automations

### Disable LED During Sleep Hours
```yaml
automation:
  - alias: "UPS LED Sleep Mode"
    trigger:
      platform: time
      at: "23:00:00"
    action:
      service: switch.turn_off
      target:
        entity_id: switch.ups_status_led
```

### Increase Brightness During Emergencies
```yaml
automation:
  - alias: "UPS Emergency Brightness"
    trigger:
      platform: state
      entity_id: text_sensor.ups_led_pattern
      to: "Critical"
    action:
      service: number.set_value
      target:
        entity_id: number.ups_led_brightness
      data:
        value: 100
```

### Toggle Night Mode Based on Presence
```yaml
automation:
  - alias: "UPS LED Night Mode Control"
    trigger:
      platform: state
      entity_id: binary_sensor.someone_home
    action:
      service: >
        switch.turn_{{ 'on' if trigger.to_state.state == 'off' else 'off' }}
      target:
        entity_id: switch.ups_led_night_mode
```

## Troubleshooting

### LED Not Working
- Verify UPS HID component is working: Check logs for UPS data
- Verify light component works: Try controlling it directly
- Check component logs: Enable `DEBUG` logging

### Night Mode Not Working
- Ensure time component is configured and has valid time
- Verify timezone is set correctly
- Check start/end times don't conflict

### Colors Look Wrong
- For RGB strips: Check `rgb_order` in light configuration
- For single-color LEDs: Only patterns work, not colors
- Try switching between discrete/gradient modes

## Debug Logging

```yaml
logger:
  logs:
    ups_status_led: DEBUG
```
