#pragma once

#include "esphome/core/component.h"
#include "esphome/core/log.h"
#include <memory>
#include <vector>
#include <string>
#include <mutex>
#include <optional>

#ifdef USE_ESP32
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <netdb.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#endif

namespace esphome {

// Forward declarations
namespace ups_hid {
class UpsHidComponent;
}

namespace nut_server {

static const char *const TAG = "nut_server";

// NUT protocol constants
static constexpr uint16_t DEFAULT_NUT_PORT = 3493;
static constexpr size_t MAX_COMMAND_LENGTH = 256;
static constexpr size_t MAX_RESPONSE_LENGTH = 2048;
static constexpr uint8_t DEFAULT_MAX_CLIENTS = 4;
static constexpr uint8_t MAX_LOGIN_ATTEMPTS = 3;
static constexpr uint32_t CLIENT_TIMEOUT_MS = 60000;  // 60 seconds

// NUT protocol version
static constexpr const char* NUT_VERSION = "2.8.0";
static constexpr const char* UPSD_VERSION = "upsd 2.8.0 ESPHome";

// Client states
enum class ClientState {
  CONNECTED,
  AUTHENTICATED,
  DISCONNECTED
};

// NUT client connection
struct NutClient {
  int socket_fd{-1};
  ClientState state{ClientState::DISCONNECTED};
  uint8_t login_attempts{0};
  uint32_t last_activity{0};
  uint32_t connect_time{0};
  std::string username;
  std::string remote_ip;
  std::string temp_username;  // For USERNAME/PASSWORD flow
  std::string temp_password;  // For USERNAME/PASSWORD flow
  
  bool is_authenticated() const { return state == ClientState::AUTHENTICATED; }
  bool is_active() const { return socket_fd >= 0 && state != ClientState::DISCONNECTED; }
  void reset() {
    socket_fd = -1;
    state = ClientState::DISCONNECTED;
    login_attempts = 0;
    last_activity = 0;
    connect_time = 0;
    username.clear();
    remote_ip.clear();
    temp_username.clear();
    temp_password.clear();
  }
};

// NUT Server Component
class NutServerComponent : public Component {
public:
  NutServerComponent();
  ~NutServerComponent();

  // ESPHome component lifecycle
  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override { return setup_priority::AFTER_CONNECTION; }

  // Configuration setters
  void set_ups_hid(ups_hid::UpsHidComponent *ups_hid) { ups_hid_ = ups_hid; }
  void set_port(uint16_t port) { port_ = port; }
  void set_username(const std::string &username) { username_ = username; }
  void set_password(const std::string &password) { password_ = password; }
  void set_max_clients(uint8_t max_clients) { 
    max_clients_ = std::min(max_clients, static_cast<uint8_t>(10)); 
  }
  void set_ups_name(const std::string &ups_name) { ups_name_ = ups_name; }

protected:
  // TCP server management
  bool start_server();
  void stop_server();
  void accept_clients();
  void handle_client(NutClient &client);
  void disconnect_client(NutClient &client);
  void cleanup_inactive_clients();
  
  // NUT protocol handlers
  void process_command(NutClient &client, const std::string &command);
  void handle_login(NutClient &client, const std::string &args);
  void handle_list_ups(NutClient &client);
  void handle_list_var(NutClient &client, const std::string &args);
  void handle_get_var(NutClient &client, const std::string &args);
  void handle_list_cmd(NutClient &client, const std::string &args);
  void handle_list_clients(NutClient &client);
  void handle_instcmd(NutClient &client, const std::string &args);
  void handle_version(NutClient &client);
  void handle_netver(NutClient &client);
  void handle_help(NutClient &client);
  void handle_upsdver(NutClient &client);
  void handle_logout(NutClient &client);
  void handle_starttls(NutClient &client);
  void handle_username(NutClient &client, const std::string &args);
  void handle_password(NutClient &client, const std::string &args);
  void handle_fsd(NutClient &client, const std::string &args);
  void handle_set_var(NutClient &client, const std::string &args);
  void handle_list_rwvar(NutClient &client, const std::string &args);
  void handle_list_enum(NutClient &client, const std::string &args);
  void handle_list_range(NutClient &client, const std::string &args);
  void handle_legacy_list_vars(NutClient &client, const std::string &ups_name);
  
  // Helper methods
  bool send_response(NutClient &client, const std::string &response);
  bool send_error(NutClient &client, const std::string &error);
  bool authenticate(const std::string &username, const std::string &password);
  std::string get_ups_var(const std::string &var_name);
  std::string get_ups_description();
  std::string get_ups_name();  // Dynamic UPS name from component
  std::vector<std::string> get_available_commands();
  bool execute_command(const std::string &command);
  std::string format_nut_value(const std::string &value);
  std::vector<std::string> split_args(const std::string &args);
  
  // Data access using provider pattern (like status LED component)
  bool has_ups_data() const;
  std::string get_ups_status() const;
  std::string get_ups_manufacturer() const;
  std::string get_ups_model() const;

private:
  // Server task management
  static void server_task(void *param);
  TaskHandle_t server_task_handle_{nullptr};
  bool server_running_{false};
  
  // Network resources
  int server_socket_{-1};
  uint16_t port_{DEFAULT_NUT_PORT};
  
  // Client management
  std::vector<NutClient> clients_;
  uint8_t max_clients_{DEFAULT_MAX_CLIENTS};
  mutable std::mutex clients_mutex_;
  
  // Authentication
  std::string username_{"nutuser"};
  std::string password_{"nutpass"};
  
  // UPS configuration
  std::string ups_name_{"ups"};
  ups_hid::UpsHidComponent *ups_hid_{nullptr};
  
  // Server state
  mutable std::mutex server_mutex_;
  bool shutdown_requested_{false};
};

}  // namespace nut_server
}  // namespace esphome