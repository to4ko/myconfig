# NUT Server Component for ESPHome

The `nut_server` component exposes UPS data from the `ups_hid` component via the Network UPS Tools (NUT) TCP protocol. This allows ESPHome devices to act as NUT servers, making UPS status and control available to NUT clients on the network.

## Features

- **Multi-client TCP Server**: Supports up to 10 simultaneous client connections (configurable)
- **NUT Protocol v2.8.0**: Compatible with standard NUT clients and monitoring tools
- **Authentication**: Optional username/password authentication for secure access
- **Real-time UPS Data**: Exposes live UPS status from the `ups_hid` component
- **Command Support**: Execute UPS commands like beeper control and battery tests
- **Thread-safe Design**: Proper mutex protection for concurrent client access
- **Non-blocking I/O**: Efficient event-driven architecture using FreeRTOS tasks

## Configuration

### Basic Configuration

```yaml
# Minimal configuration
nut_server:
  ups_hid_id: my_ups
```

### Advanced Configuration

```yaml
# Full configuration with all options
nut_server:
  ups_hid_id: my_ups           # Required: Reference to ups_hid component
  port: 3493                    # Optional: TCP port (default: 3493)
  ups_name: "office_ups"        # Optional: UPS name in NUT (default: ups_hid ID)
  username: "nutuser"           # Optional: Username for authentication
  password: "secretpass"        # Optional: Password (empty = no auth)
  max_clients: 4                # Optional: Max simultaneous clients (1-10, default: 4)
```

### Complete Example with UPS HID

```yaml
# UPS HID component configuration
ups_hid:
  id: my_ups
  update_interval: 10s

# NUT Server configuration
nut_server:
  ups_hid_id: my_ups
  port: 3493
  ups_name: "esphome_ups"
  username: "monitor"
  password: "ups123"
  max_clients: 5

# Optional: Network configuration
wifi:
  ssid: "YourWiFi"
  password: "YourPassword"
  
  # Static IP recommended for server
  manual_ip:
    static_ip: 192.168.1.100
    gateway: 192.168.1.1
    subnet: 255.255.255.0
```

## Supported NUT Commands

### Query Commands

| Command | Description | Authentication Required |
|---------|-------------|------------------------|
| `HELP` | Show available commands | No |
| `VERSION` | Get NUT protocol version | No |
| `NETVER` | Get network protocol version | No |
| `UPSDVER` | Get server version | No |
| `LIST UPS` | List available UPS devices | Yes* |
| `LIST VAR <ups>` | List all variables for UPS | Yes* |
| `GET VAR <ups> <var>` | Get specific variable value | Yes* |
| `LIST CMD <ups>` | List available commands | Yes* |
| `LIST CLIENTS` | List connected clients | Yes* |
| `LIST RW <ups>` | List read-write variables | Yes* |
| `LIST ENUM <ups> <var>` | List enum values for variable | Yes* |
| `LIST RANGE <ups> <var>` | List range for variable | Yes* |

*Authentication required only if password is configured

### Control Commands

| Command | Description | Authentication Required |
|---------|-------------|------------------------|
| `LOGIN <user> <pass>` | Authenticate client | No |
| `LOGOUT` | End authenticated session | No |
| `INSTCMD <ups> <cmd>` | Execute instant command | Yes* |

### Supported Instant Commands

The following instant commands are supported when the UPS hardware supports them:

- `beeper.enable` - Enable UPS beeper
- `beeper.disable` - Disable UPS beeper  
- `beeper.mute` - Temporarily mute beeper
- `test.battery.start.quick` - Start quick battery test (10-15 seconds)
- `test.battery.start.deep` - Start deep battery test (2-5 minutes)
- `test.battery.stop` - Stop battery test in progress

## Exposed NUT Variables

The following NUT variables are exposed based on available UPS data:

### Device Information
- `ups.mfr` - Manufacturer name
- `ups.model` - UPS model
- `ups.serial` - Serial number
- `ups.firmware` - Firmware version

### Battery Status
- `battery.charge` - Battery charge percentage (0-100)
- `battery.voltage` - Battery voltage
- `battery.runtime` - Estimated runtime in seconds
- `battery.type` - Battery chemistry type

### Power Status
- `input.voltage` - Input voltage from mains
- `output.voltage` - Output voltage to load
- `ups.load` - Load percentage (0-100)
- `ups.power` - Output power in watts
- `ups.status` - Combined status flags:
  - `OL` - Online (mains power present)
  - `OB` - On Battery
  - `LB` - Low Battery
  - `CHRG` - Charging
  - `TEST` - Test in progress
  - `ALARM` - Alarm condition

### Configuration
- `ups.delay.shutdown` - Shutdown delay in seconds
- `ups.delay.start` - Startup delay in seconds

## Client Connection Examples

### Using `upsc` (NUT client)

