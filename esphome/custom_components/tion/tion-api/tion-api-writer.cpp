#include "log.h"
#include "utils.h"

#include "tion-api-writer.h"

namespace dentra {
namespace tion {

static const char *const TAG = "tion-api-writer";

bool TionApiWriter::write_frame(uint16_t type, const void *data, size_t size) const {
  TION_LOGV(TAG, "Write frame 0x%04X: %s", type, hex_cstr(data, size));
  if (!this->writer_) {
    TION_LOGE(TAG, "Writer is not configured");
    return false;
  }
  return this->writer_(type, data, size);
}

}  // namespace tion
}  // namespace dentra
