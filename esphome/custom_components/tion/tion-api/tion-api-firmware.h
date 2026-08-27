#pragma once

#include <cstdint>

namespace dentra {
namespace tion {
namespace firmware {

enum {
  // Шаг 1. Запрос на подготовку бризера к обновлению.
  // Пакет пустой.
  FRAME_TYPE_UPDATE_PREPARE_REQ = 0x400E,

  // Ответ на запрос о готовности принимать данные прошивки.
  // Содержимое пакета: структура firmware_versions_t.
  FRAME_TYPE_UPDATE_PREPARE_RSP = 0x4004,

  // Шаг 2. Запрос старта обновления.
  // Содержимое пакета: структура firmware_info_t.
  FRAME_TYPE_UPDATE_START_REQ = 0x4005,

  // Подтверждение готовности к приему прошивки.
  FRAME_TYPE_UPDATE_START_RSP = 0x400C,

  // Шаг 3. Отправка части прошивки.
  // Содержимое первого пакета: структура firmware_chunk_t.
  // Содержимое последнего пакета: структура firmware_chunk_crc_t.
  FRAME_TYPE_UPDATE_CHUNK_REQ = 0x4006,

  // Подтверждение приема части прошивки.
  // Пакет пустой.
  FRAME_TYPE_UPDATE_CHUNK_RSP = 0x400B,

  // Шаг N (финальный). Верификация прошивки.
  // Содержимое пакета: структура firmware_info_t.
  FRAME_TYPE_UPDATE_FINISH_REQ = 0x4007,

  // Прошивка успешно установилась.
  // Пакет пустой.
  FRAME_TYPE_UPDATE_FINISH_RSP = 0x400D,

  // Ошибка обновления прошивки.
  // Пакет пока неизвестен.
  FRAME_TYPE_UPDATE_ERROR = 0x4008,
};

// Используется при ответе FRAME_TYPE_UPDATE_PREPARE_RSP.
struct FirmwareVersions {
  uint32_t device_type;
  uint16_t unknown1;  // always 0
  uint16_t hardware_version;
};

// Используется при запросе FRAME_TYPE_UPDATE_START_REQ.
struct FirmwareInfo {
  // firmware_size + sizeof(this->data) + crc_size
  uint32_t size;
  // заполнено "мусором", приложение просто инкриминирует счетчик,
  // в тионе эти данные никак не обрабатываются
  uint8_t data[128];
};

// Используется при запросе FRAME_TYPE_UPDATE_CHUNK_REQ.
struct FirmwareChunk {
  enum { SIZE = 512 };  // в приложении 1000
  uint32_t offset;
  uint8_t data[SIZE];
};

// Используется при запросе FRAME_TYPE_UPDATE_CHUNK_REQ.
struct FirmwareChunkCRC {
  enum { MARKER = 0xFFFFFFFF };
  uint32_t marker{MARKER};
  uint16_t crc;
};

}  // namespace firmware
}  // namespace tion
}  // namespace dentra
