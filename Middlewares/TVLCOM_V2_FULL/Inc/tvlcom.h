#ifndef TVLCOM_H
#define TVLCOM_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#ifndef TVLCOM_MAX_PAYLOAD_SIZE
#define TVLCOM_MAX_PAYLOAD_SIZE 256U
#endif

#ifndef TVLCOM_MAX_FRAME_SIZE
#define TVLCOM_MAX_FRAME_SIZE (TVLCOM_MAX_PAYLOAD_SIZE + 8U)
#endif

#ifndef TVLCOM_MAX_HANDLERS
#define TVLCOM_MAX_HANDLERS 16U
#endif

#define TVLCOM_SOF0 0xAAU
#define TVLCOM_SOF1 0x55U

#define TVLCOM_CMD_ACK 0x00U
#define TVLCOM_CMD_NACK 0xFFU

typedef enum
{
    TVLCOM_OK = 0,
    TVLCOM_ERR_ARG = -1,
    TVLCOM_ERR_OVERFLOW = -2,
    TVLCOM_ERR_FORMAT = -3,
    TVLCOM_ERR_CRC = -4,
    TVLCOM_ERR_NOT_FOUND = -5,
    TVLCOM_ERR_TYPE = -6,
    TVLCOM_ERR_INCOMPLETE = -7
} tvlcom_status_t;

typedef enum
{
    TVLCOM_TYPE_U8 = 0x01,
    TVLCOM_TYPE_U16 = 0x02,
    TVLCOM_TYPE_U32 = 0x03,
    TVLCOM_TYPE_FLOAT = 0x10,
    TVLCOM_TYPE_STRING = 0x20
} tvlcom_type_t;

typedef struct
{
    uint8_t type;
    uint16_t length;
    const uint8_t *value;
} tvlcom_tlv_t;

typedef struct
{
    uint8_t cmd;
    uint8_t seq;
    uint16_t payload_len;
    uint8_t payload[TVLCOM_MAX_PAYLOAD_SIZE];
} tvlcom_frame_t;

typedef struct
{
    uint8_t buffer[TVLCOM_MAX_FRAME_SIZE];
    uint16_t length;
} tvlcom_parser_t;

typedef void (*tvlcom_handler_t)(uint8_t seq,
                                 const uint8_t *payload,
                                 uint16_t payload_len,
                                 void *user_ctx);

typedef void (*tvlcom_ack_handler_t)(uint8_t cmd,
                                     uint8_t seq,
                                     const uint8_t *payload,
                                     uint16_t payload_len,
                                     void *user_ctx);

typedef void (*tvlcom_nack_handler_t)(uint8_t cmd,
                                      uint8_t seq,
                                      const uint8_t *payload,
                                      uint16_t payload_len,
                                      void *user_ctx);

typedef struct
{
    uint8_t in_use;
    uint8_t cmd;
    tvlcom_handler_t handler;
    void *user_ctx;
} tvlcom_dispatch_entry_t;

typedef struct
{
    tvlcom_dispatch_entry_t entries[TVLCOM_MAX_HANDLERS];
    tvlcom_ack_handler_t ack_handler;
    void *ack_user_ctx;
    tvlcom_nack_handler_t nack_handler;
    void *nack_user_ctx;
} tvlcom_dispatcher_t;

uint16_t tvlcom_crc16(const uint8_t *data, uint16_t length);

void tvlcom_parser_init(tvlcom_parser_t *parser);

tvlcom_status_t tvlcom_frame_build(uint8_t cmd,
                                   uint8_t seq,
                                   const uint8_t *payload,
                                   uint16_t payload_len,
                                   uint8_t *out_frame,
                                   uint16_t out_capacity,
                                   uint16_t *out_frame_len);

tvlcom_status_t tvlcom_parser_input(tvlcom_parser_t *parser,
                                    const uint8_t *data,
                                    uint16_t data_len,
                                    tvlcom_frame_t *out_frames,
                                    uint8_t max_frames,
                                    uint8_t *out_count);

tvlcom_status_t tvlcom_payload_append_raw(uint8_t *payload,
                                          uint16_t capacity,
                                          uint16_t *io_length,
                                          uint8_t type,
                                          const uint8_t *value,
                                          uint16_t value_len);

tvlcom_status_t tvlcom_payload_add_u8(uint8_t *payload,
                                      uint16_t capacity,
                                      uint16_t *io_length,
                                      uint8_t type,
                                      uint8_t value);

tvlcom_status_t tvlcom_payload_add_u16(uint8_t *payload,
                                       uint16_t capacity,
                                       uint16_t *io_length,
                                       uint8_t type,
                                       uint16_t value);

tvlcom_status_t tvlcom_payload_add_u32(uint8_t *payload,
                                       uint16_t capacity,
                                       uint16_t *io_length,
                                       uint8_t type,
                                       uint32_t value);

tvlcom_status_t tvlcom_payload_add_float(uint8_t *payload,
                                         uint16_t capacity,
                                         uint16_t *io_length,
                                         uint8_t type,
                                         float value);

tvlcom_status_t tvlcom_payload_add_string(uint8_t *payload,
                                          uint16_t capacity,
                                          uint16_t *io_length,
                                          uint8_t type,
                                          const char *value);

tvlcom_status_t tvlcom_payload_next(const uint8_t *payload,
                                    uint16_t payload_len,
                                    uint16_t *io_offset,
                                    tvlcom_tlv_t *out_tlv);

tvlcom_status_t tvlcom_payload_get_u8(const uint8_t *payload,
                                      uint16_t payload_len,
                                      uint8_t type,
                                      uint8_t *out_value);

tvlcom_status_t tvlcom_payload_get_u16(const uint8_t *payload,
                                       uint16_t payload_len,
                                       uint8_t type,
                                       uint16_t *out_value);

tvlcom_status_t tvlcom_payload_get_u32(const uint8_t *payload,
                                       uint16_t payload_len,
                                       uint8_t type,
                                       uint32_t *out_value);

tvlcom_status_t tvlcom_payload_get_float(const uint8_t *payload,
                                         uint16_t payload_len,
                                         uint8_t type,
                                         float *out_value);

tvlcom_status_t tvlcom_payload_get_string(const uint8_t *payload,
                                          uint16_t payload_len,
                                          uint8_t type,
                                          char *out_value,
                                          uint16_t out_capacity,
                                          uint16_t *out_length);

tvlcom_status_t tvlcom_payload_get_raw(const uint8_t *payload,
                                       uint16_t payload_len,
                                       uint8_t type,
                                       const uint8_t **out_value,
                                       uint16_t *out_length);

void tvlcom_dispatcher_init(tvlcom_dispatcher_t *dispatcher);

void tvlcom_dispatcher_set_ack_handler(tvlcom_dispatcher_t *dispatcher,
                                       tvlcom_ack_handler_t ack_handler,
                                       void *user_ctx);

void tvlcom_dispatcher_set_nack_handler(tvlcom_dispatcher_t *dispatcher,
                                        tvlcom_nack_handler_t nack_handler,
                                        void *user_ctx);

tvlcom_status_t tvlcom_dispatcher_register(tvlcom_dispatcher_t *dispatcher,
                                           uint8_t cmd,
                                           tvlcom_handler_t handler,
                                           void *user_ctx);

tvlcom_status_t tvlcom_dispatcher_dispatch(tvlcom_dispatcher_t *dispatcher,
                                           const tvlcom_frame_t *frame);

#ifdef __cplusplus
}
#endif

#endif

