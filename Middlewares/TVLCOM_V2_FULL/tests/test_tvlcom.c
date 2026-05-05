#include "tvlcom.h"

#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static const uint8_t k_expected_payload[] = {
    0x02, 0x02, 0x00, 0xE2, 0x04,
    0x10, 0x04, 0x00, 0xA4, 0x70, 0x9D, 0x3F
};

static const uint8_t k_expected_frame[] = {
    0xAA, 0x55, 0x0E, 0x00, 0x01, 0x01,
    0x02, 0x02, 0x00, 0xE2, 0x04,
    0x10, 0x04, 0x00, 0xA4, 0x70, 0x9D, 0x3F,
    0xE0, 0x7E
};

typedef struct
{
    uint8_t called;
    uint8_t seq;
    uint16_t u16_value;
    float float_value;
} test_dispatch_ctx_t;

typedef struct
{
    uint8_t called;
    uint8_t cmd;
    uint8_t seq;
    uint16_t payload_len;
} test_ack_ctx_t;

typedef test_ack_ctx_t test_nack_ctx_t;

static void test_handler(uint8_t seq,
                         const uint8_t *payload,
                         uint16_t payload_len,
                         void *user_ctx)
{
    test_dispatch_ctx_t *ctx = (test_dispatch_ctx_t *)user_ctx;

    ctx->called = 1U;
    ctx->seq = seq;
    assert(tvlcom_payload_get_u16(payload,
                                  payload_len,
                                  TVLCOM_TYPE_U16,
                                  &ctx->u16_value) == TVLCOM_OK);
    assert(tvlcom_payload_get_float(payload,
                                    payload_len,
                                    TVLCOM_TYPE_FLOAT,
                                    &ctx->float_value) == TVLCOM_OK);
}

static void test_ack_handler(uint8_t cmd,
                             uint8_t seq,
                             const uint8_t *payload,
                             uint16_t payload_len,
                             void *user_ctx)
{
    test_ack_ctx_t *ctx = (test_ack_ctx_t *)user_ctx;

    ctx->called = 1U;
    ctx->cmd = cmd;
    ctx->seq = seq;
    ctx->payload_len = payload_len;
    assert(payload != NULL);
    assert(payload_len == 0U);
}

static void test_nack_handler(uint8_t cmd,
                              uint8_t seq,
                              const uint8_t *payload,
                              uint16_t payload_len,
                              void *user_ctx)
{
    test_nack_ctx_t *ctx = (test_nack_ctx_t *)user_ctx;

    ctx->called = 1U;
    ctx->cmd = cmd;
    ctx->seq = seq;
    ctx->payload_len = payload_len;
    assert(payload != NULL);
    assert(payload_len == 0U);
}

static void test_build_payload_and_frame(void)
{
    uint8_t payload[TVLCOM_MAX_PAYLOAD_SIZE];
    uint8_t frame[TVLCOM_MAX_FRAME_SIZE];
    uint16_t payload_len = 0U;
    uint16_t frame_len = 0U;

    assert(tvlcom_payload_add_u16(payload,
                                  sizeof(payload),
                                  &payload_len,
                                  TVLCOM_TYPE_U16,
                                  1250U) == TVLCOM_OK);
    assert(tvlcom_payload_add_float(payload,
                                    sizeof(payload),
                                    &payload_len,
                                    TVLCOM_TYPE_FLOAT,
                                    1.23f) == TVLCOM_OK);
    assert(payload_len == sizeof(k_expected_payload));
    assert(memcmp(payload, k_expected_payload, sizeof(k_expected_payload)) == 0);

    assert(tvlcom_frame_build(0x01U,
                              0x01U,
                              payload,
                              payload_len,
                              frame,
                              sizeof(frame),
                              &frame_len) == TVLCOM_OK);
    assert(frame_len == sizeof(k_expected_frame));
    assert(memcmp(frame, k_expected_frame, sizeof(k_expected_frame)) == 0);
}

