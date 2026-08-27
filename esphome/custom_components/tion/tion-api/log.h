#pragma once

enum {
  TION_LOG_LEVEL_NONE = 0,
  TION_LOG_LEVEL_ERROR = 1,
  TION_LOG_LEVEL_WARN = 2,
  TION_LOG_LEVEL_INFO = 3,
  TION_LOG_LEVEL_CONFIG = 4,
  TION_LOG_LEVEL_DEBUG = 5,
  TION_LOG_LEVEL_VERBOSE = 6,
};

#ifdef TION_ESPHOME
#include "esphome/core/log.h"
#define TION_LOGV(tag, format, ...) \
  { \
    using namespace esphome; \
    ESP_LOGV(tag, format, ##__VA_ARGS__); \
  }
#define TION_LOGD(tag, format, ...) \
  { \
    using namespace esphome; \
    ESP_LOGD(tag, format, ##__VA_ARGS__); \
  }
#define TION_LOGC(tag, format, ...) \
  { \
    using namespace esphome; \
    ESP_LOGCONFIG(tag, format, ##__VA_ARGS__); \
  }
#define TION_LOGI(tag, format, ...) \
  { \
    using namespace esphome; \
    ESP_LOGI(tag, format, ##__VA_ARGS__); \
  }
#define TION_LOGW(tag, format, ...) \
  { \
    using namespace esphome; \
    ESP_LOGW(tag, format, ##__VA_ARGS__); \
  }
#define TION_LOGE(tag, format, ...) \
  { \
    using namespace esphome; \
    ESP_LOGE(tag, format, ##__VA_ARGS__); \
  }

#ifndef TION_LOG_LEVEL
#define TION_LOG_LEVEL ESPHOME_LOG_LEVEL
#endif

#else  // TION_ESPHOME

#include <functional>  // std::function
#include <cstdarg>     // va_list

#ifndef TION_LOG_LEVEL
#define TION_LOG_LEVEL TION_LOG_LEVEL_DEBUG
#endif

namespace dentra {
namespace tion {

using logger_fn_t = std::function<void(int, const char *, int, const char *, va_list)>;
void set_logger(const logger_fn_t &&logger);

void tion_log_printf_(int level, const char *tag, int line, const char *format, ...)  // NOLINT
    __attribute__((format(printf, 4, 5)));
#endif

#ifndef TION_LOGV
#if TION_LOG_LEVEL >= TION_LOG_LEVEL_VERBOSE
#define TION_LOGV(tag, format, ...) tion_log_printf_(TION_LOG_LEVEL_VERBOSE, tag, __LINE__, format, ##__VA_ARGS__)
#else
#define TION_LOGV(tag, format, ...)
#endif
#endif

#ifndef TION_LOGD
#if TION_LOG_LEVEL >= TION_LOG_LEVEL_DEBUG
#define TION_LOGD(tag, format, ...) tion_log_printf_(TION_LOG_LEVEL_DEBUG, tag, __LINE__, format, ##__VA_ARGS__)
#else
#define TION_LOGD(tag, format, ...)
#endif
#endif

#ifndef TION_LOGI
#if TION_LOG_LEVEL >= TION_LOG_LEVEL_INFO
#define TION_LOGI(tag, format, ...) tion_log_printf_(TION_LOG_LEVEL_INFO, tag, __LINE__, format, ##__VA_ARGS__)
#else
#define TION_LOGI(tag, format, ...)
#endif
#endif

#ifndef TION_LOGW
#if TION_LOG_LEVEL >= TION_LOG_LEVEL_WARN
#define TION_LOGW(tag, format, ...) tion_log_printf_(TION_LOG_LEVEL_WARN, tag, __LINE__, format, ##__VA_ARGS__)
#else
#define TION_LOGW(tag, format, ...)
#endif
#endif

#ifndef TION_LOGE
#if TION_LOG_LEVEL >= TION_LOG_LEVEL_ERROR
#define TION_LOGE(tag, format, ...) tion_log_printf_(TION_LOG_LEVEL_ERROR, tag, __LINE__, format, ##__VA_ARGS__)
#else
#define TION_LOGE(tag, format, ...)
#endif

}  // namespace tion
}  // namespace dentra

#endif  // TION_ESPHOME

#ifndef TION_DUMP
#define TION_DUMP TION_LOGV
#endif
