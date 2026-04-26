#include "tvlcom.h"

#include <string.h>

static uint16_t tvlcom_read_le16(const uint8_t *data)
{
    return (uint16_t)data[0] | ((uint16_t)data[1] << 8);
}

static uint32_t tvlcom_read_le32(const uint8_t *data)
{
    return (uint32_t)data[0] |
           ((uint32_t)data[1] << 8) |
           ((uint32_t)data[2] << 16) |
           ((uint32_t)data[3] << 24);
}

static void tvlcom_write_le16(uint8_t *data, uint16_t value)
{
    data[0] = (uint8_t)(value & 0xFFU);
    data[1] = (uint8_t)((value >> 8) & 0xFFU);
}

static void tvlcom_write_le32(uint8_t *data, uint32_t value)
{
    data[0] = (uint8_t)(value & 0xFFU);
    data[1] = (uint8_t)((value >> 8) & 0xFFU);
    data[2] = (uint8_t)((value >> 16) & 0xFFU);
    data[3] = (uint8_t)((value >> 24) & 0xFFU);
}

static void tvlcom_buffer_remove_prefix(uint8_t *buffer,
                                        uint16_t *length,
                                        uint16_t consumed)
{
    if ((buffer == NULL) || (length == NULL) || (consumed > *length))
    {
        return;
    }

    if (consumed < *length)
    {
        memmove(buffer, buffer + consumed, (size_t)(*length - consumed));
    }

    *length = (uint16_t)(*length - consumed);
}

