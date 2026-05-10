/**
 * @file    : uf4_tvlcom.h
 * @brief   : TVLCOM_V2_FULL compatible USB CDC command adapter.
 */

#ifndef UF4DIGITALPOWER_UF4_TVLCOM_H
#define UF4DIGITALPOWER_UF4_TVLCOM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

void UF4_TvlcomInit(void);
void UF4_TvlcomProcess(void);
void UF4_TvlcomFeed(const uint8_t *data, uint16_t len);

#ifdef __cplusplus
}
#endif

#endif /* UF4DIGITALPOWER_UF4_TVLCOM_H */
