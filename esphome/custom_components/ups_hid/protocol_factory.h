#pragma once

#include <memory>
#include <functional>
#include <unordered_map>
#include <vector>
#include <string>

namespace esphome {
namespace ups_hid {

// Forward declarations
class UpsProtocolBase;
class UpsHidComponent;

/**
 * Protocol Factory with Self-Registration Support
 * 
 * Enables protocols to register themselves automatically, following the
 * Open/Closed Principle - new protocols can be added without modifying
 * existing code.
 * 
 * Design Pattern: Factory Method + Registry Pattern
 */
class ProtocolFactory {
public:
    // Protocol creator function type
    using CreatorFunc = std::function<std::unique_ptr<UpsProtocolBase>(UpsHidComponent*)>;
    
    // Protocol metadata for better selection
    struct ProtocolInfo {
        CreatorFunc creator;
        std::string name;
        std::string description;
        std::vector<uint16_t> supported_vendors;
        int priority; // Higher priority = tried first
    };
    
    /**
     * Register a protocol with specific vendor IDs
     */
    static void register_protocol_for_vendor(uint16_t vendor_id, 
                                           const ProtocolInfo& info);
    
    /**
     * Register a fallback protocol (tried when vendor-specific fails)
     */
    static void register_fallback_protocol(const ProtocolInfo& info);
    
    /**
     * Create protocol instance for specific vendor
     */
    static std::unique_ptr<UpsProtocolBase> create_for_vendor(uint16_t vendor_id, 
                                                            UpsHidComponent* parent);
    
    /**
     * Create protocol instance by name (manual selection)
     */
    static std::unique_ptr<UpsProtocolBase> create_by_name(const std::string& protocol_name,
                                                         UpsHidComponent* parent);
    
    /**
     * Get ordered list of protocols to try for a vendor
     * Returns vendor-specific first, then fallbacks by priority
     */
    static std::vector<ProtocolInfo> get_protocols_for_vendor(uint16_t vendor_id);
    
    /**
     * Get list of all registered protocols
     */
    static std::vector<std::pair<uint16_t, ProtocolInfo>> get_all_protocols();
    
    /**
     * Check if vendor has registered protocols
     */
    static bool has_vendor_support(uint16_t vendor_id);

private:
    // Vendor-specific protocol registry
    static std::unordered_map<uint16_t, std::vector<ProtocolInfo>>& get_vendor_registry();
    
    // Fallback protocol registry (sorted by priority)
    static std::vector<ProtocolInfo>& get_fallback_registry();
    
    // Ensure registries are initialized
    static void ensure_initialized();
};

/**
 * Protocol Registration Helper Macros
 * 
 * These macros enable automatic protocol registration at startup
 */

// Forward declare for registration macros
class ProtocolFactory;

// Register protocol for specific vendor
#define REGISTER_UPS_PROTOCOL_FOR_VENDOR(vendor_id, protocol_name, creator_func, name_str, desc_str, prio) \
    namespace { \
        struct protocol_name##_registrar { \
            protocol_name##_registrar() { \
                esphome::ups_hid::ProtocolFactory::ProtocolInfo info; \
                info.creator = creator_func; \
                info.name = name_str; \
                info.description = desc_str; \
                info.supported_vendors = {vendor_id}; \
                info.priority = prio; \
                esphome::ups_hid::ProtocolFactory::register_protocol_for_vendor(vendor_id, info); \
            } \
        }; \
        static protocol_name##_registrar protocol_name##_reg; \
    }

// Register fallback protocol
#define REGISTER_UPS_FALLBACK_PROTOCOL(protocol_name, creator_func, name_str, desc_str, prio) \
    namespace { \
        struct protocol_name##_fallback_registrar { \
            protocol_name##_fallback_registrar() { \
                esphome::ups_hid::ProtocolFactory::ProtocolInfo info; \
                info.creator = creator_func; \
                info.name = name_str; \
                info.description = desc_str; \
                info.supported_vendors = {}; \
                info.priority = prio; \
                esphome::ups_hid::ProtocolFactory::register_fallback_protocol(info); \
            } \
        }; \
        static protocol_name##_fallback_registrar protocol_name##_fallback_reg; \
    }

} // namespace ups_hid
} // namespace esphome