static tvlcom_status_t tvlcom_payload_find_last(const uint8_t *payload,
                                                uint16_t payload_len,
                                                uint8_t type,
                                                tvlcom_tlv_t *out_tlv)
{
    uint16_t offset = 0U;
    tvlcom_tlv_t current;
    uint8_t found = 0U;

    if ((payload == NULL) || (out_tlv == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    while (offset < payload_len)
    {
        if ((uint16_t)(payload_len - offset) < 3U)
        {
            return TVLCOM_ERR_FORMAT;
        }

        current.type = payload[offset];
        current.length = tvlcom_read_le16(&payload[offset + 1U]);
        offset = (uint16_t)(offset + 3U);

        if ((uint16_t)(payload_len - offset) < current.length)
        {
            return TVLCOM_ERR_FORMAT;
        }

        current.value = &payload[offset];
        if (current.type == type)
        {
            *out_tlv = current;
            found = 1U;
        }

        offset = (uint16_t)(offset + current.length);
    }

    return found ? TVLCOM_OK : TVLCOM_ERR_NOT_FOUND;
}

uint16_t tvlcom_crc16(const uint8_t *data, uint16_t length)
{
    uint16_t crc = 0xFFFFU;
    uint16_t i;

    if (data == NULL)
    {
        return 0U;
    }

    while (length-- > 0U)
    {
        crc ^= *data++;
        for (i = 0U; i < 8U; ++i)
        {
            if ((crc & 0x0001U) != 0U)
            {
                crc = (uint16_t)((crc >> 1) ^ 0xA001U);
            }
            else
            {
                crc >>= 1;
            }
        }
    }

    return crc;
}

void tvlcom_parser_init(tvlcom_parser_t *parser)
{
    if (parser == NULL)
    {
        return;
    }

    parser->length = 0U;
    memset(parser->buffer, 0, sizeof(parser->buffer));
}

tvlcom_status_t tvlcom_frame_build(uint8_t cmd,
                                   uint8_t seq,
                                   const uint8_t *payload,
                                   uint16_t payload_len,
                                   uint8_t *out_frame,
                                   uint16_t out_capacity,
                                   uint16_t *out_frame_len)
{
    uint16_t body_len;
    uint16_t frame_len;
    uint16_t crc;

    if ((out_frame == NULL) || (out_frame_len == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    if ((payload == NULL) && (payload_len != 0U))
    {
        return TVLCOM_ERR_ARG;
    }

    if (payload_len > TVLCOM_MAX_PAYLOAD_SIZE)
    {
        return TVLCOM_ERR_OVERFLOW;
    }

    body_len = (uint16_t)(payload_len + 2U);
    frame_len = (uint16_t)(body_len + 6U);

    if (out_capacity < frame_len)
    {
        return TVLCOM_ERR_OVERFLOW;
    }

    out_frame[0] = TVLCOM_SOF0;
    out_frame[1] = TVLCOM_SOF1;
    tvlcom_write_le16(&out_frame[2], body_len);
    out_frame[4] = cmd;
    out_frame[5] = seq;

    if (payload_len > 0U)
    {
        memcpy(&out_frame[6], payload, payload_len);
    }

    crc = tvlcom_crc16(out_frame, (uint16_t)(frame_len - 2U));
    tvlcom_write_le16(&out_frame[frame_len - 2U], crc);

    *out_frame_len = frame_len;
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_parser_input(tvlcom_parser_t *parser,
                                    const uint8_t *data,
                                    uint16_t data_len,
                                    tvlcom_frame_t *out_frames,
                                    uint8_t max_frames,
                                    uint8_t *out_count)
{
    tvlcom_status_t status = TVLCOM_OK;
    uint8_t parsed_count = 0U;

    if ((parser == NULL) || (out_count == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    *out_count = 0U;

    if ((data == NULL) && (data_len != 0U))
    {
        return TVLCOM_ERR_ARG;
    }

    if ((out_frames == NULL) && (max_frames != 0U))
    {
        return TVLCOM_ERR_ARG;
    }

    if ((uint32_t)parser->length + data_len > (uint32_t)sizeof(parser->buffer))
    {
        parser->length = 0U;
        return TVLCOM_ERR_OVERFLOW;
    }

    if (data_len > 0U)
    {
        memcpy(&parser->buffer[parser->length], data, data_len);
        parser->length = (uint16_t)(parser->length + data_len);
    }

    while (parser->length >= 6U)
    {
        uint16_t body_len;
        uint16_t total_len;
        uint16_t recv_crc;
        uint16_t calc_crc;

        if ((parser->buffer[0] != TVLCOM_SOF0) ||
            (parser->buffer[1] != TVLCOM_SOF1))
        {
            tvlcom_buffer_remove_prefix(parser->buffer, &parser->length, 1U);
            continue;
        }

        body_len = tvlcom_read_le16(&parser->buffer[2]);
        total_len = (uint16_t)(body_len + 6U);

        if (body_len < 2U)
        {
            tvlcom_buffer_remove_prefix(parser->buffer, &parser->length, 2U);
            status = TVLCOM_ERR_FORMAT;
            continue;
        }

        if (body_len > (TVLCOM_MAX_PAYLOAD_SIZE + 2U))
        {
            tvlcom_buffer_remove_prefix(parser->buffer, &parser->length, 2U);
            status = TVLCOM_ERR_OVERFLOW;
            continue;
        }

        if (parser->length < total_len)
        {
            break;
        }

        recv_crc = tvlcom_read_le16(&parser->buffer[total_len - 2U]);
        calc_crc = tvlcom_crc16(parser->buffer, (uint16_t)(total_len - 2U));

        if (recv_crc != calc_crc)
        {
            tvlcom_buffer_remove_prefix(parser->buffer, &parser->length, total_len);
            status = TVLCOM_ERR_CRC;
            continue;
        }

        if (parsed_count < max_frames)
        {
            out_frames[parsed_count].cmd = parser->buffer[4];
            out_frames[parsed_count].seq = parser->buffer[5];
            out_frames[parsed_count].payload_len = (uint16_t)(body_len - 2U);
            if (out_frames[parsed_count].payload_len > 0U)
            {
                memcpy(out_frames[parsed_count].payload,
                       &parser->buffer[6],
                       out_frames[parsed_count].payload_len);
            }
            ++parsed_count;
        }

        tvlcom_buffer_remove_prefix(parser->buffer, &parser->length, total_len);
    }

    *out_count = parsed_count;
    return status;
}

tvlcom_status_t tvlcom_payload_append_raw(uint8_t *payload,
                                          uint16_t capacity,
                                          uint16_t *io_length,
                                          uint8_t type,
                                          const uint8_t *value,
                                          uint16_t value_len)
{
    uint16_t offset;
    uint16_t needed;

    if ((payload == NULL) || (io_length == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    if ((value == NULL) && (value_len != 0U))
    {
        return TVLCOM_ERR_ARG;
    }

    offset = *io_length;
    needed = (uint16_t)(3U + value_len);

    if ((uint32_t)offset + needed > capacity)
    {
        return TVLCOM_ERR_OVERFLOW;
    }

    payload[offset] = type;
    tvlcom_write_le16(&payload[offset + 1U], value_len);
    if (value_len > 0U)
    {
        memcpy(&payload[offset + 3U], value, value_len);
    }

    *io_length = (uint16_t)(offset + needed);
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_add_u8(uint8_t *payload,
                                      uint16_t capacity,
                                      uint16_t *io_length,
                                      uint8_t type,
                                      uint8_t value)
{
    return tvlcom_payload_append_raw(payload, capacity, io_length, type, &value, 1U);
}

tvlcom_status_t tvlcom_payload_add_u16(uint8_t *payload,
                                       uint16_t capacity,
                                       uint16_t *io_length,
                                       uint8_t type,
                                       uint16_t value)
{
    uint8_t encoded[2];
    tvlcom_write_le16(encoded, value);
    return tvlcom_payload_append_raw(payload, capacity, io_length, type, encoded, 2U);
}

tvlcom_status_t tvlcom_payload_add_u32(uint8_t *payload,
                                       uint16_t capacity,
                                       uint16_t *io_length,
                                       uint8_t type,
                                       uint32_t value)
{
    uint8_t encoded[4];
    tvlcom_write_le32(encoded, value);
    return tvlcom_payload_append_raw(payload, capacity, io_length, type, encoded, 4U);
}

tvlcom_status_t tvlcom_payload_add_float(uint8_t *payload,
                                         uint16_t capacity,
                                         uint16_t *io_length,
                                         uint8_t type,
                                         float value)
{
    union
    {
        float f;
        uint32_t u32;
    } conv;

    conv.f = value;
    return tvlcom_payload_add_u32(payload, capacity, io_length, type, conv.u32);
}

tvlcom_status_t tvlcom_payload_add_string(uint8_t *payload,
                                          uint16_t capacity,
                                          uint16_t *io_length,
                                          uint8_t type,
                                          const char *value)
{
    uint16_t len;

    if (value == NULL)
    {
        return TVLCOM_ERR_ARG;
    }

    len = (uint16_t)strlen(value);
    return tvlcom_payload_append_raw(payload,
                                     capacity,
                                     io_length,
                                     type,
                                     (const uint8_t *)value,
                                     len);
}

tvlcom_status_t tvlcom_payload_next(const uint8_t *payload,
                                    uint16_t payload_len,
                                    uint16_t *io_offset,
                                    tvlcom_tlv_t *out_tlv)
{
    uint16_t offset;

    if ((payload == NULL) || (io_offset == NULL) || (out_tlv == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    offset = *io_offset;
    if (offset >= payload_len)
    {
        return TVLCOM_ERR_NOT_FOUND;
    }

    if ((uint16_t)(payload_len - offset) < 3U)
    {
        return TVLCOM_ERR_FORMAT;
    }

    out_tlv->type = payload[offset];
    out_tlv->length = tvlcom_read_le16(&payload[offset + 1U]);
    offset = (uint16_t)(offset + 3U);

    if ((uint16_t)(payload_len - offset) < out_tlv->length)
    {
        return TVLCOM_ERR_FORMAT;
    }

    out_tlv->value = &payload[offset];
    *io_offset = (uint16_t)(offset + out_tlv->length);
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_get_u8(const uint8_t *payload,
                                      uint16_t payload_len,
                                      uint8_t type,
                                      uint8_t *out_value)
{
    tvlcom_tlv_t tlv;
    tvlcom_status_t status;

    if (out_value == NULL)
    {
        return TVLCOM_ERR_ARG;
    }

    status = tvlcom_payload_find_last(payload, payload_len, type, &tlv);
    if (status != TVLCOM_OK)
    {
        return status;
    }

    if (tlv.length != 1U)
    {
        return TVLCOM_ERR_TYPE;
    }

    *out_value = tlv.value[0];
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_get_u16(const uint8_t *payload,
                                       uint16_t payload_len,
                                       uint8_t type,
                                       uint16_t *out_value)
{
    tvlcom_tlv_t tlv;
    tvlcom_status_t status;

    if (out_value == NULL)
    {
        return TVLCOM_ERR_ARG;
    }

    status = tvlcom_payload_find_last(payload, payload_len, type, &tlv);
    if (status != TVLCOM_OK)
    {
        return status;
    }

    if (tlv.length != 2U)
    {
        return TVLCOM_ERR_TYPE;
    }

    *out_value = tvlcom_read_le16(tlv.value);
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_get_u32(const uint8_t *payload,
                                       uint16_t payload_len,
                                       uint8_t type,
                                       uint32_t *out_value)
{
    tvlcom_tlv_t tlv;
    tvlcom_status_t status;

    if (out_value == NULL)
    {
        return TVLCOM_ERR_ARG;
    }

    status = tvlcom_payload_find_last(payload, payload_len, type, &tlv);
    if (status != TVLCOM_OK)
    {
        return status;
    }

    if (tlv.length != 4U)
    {
        return TVLCOM_ERR_TYPE;
    }

    *out_value = tvlcom_read_le32(tlv.value);
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_get_float(const uint8_t *payload,
                                         uint16_t payload_len,
                                         uint8_t type,
                                         float *out_value)
{
    union
    {
        uint32_t u32;
        float f;
    } conv;
    tvlcom_status_t status;

    if (out_value == NULL)
    {
        return TVLCOM_ERR_ARG;
    }

    status = tvlcom_payload_get_u32(payload, payload_len, type, &conv.u32);
    if (status != TVLCOM_OK)
    {
        return status;
    }

    *out_value = conv.f;
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_get_string(const uint8_t *payload,
                                          uint16_t payload_len,
                                          uint8_t type,
                                          char *out_value,
                                          uint16_t out_capacity,
                                          uint16_t *out_length)
{
    tvlcom_tlv_t tlv;
    tvlcom_status_t status;

    if ((out_value == NULL) || (out_length == NULL) || (out_capacity == 0U))
    {
        return TVLCOM_ERR_ARG;
    }

    status = tvlcom_payload_find_last(payload, payload_len, type, &tlv);
    if (status != TVLCOM_OK)
    {
        return status;
    }

    if (out_capacity <= tlv.length)
    {
        return TVLCOM_ERR_OVERFLOW;
    }

    memcpy(out_value, tlv.value, tlv.length);
    out_value[tlv.length] = '\0';
    *out_length = tlv.length;
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_payload_get_raw(const uint8_t *payload,
                                       uint16_t payload_len,
                                       uint8_t type,
                                       const uint8_t **out_value,
                                       uint16_t *out_length)
{
    tvlcom_tlv_t tlv;
    tvlcom_status_t status;

    if ((out_value == NULL) || (out_length == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    status = tvlcom_payload_find_last(payload, payload_len, type, &tlv);
    if (status != TVLCOM_OK)
    {
        return status;
    }

    *out_value = tlv.value;
    *out_length = tlv.length;
    return TVLCOM_OK;
}

void tvlcom_dispatcher_init(tvlcom_dispatcher_t *dispatcher)
{
    if (dispatcher == NULL)
    {
        return;
    }

    memset(dispatcher, 0, sizeof(*dispatcher));
}

void tvlcom_dispatcher_set_ack_handler(tvlcom_dispatcher_t *dispatcher,
                                       tvlcom_ack_handler_t ack_handler,
                                       void *user_ctx)
{
    if (dispatcher == NULL)
    {
        return;
    }

    dispatcher->ack_handler = ack_handler;
    dispatcher->ack_user_ctx = user_ctx;
}

void tvlcom_dispatcher_set_nack_handler(tvlcom_dispatcher_t *dispatcher,
                                        tvlcom_nack_handler_t nack_handler,
                                        void *user_ctx)
{
    if (dispatcher == NULL)
    {
        return;
    }

    dispatcher->nack_handler = nack_handler;
    dispatcher->nack_user_ctx = user_ctx;
}

tvlcom_status_t tvlcom_dispatcher_register(tvlcom_dispatcher_t *dispatcher,
                                           uint8_t cmd,
                                           tvlcom_handler_t handler,
                                           void *user_ctx)
{
    uint32_t i;
    uint32_t free_index = TVLCOM_MAX_HANDLERS;

    if ((dispatcher == NULL) || (handler == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    if ((cmd == TVLCOM_CMD_ACK) || (cmd == TVLCOM_CMD_NACK))
    {
        return TVLCOM_ERR_ARG;
    }

    for (i = 0U; i < TVLCOM_MAX_HANDLERS; ++i)
    {
        if ((dispatcher->entries[i].in_use != 0U) &&
            (dispatcher->entries[i].cmd == cmd))
        {
            dispatcher->entries[i].handler = handler;
            dispatcher->entries[i].user_ctx = user_ctx;
            return TVLCOM_OK;
        }

        if ((dispatcher->entries[i].in_use == 0U) && (free_index == TVLCOM_MAX_HANDLERS))
        {
            free_index = i;
        }
    }

    if (free_index >= TVLCOM_MAX_HANDLERS)
    {
        return TVLCOM_ERR_OVERFLOW;
    }

    dispatcher->entries[free_index].in_use = 1U;
    dispatcher->entries[free_index].cmd = cmd;
    dispatcher->entries[free_index].handler = handler;
    dispatcher->entries[free_index].user_ctx = user_ctx;
    return TVLCOM_OK;
}

tvlcom_status_t tvlcom_dispatcher_dispatch(tvlcom_dispatcher_t *dispatcher,
                                           const tvlcom_frame_t *frame)
{
    uint32_t i;

    if ((dispatcher == NULL) || (frame == NULL))
    {
        return TVLCOM_ERR_ARG;
    }

    if (frame->cmd == TVLCOM_CMD_ACK)
    {
        if (dispatcher->ack_handler != NULL)
        {
            dispatcher->ack_handler(frame->cmd,
                                    frame->seq,
                                    frame->payload,
                                    frame->payload_len,
                                    dispatcher->ack_user_ctx);
            return TVLCOM_OK;
        }

        return TVLCOM_ERR_NOT_FOUND;
    }

    if (frame->cmd == TVLCOM_CMD_NACK)
    {
        if (dispatcher->nack_handler != NULL)
        {
            dispatcher->nack_handler(frame->cmd,
                                     frame->seq,
                                     frame->payload,
                                     frame->payload_len,
                                     dispatcher->nack_user_ctx);
            return TVLCOM_OK;
        }

        return TVLCOM_ERR_NOT_FOUND;
    }

    for (i = 0U; i < TVLCOM_MAX_HANDLERS; ++i)
    {
        if ((dispatcher->entries[i].in_use != 0U) &&
            (dispatcher->entries[i].cmd == frame->cmd))
        {
            dispatcher->entries[i].handler(frame->seq,
                                           frame->payload,
                                           frame->payload_len,
                                           dispatcher->entries[i].user_ctx);
            return TVLCOM_OK;
        }
    }

    return TVLCOM_ERR_NOT_FOUND;
}

