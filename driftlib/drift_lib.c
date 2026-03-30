/* drift_lib.c - DLL for Python ctypes */
/* Compile: gcc -shared -o drift_lib.dll drift_lib.c -lm */

#include <math.h>
#include <stdint.h>

#ifdef _WIN32
#define DLLEXPORT __declspec(dllexport)
#else
#define DLLEXPORT
#endif

typedef struct {
    uint8_t r, g, b;
} DriftColor;

typedef enum {
    DRIFT_RED_AWAY = 0,
    DRIFT_BLUE_ORTHOGONAL = 1,
    DRIFT_GREEN_APPROACH = 2,
    DRIFT_ORANGE_STATIC = 3,
    DRIFT_YELLOW_TRANSITION = 4
} DriftState;

DLLEXPORT DriftState classify_drift(float velocity_toward, float velocity_ortho, float threshold) {
    float speed_away = -velocity_toward;
    
    if (fabsf(velocity_ortho) > threshold && fabsf(velocity_ortho) > fabsf(velocity_toward)) {
        return DRIFT_BLUE_ORTHOGONAL;
    }
    if (speed_away > threshold) {
        return DRIFT_RED_AWAY;
    }
    if (velocity_toward > threshold) {
        return DRIFT_GREEN_APPROACH;
    }
    if (fabsf(velocity_toward) < threshold && fabsf(velocity_ortho) < threshold) {
        return DRIFT_ORANGE_STATIC;
    }
    return DRIFT_YELLOW_TRANSITION;
}

DLLEXPORT void get_color(DriftState state, float intensity, uint8_t* r, uint8_t* g, uint8_t* b) {
    switch(state) {
        case DRIFT_RED_AWAY:
            *r = 255; *g = (uint8_t)(69 * intensity); *b = 0;
            break;
        case DRIFT_BLUE_ORTHOGONAL:
            *r = 0; *g = (uint8_t)(128 * intensity); *b = 255;
            break;
        case DRIFT_GREEN_APPROACH:
            *r = (uint8_t)(100 * intensity); *g = 255; *b = (uint8_t)(50 * intensity);
            break;
        case DRIFT_ORANGE_STATIC:
            *r = 255; *g = 165; *b = 0;
            break;
        case DRIFT_YELLOW_TRANSITION:
            *r = 255; *g = 255; *b = (uint8_t)(100 * intensity);
            break;
        default:
            *r = *g = *b = 128;
    }
}

DLLEXPORT const char* get_state_name(DriftState state) {
    const char* names[] = {"RED_AWAY", "BLUE_ORTHOGONAL", "GREEN_APPROACH", 
                          "ORANGE_STATIC", "YELLOW_TRANSITION"};
    return names[state];
}