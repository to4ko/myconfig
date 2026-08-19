#include "nut_server.h"
#include "../ups_hid/ups_hid.h"
#include "esphome/core/log.h"
#include "esphome/core/util.h"
#include "esphome/core/hal.h"
#include <algorithm>
#include <sstream>
#include <iomanip>
#include <cstring>

#ifdef USE_ESP32
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <fcntl.h>
#include <errno.h>
#endif

namespace esphome {
namespace nut_server {

NutServerComponent::NutServerComponent() {
  clients_.reserve(DEFAULT_MAX_CLIENTS);
}

NutServerComponent::~NutServerComponent() {
  stop_server();
}

void NutServerComponent::setup() {
  ESP_LOGCONFIG(TAG, "Setting up NUT Server...");
  
  if (!ups_hid_) {
    ESP_LOGE(TAG, "No UPS HID component configured!");
    mark_failed();
    return;
  }
  
  // Initialize clients
  clients_.resize(max_clients_);
  for (auto &client : clients_) {
    client.reset();
  }
  
  if (!start_server()) {
    ESP_LOGE(TAG, "Failed to start NUT server!");
    mark_failed();
    return;
  }
  
  ESP_LOGCONFIG(TAG, "NUT Server started on port %d", port_);
}

void NutServerComponent::loop() {
  // Main loop handles client cleanup
  cleanup_inactive_clients();
}

void NutServerComponent::dump_config() {
  ESP_LOGCONFIG(TAG, "NUT Server:");
  ESP_LOGCONFIG(TAG, "  Port: %d", port_);
  ESP_LOGCONFIG(TAG, "  Max Clients: %d", max_clients_);
  ESP_LOGCONFIG(TAG, "  UPS Name: %s", get_ups_name().c_str());
  ESP_LOGCONFIG(TAG, "  Username: %s", username_.c_str());
  ESP_LOGCONFIG(TAG, "  Authentication: %s", password_.empty() ? "Disabled" : "Enabled");
  
  if (ups_hid_) {
    ESP_LOGCONFIG(TAG, "  UPS HID Component: Connected");
  } else {
    ESP_LOGCONFIG(TAG, "  UPS HID Component: Not configured!");
  }
}

bool NutServerComponent::start_server() {
#ifdef USE_ESP32
  // Create server socket
  server_socket_ = ::socket(AF_INET, SOCK_STREAM, 0);
  if (server_socket_ < 0) {
    ESP_LOGE(TAG, "Failed to create socket: %d", errno);
    return false;
  }
  
  // Set socket options
  int yes = 1;
  if (::setsockopt(server_socket_, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) < 0) {
    ESP_LOGW(TAG, "Failed to set SO_REUSEADDR: %d", errno);
  }
  
  // Set non-blocking mode
  int flags = fcntl(server_socket_, F_GETFL, 0);
  if (fcntl(server_socket_, F_SETFL, flags | O_NONBLOCK) < 0) {
    ESP_LOGW(TAG, "Failed to set non-blocking mode: %d", errno);
  }
  
  // Bind to port
  struct sockaddr_in server_addr;
  memset(&server_addr, 0, sizeof(server_addr));
  server_addr.sin_family = AF_INET;
  server_addr.sin_addr.s_addr = INADDR_ANY;
  server_addr.sin_port = htons(port_);
  
  if (::bind(server_socket_, (struct sockaddr *)&server_addr, sizeof(server_addr)) < 0) {
    ESP_LOGE(TAG, "Failed to bind to port %d: %d", port_, errno);
    ::close(server_socket_);
    server_socket_ = -1;
    return false;
  }
  
  // Start listening
  if (::listen(server_socket_, max_clients_) < 0) {
    ESP_LOGE(TAG, "Failed to listen on socket: %d", errno);
    ::close(server_socket_);
    server_socket_ = -1;
    return false;
  }
  
  // Create server task
  server_running_ = true;
  xTaskCreate(server_task, "nut_server", 4096, this, 1, &server_task_handle_);
  
  return true;
#else
  ESP_LOGE(TAG, "NUT Server requires ESP32 platform");
  return false;
#endif
}

void NutServerComponent::stop_server() {
#ifdef USE_ESP32
  shutdown_requested_ = true;
  server_running_ = false;
  
  // Close all client connections
  {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    for (auto &client : clients_) {
      if (client.is_active()) {
        disconnect_client(client);
      }
    }
  }
  
  // Close server socket
  if (server_socket_ >= 0) {
    ::close(server_socket_);
    server_socket_ = -1;
  }
  
  // Wait for server task to finish
  if (server_task_handle_) {
    vTaskDelete(server_task_handle_);
    server_task_handle_ = nullptr;
  }
#endif
}

void NutServerComponent::server_task(void *param) {
#ifdef USE_ESP32
  NutServerComponent *server = static_cast<NutServerComponent *>(param);
  
  while (server->server_running_) {
    server->accept_clients();
    
    // Handle all connected clients
    {
      std::lock_guard<std::mutex> lock(server->clients_mutex_);
      for (auto &client : server->clients_) {
        if (client.is_active()) {
          server->handle_client(client);
        }
      }
    }
    
    vTaskDelay(10 / portTICK_PERIOD_MS);
  }
  
  vTaskDelete(nullptr);
#endif
}

void NutServerComponent::accept_clients() {
#ifdef USE_ESP32
  struct sockaddr_in client_addr;
  socklen_t client_len = sizeof(client_addr);
  
  int client_socket = ::accept(server_socket_, (struct sockaddr *)&client_addr, &client_len);
  if (client_socket < 0) {
    if (errno != EWOULDBLOCK && errno != EAGAIN) {
      ESP_LOGW(TAG, "Accept failed: %d", errno);
    }
    return;
  }
  
  // Set client socket to non-blocking
  int flags = fcntl(client_socket, F_GETFL, 0);
  fcntl(client_socket, F_SETFL, flags | O_NONBLOCK);
  
  // Find available client slot
  std::lock_guard<std::mutex> lock(clients_mutex_);
  for (auto &client : clients_) {
    if (!client.is_active()) {
      client.socket_fd = client_socket;
      client.state = ClientState::CONNECTED;
      uint32_t now = millis();
      client.last_activity = now;
      client.connect_time = now;
      client.login_attempts = 0;
      client.remote_ip = std::string(inet_ntoa(client_addr.sin_addr));
      
      ESP_LOGD(TAG, "Client connected from %s", client.remote_ip.c_str());
      
      // NUT protocol: No initial greeting - wait for client commands
      return;
    }
  }
  
  // No available slots
  ESP_LOGW(TAG, "Maximum clients reached, rejecting connection");
  const char *msg = "ERR MAX-CLIENTS Maximum number of clients reached\n";
  ::send(client_socket, msg, strlen(msg), 0);
  ::close(client_socket);
#endif
}

void NutServerComponent::handle_client(NutClient &client) {
#ifdef USE_ESP32
  char buffer[MAX_COMMAND_LENGTH];
  int bytes_received = ::recv(client.socket_fd, buffer, sizeof(buffer) - 1, 0);
  
  if (bytes_received > 0) {
    buffer[bytes_received] = '\0';
    
    // Remove trailing newline
    char *newline = strchr(buffer, '\n');
    if (newline) *newline = '\0';
    newline = strchr(buffer, '\r');
    if (newline) *newline = '\0';
    
    client.last_activity = millis();
    
    ESP_LOGV(TAG, "Received command: %s", buffer);
    process_command(client, std::string(buffer));
    
  } else if (bytes_received == 0) {
    // Client disconnected
    ESP_LOGD(TAG, "Client disconnected");
    disconnect_client(client);
  } else {
    if (errno != EWOULDBLOCK && errno != EAGAIN) {
      if (errno == ECONNRESET || errno == EPIPE) {
        // Client abruptly disconnected - this is normal, log at debug level
        ESP_LOGD(TAG, "Client connection reset (error %d)", errno);
      } else {
        // Other errors are more concerning
        ESP_LOGW(TAG, "Receive error: %d", errno);
      }
      disconnect_client(client);
    }
  }
#endif
}

void NutServerComponent::disconnect_client(NutClient &client) {
#ifdef USE_ESP32
  if (client.socket_fd >= 0) {
    ::close(client.socket_fd);
  }
  client.reset();
#endif
}

void NutServerComponent::cleanup_inactive_clients() {
  std::lock_guard<std::mutex> lock(clients_mutex_);
  // Capture "now" *after* acquiring the lock, not before: nut_server runs
  // its own FreeRTOS task (server_task) that updates client.last_activity
  // independently of this function, which runs from the main ESPHome
  // loop(). If "now" were captured before waiting on the mutex, the other
  // thread can race ahead and set last_activity to something newer than
  // our stale "now" snapshot by the time we actually get the lock.
  uint32_t now = millis();

  for (auto &client : clients_) {
    if (!client.is_active()) {
      continue;
    }
    // Guard against last_activity being (very slightly) newer than "now"
    // - possible even with "now" captured after the lock, since millis()
    // isn't perfectly synchronized across FreeRTOS tasks/cores down to
    // the millisecond. Without this guard, unsigned subtraction wraps
    // around to ~4294967295 ms and every client gets disconnected
    // immediately on its very first activity update.
    if (now < client.last_activity) {
      continue;
    }
    uint32_t elapsed = now - client.last_activity;
    if (elapsed > CLIENT_TIMEOUT_MS) {
      ESP_LOGD(TAG, "Client %s timed out (now=%u, last_activity=%u, elapsed=%u ms, state=%d), disconnecting",
               client.remote_ip.c_str(), (unsigned) now, (unsigned) client.last_activity, (unsigned) elapsed,
               (int) client.state);
      disconnect_client(client);
    }
  }
}

void NutServerComponent::process_command(NutClient &client, const std::string &command) {
  if (command.empty()) {
    return;
  }
  
  // Parse command and arguments
  size_t space_pos = command.find(' ');
  std::string cmd = (space_pos != std::string::npos) ? 
                     command.substr(0, space_pos) : command;
  std::string args = (space_pos != std::string::npos) ? 
                      command.substr(space_pos + 1) : "";
  
  // Debug: Log all received commands
  ESP_LOGD(TAG, "Received command: '%s' args: '%s'", cmd.c_str(), args.c_str());
  
  // Convert command to uppercase for comparison
  std::transform(cmd.begin(), cmd.end(), cmd.begin(), ::toupper);
  
  // Commands that don't require authentication
  if (cmd == "HELP") {
    handle_help(client);
  } else if (cmd == "VER" || cmd == "VERSION") {
    handle_version(client);
  } else if (cmd == "NETVER") {
    handle_netver(client);
  } else if (cmd == "STARTTLS") {
    handle_starttls(client);
  } else if (cmd == "USERNAME") {
    handle_username(client, args);
  } else if (cmd == "PASSWORD") {
    handle_password(client, args);
  } else if (cmd == "LOGIN") {
    handle_login(client, args);
  } else if (cmd == "LOGOUT") {
    handle_logout(client);
  } else if (cmd == "UPSDVER") {
    handle_upsdver(client);
  }
  // Commands requiring authentication
  else if (!password_.empty() && !client.is_authenticated()) {
    send_error(client, "ACCESS-DENIED");
  } else {
    // Authenticated commands
    if (cmd == "LIST") {
      // Parse LIST subcommand
      size_t sub_pos = args.find(' ');
      std::string subcmd = (sub_pos != std::string::npos) ? 
                           args.substr(0, sub_pos) : args;
      std::string subargs = (sub_pos != std::string::npos) ? 
                            args.substr(sub_pos + 1) : "";
      
      std::transform(subcmd.begin(), subcmd.end(), subcmd.begin(), ::toupper);
      
      if (subcmd == "UPS") {
        handle_list_ups(client);
      } else if (subcmd == "VAR") {
        handle_list_var(client, subargs);
      } else if (subcmd == "CMD") {
        handle_list_cmd(client, subargs);
      } else if (subcmd == "CLIENTS") {
        handle_list_clients(client);
      } else if (subcmd == "RW") {
        handle_list_rwvar(client, subargs);
      } else if (subcmd == "ENUM") {
        handle_list_enum(client, subargs);
      } else if (subcmd == "RANGE") {
        handle_list_range(client, subargs);
      } else {
        send_error(client, "INVALID-ARGUMENT");
      }
    } else if (cmd == "GET") {
      // Parse GET subcommand
      size_t sub_pos = args.find(' ');
      std::string subcmd = (sub_pos != std::string::npos) ? 
                           args.substr(0, sub_pos) : args;
      std::string subargs = (sub_pos != std::string::npos) ? 
                            args.substr(sub_pos + 1) : "";
      
      std::transform(subcmd.begin(), subcmd.end(), subcmd.begin(), ::toupper);
      
      if (subcmd == "VAR") {
        handle_get_var(client, subargs);
      } else {
        send_error(client, "INVALID-ARGUMENT");
      }
    } else if (cmd == "SET") {
      // Parse SET subcommand
      size_t sub_pos = args.find(' ');
      std::string subcmd = (sub_pos != std::string::npos) ? 
                           args.substr(0, sub_pos) : args;
      std::string subargs = (sub_pos != std::string::npos) ? 
                            args.substr(sub_pos + 1) : "";
      
      std::transform(subcmd.begin(), subcmd.end(), subcmd.begin(), ::toupper);
      
      if (subcmd == "VAR") {
        handle_set_var(client, subargs);
      } else {
        send_error(client, "INVALID-ARGUMENT");
      }
    } else if (cmd == "INSTCMD") {
      handle_instcmd(client, args);
    } else if (cmd == "FSD") {
      handle_fsd(client, args);
    } else if (cmd == get_ups_name()) {
      // Legacy upsc -l format: sends UPS name directly as command
      // This is for old-style variable name support
      handle_legacy_list_vars(client, cmd);
    } else {
      ESP_LOGW(TAG, "Unknown command received: '%s' with args: '%s'", cmd.c_str(), args.c_str());
      send_error(client, "UNKNOWN-COMMAND");
    }
  }
}

void NutServerComponent::handle_login(NutClient &client, const std::string &args) {
  auto parts = split_args(args);
  // client could already submitted login information through its correspondening commands
  if (client.state == ClientState::AUTHENTICATED)
  {
    client.login_attempts++;
    if (client.login_attempts >= MAX_LOGIN_ATTEMPTS)
    {
      ESP_LOGW(TAG, "Max login attempts exceeded, disconnecting client");
      disconnect_client(client);
      return;
    }
    send_response(client, "OK\n");
    ESP_LOGD(TAG, "Client already connected");
    return;
  }

  // client isn't authenticated and did not provide any credentials
  if (parts.size() != 2)
  {
    send_error(client, "INVALID-ARGUMENT");
    return;
  }

  if (authenticate(parts[0], parts[1])) {
    client.state = ClientState::AUTHENTICATED;
    client.username = parts[0];
    send_response(client, "OK\n");
    ESP_LOGD(TAG, "Client authenticated as %s", parts[0].c_str());
  } else {
    client.login_attempts++;
    if (client.login_attempts >= MAX_LOGIN_ATTEMPTS) {
      ESP_LOGW(TAG, "Max login attempts exceeded, disconnecting client");
      disconnect_client(client);
    } else {
      send_error(client, "ACCESS-DENIED");
    }
  }
}

void NutServerComponent::handle_logout(NutClient &client) {
  send_response(client, "OK Goodbye\n");
  // Close the connection after sending the goodbye message
  disconnect_client(client);
}

void NutServerComponent::handle_list_ups(NutClient &client) {
  std::string ups_name = get_ups_name();
  std::string ups_description = get_ups_description();
  
  std::string response = "BEGIN LIST UPS\n";
  response += "UPS " + ups_name + " \"" + ups_description + "\"\n";
  response += "END LIST UPS\n";
  send_response(client, response);
}

void NutServerComponent::handle_list_var(NutClient &client, const std::string &args) {
  if (args != get_ups_name()) {
    send_error(client, "UNKNOWN-UPS");
    return;
  }
  
  if (!has_ups_data()) {
    send_error(client, "DATA-STALE");
    return;
  }
  
  std::string ups_name = get_ups_name();
  std::string response = "BEGIN LIST VAR " + ups_name + "\n";
  
  // Standard NUT variables mapping to actual UPS data
  std::vector<std::string> variables = {
    "ups.mfr", "ups.model", "ups.status", "ups.serial", "ups.firmware",
    "battery.charge", "battery.voltage", "battery.voltage.nominal", "battery.runtime",
    "input.voltage", "input.voltage.nominal", "input.frequency", 
    "input.transfer.low", "input.transfer.high",
    "output.voltage", "output.voltage.nominal", 
    "ups.load", "ups.realpower.nominal", "ups.power.nominal"
  };
  
  for (const auto &var : variables) {
    std::string value = get_ups_var(var);
    if (!value.empty()) {
      response += "VAR " + ups_name + " " + var + " \"" + value + "\"\n";
    }
  }
  
  response += "END LIST VAR " + ups_name + "\n";
  send_response(client, response);
}

void NutServerComponent::handle_get_var(NutClient &client, const std::string &args) {
  auto parts = split_args(args);
  if (parts.size() != 2) {
    send_error(client, "INVALID-ARGUMENT");
    return;
  }
  
  if (parts[0] != get_ups_name()) {
    send_error(client, "UNKNOWN-UPS");
    return;
  }
  
  std::string value = get_ups_var(parts[1]);
  if (!value.empty()) {
    std::string response = "VAR " + get_ups_name() + " " + parts[1] + " \"" + value + "\"\n";
    send_response(client, response);
  } else {
    send_error(client, "VAR-NOT-SUPPORTED");
  }
}

void NutServerComponent::handle_list_cmd(NutClient &client, const std::string &args) {
  if (args != get_ups_name()) {
    send_error(client, "UNKNOWN-UPS");
    return;
  }
  
  std::string response = "BEGIN LIST CMD " + get_ups_name() + "\n";
  
  auto commands = get_available_commands();
  for (const auto &cmd : commands) {
    response += "CMD " + get_ups_name() + " " + cmd + "\n";
  }
  
  response += "END LIST CMD " + get_ups_name() + "\n";
  send_response(client, response);
}

void NutServerComponent::handle_list_clients(NutClient &client) {
  std::string response = "BEGIN LIST CLIENT\n";
  
  uint32_t now = millis();
  // Note: clients_mutex_ is already held by the calling context (server loop)
  
  for (size_t i = 0; i < clients_.size(); ++i) {
    const auto &c = clients_[i];
    if (c.is_active()) {
      // Format: CLIENT <ip> <connected_time> <status>
      std::string status = c.is_authenticated() ? "authenticated" : "connected";
      uint32_t connected_time = (now >= c.connect_time) ? (now - c.connect_time) / 1000 : 0;  // seconds
      
      response += "CLIENT " + c.remote_ip + " " + std::to_string(connected_time) + " " + status + "\n";
    }
  }
  
  response += "END LIST CLIENT\n";
  send_response(client, response);
}

void NutServerComponent::handle_instcmd(NutClient &client, const std::string &args) {
  ESP_LOGD(TAG, "INSTCMD received with args: '%s'", args.c_str());
  
  auto parts = split_args(args);
  ESP_LOGD(TAG, "INSTCMD parsed into %zu parts", parts.size());
  for (size_t i = 0; i < parts.size(); ++i) {
    ESP_LOGD(TAG, "  Part %zu: '%s'", i, parts[i].c_str());
  }
  
  if (parts.size() != 2) {
    ESP_LOGW(TAG, "INSTCMD invalid argument count: %zu (expected 2)", parts.size());
    send_error(client, "INVALID-ARGUMENT");
    return;
  }
  
  ESP_LOGD(TAG, "UPS name comparison: received='%s', expected='%s'", parts[0].c_str(), get_ups_name().c_str());
  if (parts[0] != get_ups_name()) {
    ESP_LOGW(TAG, "INSTCMD unknown UPS: '%s'", parts[0].c_str());
    send_error(client, "UNKNOWN-UPS");
    return;
  }
  
  ESP_LOGD(TAG, "Executing command: '%s'", parts[1].c_str());
  bool cmd_result = execute_command(parts[1]);
  ESP_LOGD(TAG, "Command execution result: %s", cmd_result ? "SUCCESS" : "FAILED");
  
  if (cmd_result) {
    send_response(client, "OK\n");
  } else {
    ESP_LOGW(TAG, "Command failed or not supported: %s", parts[1].c_str());
    send_error(client, "CMD-NOT-SUPPORTED");
  }
}

void NutServerComponent::handle_version(NutClient &client) {
  std::string response = "VERSION \"" + std::string(NUT_VERSION) + "\"\n";
  send_response(client, response);
}

void NutServerComponent::handle_netver(NutClient &client) {
  // NETVER returns the network protocol version only, no prefix
  // NUT network protocol version 1.3 is current standard
  send_response(client, "1.3\n");
}

void NutServerComponent::handle_help(NutClient &client) {
  std::string response = "Commands: HELP VERSION NETVER STARTTLS USERNAME PASSWORD LOGIN LOGOUT LIST GET SET INSTCMD FSD UPSDVER\n";
  send_response(client, response);
}

void NutServerComponent::handle_upsdver(NutClient &client) {
  std::string response = std::string(UPSD_VERSION) + "\n";
  send_response(client, response);
}

void NutServerComponent::handle_starttls(NutClient &client) {
  // STARTTLS is not supported (we don't have TLS/SSL)
  send_error(client, "FEATURE-NOT-SUPPORTED");
}

void NutServerComponent::handle_username(NutClient &client, const std::string &args) {
  if (args.empty()) {
    send_error(client, "INVALID-ARGUMENT");
    return;
  }
  
  client.temp_username = args;
  ESP_LOGD(TAG, "Received username: %s", args.c_str());
  send_response(client, "OK\n");
}

void NutServerComponent::handle_password(NutClient &client, const std::string &args) {
  if (args.empty()) {
    send_error(client, "INVALID-ARGUMENT");
    return;
  }
  
  client.temp_password = args;
  ESP_LOGD(TAG, "Received password (authentication attempt)");
  
  // Attempt authentication with stored credentials
  if (authenticate(client.temp_username, client.temp_password)) {
    client.state = ClientState::AUTHENTICATED;
    client.username = client.temp_username;
    client.login_attempts = 0;
    ESP_LOGI(TAG, "Client authenticated successfully: %s", client.username.c_str());
    send_response(client, "OK\n");
  } else {
    client.login_attempts++;
    if (client.login_attempts >= MAX_LOGIN_ATTEMPTS) {
      ESP_LOGW(TAG, "Max login attempts exceeded, disconnecting client");
      disconnect_client(client);
    } else {
      send_error(client, "ACCESS-DENIED");
    }
  }
  
  // Clear temporary credentials
  client.temp_username.clear();
  client.temp_password.clear();
}

void NutServerComponent::handle_fsd(NutClient &client, const std::string &args) {
  // FSD (Forced Shutdown) - this is a critical command
  // For now, just acknowledge but don't actually shutdown
  ESP_LOGW(TAG, "FSD (Forced Shutdown) command received from client");
  send_response(client, "OK FSD-SET\n");
}

void NutServerComponent::handle_set_var(NutClient &client, const std::string &args) {
  // SET VAR is not supported in this implementation
  send_error(client, "CMD-NOT-SUPPORTED");
}

void NutServerComponent::handle_list_rwvar(NutClient &client, const std::string &args) {
  // No read-write variables supported
  if (args != get_ups_name()) {
    send_error(client, "UNKNOWN-UPS");
    return;
  }
  
  std::string response = "BEGIN LIST RW " + get_ups_name() + "\n";
  response += "END LIST RW " + get_ups_name() + "\n";
  send_response(client, response);
}

void NutServerComponent::handle_list_enum(NutClient &client, const std::string &args) {
  // No enum variables supported
  auto parts = split_args(args);
  if (parts.size() != 2 || parts[0] != get_ups_name()) {
    send_error(client, "INVALID-ARGUMENT");
    return;
  }
  
  std::string response = "BEGIN LIST ENUM " + get_ups_name() + " " + parts[1] + "\n";
  response += "END LIST ENUM " + get_ups_name() + " " + parts[1] + "\n";
  send_response(client, response);
}

void NutServerComponent::handle_list_range(NutClient &client, const std::string &args) {
  // No range variables supported
  auto parts = split_args(args);
  if (parts.size() != 2 || parts[0] != get_ups_name()) {
    send_error(client, "INVALID-ARGUMENT");
    return;
  }
  
  std::string response = "BEGIN LIST RANGE " + get_ups_name() + " " + parts[1] + "\n";
  response += "END LIST RANGE " + get_ups_name() + " " + parts[1] + "\n";
  send_response(client, response);
}

void NutServerComponent::handle_legacy_list_vars(NutClient &client, const std::string &ups_name) {
  // Legacy format for upsc -l: return simple variable names without quotes
  if (!has_ups_data()) {
    send_error(client, "DATA-STALE");
    return;
  }
  
  std::string response = "";
  
  // Simple list format for legacy upsc -l support
  response += "ups.mfr\n";
  response += "ups.model\n";
  response += "battery.charge\n";
  response += "input.voltage\n";
  response += "output.voltage\n";
  response += "ups.load\n";
  response += "battery.runtime\n";
  response += "ups.status\n";
  
  send_response(client, response);
}

bool NutServerComponent::send_response(NutClient &client, const std::string &response) {
#ifdef USE_ESP32
  int bytes_sent = ::send(client.socket_fd, response.c_str(), response.length(), 0);
  if (bytes_sent < 0) {
    if (errno == ECONNRESET || errno == EPIPE || errno == ENOTCONN) {
      ESP_LOGD(TAG, "Client connection reset (error %d)", errno);
    } else {
      ESP_LOGW(TAG, "Send error: %d", errno);
    }
    return false;
  }
  return bytes_sent == (int)response.length();
#else
  return false;
#endif
}

bool NutServerComponent::send_error(NutClient &client, const std::string &error) {
  std::string response = "ERR " + error + "\n";
  return send_response(client, response);
}

bool NutServerComponent::authenticate(const std::string &username, const std::string &password) {
  if (password_.empty()) {
    // No authentication required
    return true;
  }
  return (username == username_ && password == password_);
}

std::string NutServerComponent::get_ups_var(const std::string &var_name) {
  if (!has_ups_data()) {
    return "";
  }
  
  // Map variable names to data using data provider pattern
  if (var_name == "ups.mfr") return get_ups_manufacturer();
  if (var_name == "ups.model") return get_ups_model();
  
  if (ups_hid_) {
    auto ups_data = ups_hid_->get_ups_data();
    
    // Device information variables
    if (var_name == "ups.serial" && !ups_data.device.serial_number.empty()) {
      return ups_data.device.serial_number;
    }
    if (var_name == "ups.firmware" && !ups_data.device.firmware_version.empty()) {
      return ups_data.device.firmware_version;
    }
    
    // Battery variables
    if (var_name == "battery.charge") {
      float battery_level = ups_hid_->get_battery_level();
      if (battery_level >= 0) return std::to_string(static_cast<int>(battery_level));
    }
    if (var_name == "battery.voltage" && !std::isnan(ups_data.battery.voltage)) {
      return format_nut_value(std::to_string(ups_data.battery.voltage));
    }
    if (var_name == "battery.voltage.nominal" && !std::isnan(ups_data.battery.voltage_nominal)) {
      return format_nut_value(std::to_string(ups_data.battery.voltage_nominal));
    }
    if (var_name == "battery.runtime") {
      float runtime_minutes = ups_hid_->get_runtime_minutes();
      if (runtime_minutes > 0) return std::to_string(static_cast<int>(runtime_minutes * 60));
    }
    
    // Input power variables
    if (var_name == "input.voltage") {
      float input_voltage = ups_hid_->get_input_voltage();
      if (input_voltage > 0) return format_nut_value(std::to_string(input_voltage));
    }
    if (var_name == "input.voltage.nominal" && !std::isnan(ups_data.power.input_voltage_nominal)) {
      return format_nut_value(std::to_string(ups_data.power.input_voltage_nominal));
    }
    if (var_name == "input.frequency" && !std::isnan(ups_data.power.frequency)) {
      return format_nut_value(std::to_string(ups_data.power.frequency));
    }
    if (var_name == "input.transfer.low" && !std::isnan(ups_data.power.input_transfer_low)) {
      return format_nut_value(std::to_string(ups_data.power.input_transfer_low));
    }
    if (var_name == "input.transfer.high" && !std::isnan(ups_data.power.input_transfer_high)) {
      return format_nut_value(std::to_string(ups_data.power.input_transfer_high));
    }
    
    // Output power variables
    if (var_name == "output.voltage") {
      float output_voltage = ups_hid_->get_output_voltage();
      if (output_voltage > 0) return format_nut_value(std::to_string(output_voltage));
    }
    if (var_name == "output.voltage.nominal" && !std::isnan(ups_data.power.output_voltage_nominal)) {
      return format_nut_value(std::to_string(ups_data.power.output_voltage_nominal));
    }
    
    // Load and power variables
    if (var_name == "ups.load") {
      float load_percent = ups_hid_->get_load_percent();
      if (load_percent >= 0) return std::to_string(static_cast<int>(load_percent));
    }
    if (var_name == "ups.realpower.nominal" && !std::isnan(ups_data.power.realpower_nominal)) {
      return std::to_string(static_cast<int>(ups_data.power.realpower_nominal));
    }
    if (var_name == "ups.power.nominal" && !std::isnan(ups_data.power.apparent_power_nominal)) {
      return std::to_string(static_cast<int>(ups_data.power.apparent_power_nominal));
    }
  }
  
  if (var_name == "ups.status") {
    return get_ups_status();
  }
  
  return "";
}

std::string NutServerComponent::get_ups_name() {
  // Return a consistent UPS name
  // This will be set during component configuration
  return ups_name_.empty() ? "ups" : ups_name_;
}

std::string NutServerComponent::get_ups_description() {
  if (!has_ups_data()) {
    return "ESPHome UPS";
  }
  
  std::string manufacturer = get_ups_manufacturer();
  std::string model = get_ups_model();
  
  std::string desc = manufacturer;
  if (!desc.empty() && !model.empty()) {
    desc += " " + model;
  } else if (desc.empty()) {
    desc = "ESPHome UPS";
  }
  return desc;
}

std::vector<std::string> NutServerComponent::get_available_commands() {
  std::vector<std::string> commands;
  
  if (ups_hid_ && ups_hid_->is_connected()) {
    // Standard UPS HID commands that are always available
    commands.push_back("beeper.enable");
    commands.push_back("beeper.disable"); 
    commands.push_back("beeper.mute");
    commands.push_back("beeper.test");
    commands.push_back("test.battery.start.quick");
    commands.push_back("test.battery.start.deep");
    commands.push_back("test.battery.stop");
    // Standard NUT command names for panel/UPS tests
    commands.push_back("test.panel.start");
    commands.push_back("test.panel.stop");
    // Keep legacy names for compatibility
    commands.push_back("test.ups.start");
    commands.push_back("test.ups.stop");
  }
  
  return commands;
}

bool NutServerComponent::execute_command(const std::string &command) {
  if (!ups_hid_) {
    return false;
  }
  
  // Map NUT commands to specific UPS HID methods
  if (command == "beeper.enable") {
    return ups_hid_->beeper_enable();
  } else if (command == "beeper.disable") {
    return ups_hid_->beeper_disable();
  } else if (command == "beeper.mute") {
    return ups_hid_->beeper_mute();
  } else if (command == "beeper.test") {
    return ups_hid_->beeper_test();
  } else if (command == "test.battery.start.quick") {
    return ups_hid_->start_battery_test_quick();
  } else if (command == "test.battery.start.deep") {
    return ups_hid_->start_battery_test_deep();
  } else if (command == "test.battery.stop") {
    return ups_hid_->stop_battery_test();
  } else if (command == "test.panel.start" || command == "test.ups.start") {
    return ups_hid_->start_ups_test();
  } else if (command == "test.panel.stop" || command == "test.ups.stop") {
    return ups_hid_->stop_ups_test();
  }
  
  return false;
}

std::string NutServerComponent::format_nut_value(const std::string &value) {
  // Format floating point values to 1 decimal place
  // Simple approach without exceptions
  char* endptr;
  float f = std::strtof(value.c_str(), &endptr);
  if (endptr != value.c_str() && *endptr == '\0') {
    // Valid float conversion
    std::ostringstream oss;
    oss << std::fixed << std::setprecision(1) << f;
    return oss.str();
  }
  return value;
}

std::vector<std::string> NutServerComponent::split_args(const std::string &args) {
  std::vector<std::string> result;
  std::istringstream iss(args);
  std::string token;
  
  while (iss >> token) {
    // Handle quoted strings
    if (token.front() == '"') {
      std::string quoted = token.substr(1);
      if (quoted.back() != '"') {
        std::string rest;
        std::getline(iss, rest, '"');
        quoted += rest;
      } else {
        quoted.pop_back();
      }
      result.push_back(quoted);
    } else {
      result.push_back(token);
    }
  }
  
  return result;
}

bool NutServerComponent::has_ups_data() const {
  return ups_hid_ && ups_hid_->is_connected();
}

std::string NutServerComponent::get_ups_status() const {
  if (!ups_hid_ || !ups_hid_->is_connected()) {
    return "";
  }
  // Shared with the "nut_status" ESPHome text sensor - see
  // UpsHidComponent::get_nut_status() for the actual OL/OB/LB/CHRG/
  // DISCHRG/ALARM logic, kept in one place so both stay in sync.
  return ups_hid_->get_nut_status();
}

std::string NutServerComponent::get_ups_manufacturer() const {
  if (ups_hid_) {
    auto ups_data = ups_hid_->get_ups_data();
    if (!ups_data.device.manufacturer.empty()) {
      return ups_data.device.manufacturer;
    }
  }
  return "Unknown";
}

std::string NutServerComponent::get_ups_model() const {
  if (ups_hid_) {
    auto ups_data = ups_hid_->get_ups_data();
    if (!ups_data.device.model.empty()) {
      return ups_data.device.model;
    }
  }
  return "Unknown UPS";
}

}  // namespace nut_server
}  // namespace esphome