```bash
# List UPS status (no auth)
upsc esphome_ups@192.168.1.100

# List UPS status (with auth)
upsc -u monitor -p ups123 esphome_ups@192.168.1.100

# Get specific variable
upsc esphome_ups@192.168.1.100 battery.charge
```

### Using `telnet` for Testing

```bash
telnet 192.168.1.100 3493

# Commands to try:
HELP
VERSION
LOGIN monitor ups123
LIST UPS
LIST VAR esphome_ups
GET VAR esphome_ups battery.charge
LIST CMD esphome_ups
LIST CLIENTS
INSTCMD esphome_ups beeper.mute
LOGOUT
```

### Python Client Example

```python
import socket

def nut_query(host, port, commands):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    
    responses = []
    for cmd in commands:
        sock.send(f"{cmd}\n".encode())
        response = sock.recv(1024).decode()
        responses.append(response)
    
    sock.close()
    return responses

# Query UPS
host = "192.168.1.100"
port = 3493
commands = [
    "LOGIN monitor ups123",
    "LIST VAR esphome_ups",
    "LOGOUT"
]

results = nut_query(host, port, commands)
for r in results:
    print(r)
```

## Integration with NUT Monitoring Tools

### NUT Monitor (nut-monitor)
The component is compatible with GUI monitoring tools like `nut-monitor`. Configure the connection with:
- Host: ESP32 IP address
- Port: 3493 (or configured port)
- UPS Name: As configured in `ups_name`
- Username/Password: If authentication is enabled

### Home Assistant NUT Integration
You can use Home Assistant's NUT integration to monitor the UPS:

```yaml
# Home Assistant configuration.yaml
sensor:
  - platform: nut
    host: 192.168.1.100
    port: 3493
    username: monitor
    password: ups123
    resources:
      - battery.charge
      - battery.runtime
      - input.voltage
      - ups.load
      - ups.status
```

### Grafana + Prometheus
Use the NUT exporter for Prometheus to collect metrics:

```yaml
# prometheus-nut-exporter configuration
nut_servers:
  - name: esphome_ups
    host: 192.168.1.100
    port: 3493
    username: monitor
    password: ups123
```

## Design Patterns and Architecture

### Component Architecture

The NUT server component follows several design patterns for robustness:

1. **Server/Client Pattern**: Multi-client TCP server with connection management
2. **Command Pattern**: NUT protocol commands mapped to handler methods
3. **Observer Pattern**: Real-time UPS data updates from `ups_hid` component
4. **Strategy Pattern**: Authentication strategy (optional auth vs required)

### Thread Safety

- **Mutex Protection**: Client list and UPS data access protected by mutexes
- **Non-blocking I/O**: All socket operations are non-blocking
- **FreeRTOS Tasks**: Dedicated server task for handling connections
- **Timeout Management**: Automatic cleanup of inactive clients

### SOLID Principles

- **Single Responsibility**: Separate classes for server, client, and protocol handling
- **Open/Closed**: Extensible for new NUT commands without modifying core
- **Liskov Substitution**: Compatible with standard NUT protocol expectations
- **Interface Segregation**: Clean separation between UPS data provider and NUT server
- **Dependency Inversion**: Depends on `ups_hid` interface, not implementation

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check firewall rules allow TCP port 3493
   - Verify ESP32 is connected to network
   - Confirm server started successfully in logs

2. **Authentication Failed**
   - Verify username and password match configuration
   - Check for typos in credentials
   - Try without authentication first

3. **No UPS Data**
   - Ensure `ups_hid` component is working
   - Check USB connection to UPS
   - Verify UPS is supported by `ups_hid`

4. **Client Timeout**
   - Clients are disconnected after 60 seconds of inactivity
   - Send periodic queries to maintain connection
   - Increase client timeout if needed (requires code modification)

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  level: DEBUG
  logs:
    nut_server: DEBUG
    ups_hid: DEBUG
```

## Development Notes

### Adding New NUT Variables

To expose additional UPS data as NUT variables:

1. Ensure data is available in `UpsData` structure
2. Add mapping in `get_ups_var()` method
3. Include in `handle_list_var()` response

### Adding New Commands

To support additional instant commands:

1. Add command mapping in `execute_command()` method
2. Implement handler in `ups_hid` component if needed
3. Add to `get_available_commands()` list

### Future Enhancements

Planned improvements for future versions:

- [ ] Support for SET VAR (configure UPS settings)
- [ ] Event notifications (NOTIFY)
- [ ] Multiple UPS support (when multiple `ups_hid` components exist)
- [ ] Configurable client timeout
- [ ] Rate limiting for failed authentication attempts

## References

- [Network UPS Tools (NUT) Protocol](https://networkupstools.org/docs/developer-guide.chunked/ar01s09.html)
- [NUT Command Reference](https://networkupstools.org/docs/man/upsd.html)
- [ESPHome Component Development](https://esphome.io/custom/custom_component.html)
- [UPS HID Component Documentation](../ups_hid/README.md)