static void test_parse_complete_frame(void)
{
    tvlcom_parser_t parser;
    tvlcom_frame_t frames[2];
    uint8_t count = 0U;
    uint16_t value_u16 = 0U;
    float value_float = 0.0f;

    tvlcom_parser_init(&parser);
    assert(tvlcom_parser_input(&parser,
                               k_expected_frame,
                               sizeof(k_expected_frame),
                               frames,
                               2U,
                               &count) == TVLCOM_OK);
    assert(count == 1U);
    assert(frames[0].cmd == 0x01U);
    assert(frames[0].seq == 0x01U);
    assert(frames[0].payload_len == sizeof(k_expected_payload));
    assert(memcmp(frames[0].payload, k_expected_payload, sizeof(k_expected_payload)) == 0);
    assert(tvlcom_payload_get_u16(frames[0].payload,
                                  frames[0].payload_len,
                                  TVLCOM_TYPE_U16,
                                  &value_u16) == TVLCOM_OK);
    assert(value_u16 == 1250U);
    assert(tvlcom_payload_get_float(frames[0].payload,
                                    frames[0].payload_len,
                                    TVLCOM_TYPE_FLOAT,
                                    &value_float) == TVLCOM_OK);
    assert(fabsf(value_float - 1.23f) < 0.0001f);
}

static void test_parse_fragmented_and_junk_prefixed_frame(void)
{
    tvlcom_parser_t parser;
    tvlcom_frame_t frames[2];
    uint8_t count = 0U;
    const uint8_t junked[] = {0x00, 0x11, 0x22, 0xAA, 0x55, 0x0E, 0x00, 0x01, 0x01,
                              0x02, 0x02, 0x00, 0xE2, 0x04, 0x10, 0x04, 0x00, 0xA4,
                              0x70, 0x9D, 0x3F, 0xE0, 0x7E};

    tvlcom_parser_init(&parser);
    assert(tvlcom_parser_input(&parser,
                               k_expected_frame,
                               5U,
                               frames,
                               2U,
                               &count) == TVLCOM_OK);
    assert(count == 0U);
    assert(tvlcom_parser_input(&parser,
                               &k_expected_frame[5],
                               (uint16_t)(sizeof(k_expected_frame) - 5U),
                               frames,
                               2U,
                               &count) == TVLCOM_OK);
    assert(count == 1U);
    assert(frames[0].seq == 0x01U);

    tvlcom_parser_init(&parser);
    assert(tvlcom_parser_input(&parser,
                               junked,
                               sizeof(junked),
                               frames,
                               2U,
                               &count) == TVLCOM_OK);
    assert(count == 1U);
    assert(frames[0].cmd == 0x01U);
}

static void test_parse_multiple_frames(void)
{
    tvlcom_parser_t parser;
    tvlcom_frame_t frames[4];
    uint8_t stream[64];
    uint8_t frame2[TVLCOM_MAX_FRAME_SIZE];
    uint16_t frame2_len = 0U;
    uint8_t count = 0U;
    uint16_t total_len;

    assert(tvlcom_frame_build(0x01U,
                              0x02U,
                              k_expected_payload,
                              sizeof(k_expected_payload),
                              frame2,
                              sizeof(frame2),
                              &frame2_len) == TVLCOM_OK);

    memcpy(stream, k_expected_frame, sizeof(k_expected_frame));
    memcpy(&stream[sizeof(k_expected_frame)], frame2, frame2_len);
    total_len = (uint16_t)(sizeof(k_expected_frame) + frame2_len);

    tvlcom_parser_init(&parser);
    assert(tvlcom_parser_input(&parser,
                               stream,
                               total_len,
                               frames,
                               4U,
                               &count) == TVLCOM_OK);
    assert(count == 2U);
    assert(frames[0].seq == 0x01U);
    assert(frames[1].seq == 0x02U);
}

static void test_bad_crc_is_dropped(void)
{
    tvlcom_parser_t parser;
    tvlcom_frame_t frames[2];
    uint8_t bad_frame[sizeof(k_expected_frame)];
    uint8_t count = 0U;

    memcpy(bad_frame, k_expected_frame, sizeof(k_expected_frame));
    bad_frame[sizeof(bad_frame) - 1U] ^= 0x01U;

    tvlcom_parser_init(&parser);
    assert(tvlcom_parser_input(&parser,
                               bad_frame,
                               sizeof(bad_frame),
                               frames,
                               2U,
                               &count) == TVLCOM_ERR_CRC);
    assert(count == 0U);
}

