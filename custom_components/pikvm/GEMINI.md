# PiKVM Integration Internal Module Manifest (`pikvm`)

## Module Overview
This document specifies the internal contracts, dependency graph, and invariants for `custom_components/pikvm`.

## Dependency & Import Hierarchy
1. `const.py` (leaf module - constants only)
2. `utils.py` (helpers, depends on `const.py`, `pikvm-aio`)
3. `cert_handler.py` (SSL context & verification, depends on `pikvm-aio`)
4. `coordinator.py` (polling engine, depends on `const.py`, `utils.py`, `cert_handler.py`, `pikvm-aio`)
5. `entity.py` (base entity & description contract, depends on `coordinator.py`)
6. `sensor.py` & `binary_sensor.py` (platform implementations, depend on `coordinator.py`, `entity.py`, `utils.py`)
7. `options_flow.py` (options UI, depends on `const.py`)
8. `config_flow.py` (setup, reauth, & reconfigure UI, depends on `const.py`, `cert_handler.py`, `options_flow.py`, `utils.py`)
9. `diagnostics.py` (diagnostics dump, depends on `const.py`, `coordinator.py`)
10. `__init__.py` (root orchestrator, depends on all modules above)

## Behavioral Contracts & Lifecycle Invariants

### 1. `entry.runtime_data` & Storage
- `async_setup_entry` sets `entry.runtime_data = coordinator`.
- Platforms access the coordinator directly via `config_entry.runtime_data`.

### 2. Hardware Certificates & Websession Injection
- Stock PiKVM hardware certificates are self-signed without CA BasicConstraints or IP SANs.
- We fetch the PEM certificate via `fetch_serialized_cert` to detect new clients and encrypt traffic rather than for CA-chain host verification (`verify_ssl=False`, `check_hostname=False`).
- Home Assistant's shared `aiohttp.ClientSession` (`async_get_clientsession(hass)`) and pre-warmed no-verify `SSLContext` (`get_default_no_verify_context()`) are passed to `PiKVMClient` to satisfy Platinum rules `inject-websession` and `async-dependency`.

### 3. Authentication & 2FA Lifecycle
- When 2FA is active, KVMD expects credentials as `password + 6_digit_otp`.
- If 2FA is cleared/disabled on PiKVM, `CONF_TOTP` must be updated to `""` during reauth or reconfigure.
- In reauth and reconfigure flows, `totp_secret = user_input.get(CONF_TOTP, "").strip()`. Submitting empty string or whitespace explicitly clears the stored TOTP key without repopulating previous secrets.

### 4. Issue Registry (Repairs)
- Managed in `PiKVMDataUpdateCoordinator._async_check_hardware_health`.
- Issues registered under domain `pikvm`:
  - `undervoltage_{entry_id}`: `IssueSeverity.CRITICAL` if active now, `IssueSeverity.WARNING` if past flag set.
  - `throttling_{entry_id}`: `IssueSeverity.WARNING`.
- All issues must include `learn_more_url` linking to official PiKVM docs (`https://docs.pikvm.org/power/`, `https://docs.pikvm.org/`).
- Issues MUST be deleted via `async_delete_issue` as soon as the condition clears.

### 5. Sensor vs Binary Sensor Separation
- Any boolean/status telemetry MUST reside in `binary_sensor.py` (`throttling`, `msd_enabled`, `msd_drive`, `extra_<service>`).
- Continuous numeric telemetry MUST reside in `sensor.py` (`cpu_temp`, `cpu_utilization`, `memory_utilization`, `fan_speed`, `msd_storage`).
- All numeric sensors must declare `state_class=SensorStateClass.MEASUREMENT` and `native_unit_of_measurement` to participate in Long-Term Statistics.

### 6. Hassfest & Translation Constraints
- External URLs must never be placed inside `strings.json` descriptions (`data_description`). Use parameter placeholders or clean hostnames to pass `hassfest` translation validation.

### 7. Redaction Invariants
- `diagnostics.py` must redact all sensitive keys (`CONF_PASSWORD`, `CONF_TOTP`, `CONF_CERTIFICATE`, `token`, `secret`, `api_key`, `cookie`, `jwt`) from both config entry data and coordinator telemetry before returning.