static void test_dispatcher(void)
{
    tvlcom_dispatcher_t dispatcher;
    tvlcom_frame_t frame;
    tvlcom_frame_t ack_frame;
    tvlcom_frame_t nack_frame;
    test_dispatch_ctx_t ctx;
    test_ack_ctx_t ack_ctx;
    test_nack_ctx_t nack_ctx;

    memset(&ctx, 0, sizeof(ctx));
    memset(&ack_ctx, 0, sizeof(ack_ctx));
    memset(&nack_ctx, 0, sizeof(nack_ctx));
    memset(&frame, 0, sizeof(frame));
    memset(&ack_frame, 0, sizeof(ack_frame));
    memset(&nack_frame, 0, sizeof(nack_frame));
    frame.cmd = 0x01U;
    frame.seq = 0x5AU;
    frame.payload_len = sizeof(k_expected_payload);
    memcpy(frame.payload, k_expected_payload, sizeof(k_expected_payload));
    ack_frame.cmd = TVLCOM_CMD_ACK;
    ack_frame.seq = 0x5AU;
    nack_frame.cmd = TVLCOM_CMD_NACK;
    nack_frame.seq = 0x6BU;

    tvlcom_dispatcher_init(&dispatcher);
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &frame) == TVLCOM_ERR_NOT_FOUND);
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &ack_frame) == TVLCOM_ERR_NOT_FOUND);
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &nack_frame) == TVLCOM_ERR_NOT_FOUND);

    tvlcom_dispatcher_set_ack_handler(&dispatcher, test_ack_handler, &ack_ctx);
    tvlcom_dispatcher_set_nack_handler(&dispatcher, test_nack_handler, &nack_ctx);
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &frame) == TVLCOM_ERR_NOT_FOUND);
    assert(ack_ctx.called == 0U);
    assert(nack_ctx.called == 0U);

    assert(tvlcom_dispatcher_dispatch(&dispatcher, &ack_frame) == TVLCOM_OK);
    assert(ack_ctx.called == 1U);
    assert(ack_ctx.cmd == TVLCOM_CMD_ACK);
    assert(ack_ctx.seq == 0x5AU);
    assert(ack_ctx.payload_len == 0U);

    assert(tvlcom_dispatcher_dispatch(&dispatcher, &nack_frame) == TVLCOM_OK);
    assert(nack_ctx.called == 1U);
    assert(nack_ctx.cmd == TVLCOM_CMD_NACK);
    assert(nack_ctx.seq == 0x6BU);
    assert(nack_ctx.payload_len == 0U);

    memset(&ack_ctx, 0, sizeof(ack_ctx));
    memset(&nack_ctx, 0, sizeof(nack_ctx));
    assert(tvlcom_dispatcher_register(&dispatcher,
                                      TVLCOM_CMD_ACK,
                                      test_handler,
                                      &ctx) == TVLCOM_ERR_ARG);
    assert(tvlcom_dispatcher_register(&dispatcher,
                                      TVLCOM_CMD_NACK,
                                      test_handler,
                                      &ctx) == TVLCOM_ERR_ARG);
    assert(tvlcom_dispatcher_register(&dispatcher,
                                      0x01U,
                                      test_handler,
                                      &ctx) == TVLCOM_OK);
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &frame) == TVLCOM_OK);
    assert(ack_ctx.called == 0U);
    assert(nack_ctx.called == 0U);
    assert(ctx.called == 1U);
    assert(ctx.seq == 0x5AU);
    assert(ctx.u16_value == 1250U);
    assert(fabsf(ctx.float_value - 1.23f) < 0.0001f);

    tvlcom_dispatcher_set_ack_handler(&dispatcher, NULL, NULL);
    tvlcom_dispatcher_set_nack_handler(&dispatcher, NULL, NULL);
    memset(&ack_ctx, 0, sizeof(ack_ctx));
    memset(&nack_ctx, 0, sizeof(nack_ctx));
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &ack_frame) == TVLCOM_ERR_NOT_FOUND);
    assert(tvlcom_dispatcher_dispatch(&dispatcher, &nack_frame) == TVLCOM_ERR_NOT_FOUND);
    assert(ack_ctx.called == 0U);
    assert(nack_ctx.called == 0U);
}

int main(void)
{
    test_build_payload_and_frame();
    test_parse_complete_frame();
    test_parse_fragmented_and_junk_prefixed_frame();
    test_parse_multiple_frames();
    test_bad_crc_is_dropped();
    test_dispatcher();

    printf("All STM32/C TVLCOM tests passed.\n");
    return 0;
}

