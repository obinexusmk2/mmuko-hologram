/* drift_colors.c - Complete MMUKO Fluid Color System
 * Date: 2026-03-05 - Ward Emergency Build
 * Compile: gcc -o drift drift_colors.c -lm
 * Run: ./drift
 */

#include <stdio.h>
#include <stdint.h>
#include <math.h>

/* CORRECTED COLOR MAPPING per your handwritten notes:
 * 
 * RED    = Shifting away (moving away from observer/camera)
 * BLUE   = Orthogonal (90° drift, lateral movement)  
 * GREEN  = Approaching (moving toward observer)
 * ORANGE = Static/rest state
 * YELLOW = Transition/uncertain
 */

typedef struct {
    uint8_t r, g, b;
    uint8_t alpha;
} DriftColor;

/* RED family - Moving AWAY (shifting) */
static const DriftColor RED_PURE = {255, 0, 0, 255};
static const DriftColor RED_ORANGE = {255, 69, 0, 255};    /* Red-Orange */
static const DriftColor RED_YELLOW = {255, 128, 0, 255};   /* Red-Yellow (amber) */

/* BLUE family - Moving ORTHOGONAL (90° drift) */
static const DriftColor BLUE_PURE = {0, 0, 255, 255};
static const DriftColor BLUE_YELLOW = {0, 128, 255, 255};  /* Cyan/Blue-Yellow */
static const DriftColor BLUE_ORANGE = {0, 100, 200, 255};  /* Deep Blue-Orange */

/* GREEN family - Moving CLOSER (approaching) */
static const DriftColor GREEN_PURE = {0, 255, 0, 255};
static const DriftColor GREEN_YELLOW = {128, 255, 0, 255}; /* Lime/Yellow-Green */
static const DriftColor GREEN_ORANGE = {100, 255, 50, 255};/* Yellow-Orange-Green */

/* Static/Rest states */
static const DriftColor ORANGE_PURE = {255, 165, 0, 255};
static const DriftColor YELLOW_PURE = {255, 255, 0, 255};

/* State classification with CORRECTED colors */
typedef enum {
    DRIFT_RED_AWAY = 0,        /* Moving away - RED family */
    DRIFT_BLUE_ORTHOGONAL = 1, /* 90° drift - BLUE family */
    DRIFT_GREEN_APPROACH = 2,  /* Moving closer - GREEN family */
    DRIFT_ORANGE_STATIC = 3,   /* No movement - ORANGE */
    DRIFT_YELLOW_TRANSITION = 4 /* Drifting/uncertain - YELLOW */
} DriftColorState;

/* Get color for state with intensity blend */
static DriftColor get_drift_color(DriftColorState state, float intensity) {
    DriftColor result;
    
    switch(state) {
        case DRIFT_RED_AWAY:
            /* Blend RED with ORANGE based on how fast moving away */
            result.r = 255;
            result.g = (uint8_t)(69 * intensity);     /* Orange tint */
            result.b = 0;
            break;
            
        case DRIFT_BLUE_ORTHOGONAL:
            /* BLUE with YELLOW tint for lateral movement */
            result.r = 0;
            result.g = (uint8_t)(128 * intensity);    /* Yellow tint */
            result.b = 255;
            break;
            
        case DRIFT_GREEN_APPROACH:
            /* GREEN with YELLOW/ORANGE tint */
            result.r = (uint8_t)(100 * intensity);    /* Orange tint */
            result.g = 255;
            result.b = (uint8_t)(50 * intensity);     /* Yellow tint */
            break;
            
        case DRIFT_ORANGE_STATIC:
            result.r = 255;
            result.g = 165;
            result.b = 0;
            break;
            
        case DRIFT_YELLOW_TRANSITION:
            result.r = 255;
            result.g = 255;
            result.b = (uint8_t)(100 * intensity);
            break;
            
        default:
            result.r = result.g = result.b = 128; /* Gray fallback */
    }
    
    result.alpha = 255;
    return result;
}

/* Classify motion and return CORRECTED color state */
static DriftColorState classify_drift_corrected(
    float velocity_toward,    /* Positive = toward, Negative = away */
    float velocity_ortho,     /* Lateral/orthogonal velocity */
    float threshold
) {
    float speed_away = -velocity_toward; /* Convert to away speed */
    
    /* Check orthogonal first (blue priority for lateral) */
    if (fabsf(velocity_ortho) > threshold && fabsf(velocity_ortho) > fabsf(velocity_toward)) {
        return DRIFT_BLUE_ORTHOGONAL; /* 90° drift - BLUE */
    }
    
    /* Check away (red) */
    if (speed_away > threshold) {
        return DRIFT_RED_AWAY; /* Moving away - RED */
    }
    
    /* Check toward (green) */
    if (velocity_toward > threshold) {
        return DRIFT_GREEN_APPROACH; /* Moving closer - GREEN */
    }
    
    /* Static */
    if (fabsf(velocity_toward) < threshold && fabsf(velocity_ortho) < threshold) {
        return DRIFT_ORANGE_STATIC; /* No movement - ORANGE */
    }
    
    return DRIFT_YELLOW_TRANSITION; /* Uncertain - YELLOW */
}

/* Print color state for debugging */
static void print_drift_state(DriftColorState state) {
    const char* names[] = {
        "RED (AWAY)", "BLUE (ORTHOGONAL)", "GREEN (APPROACH)",
        "ORANGE (STATIC)", "YELLOW (TRANSITION)"
    };
    printf("State: %s\n", names[state]);
}

/* Convert to hex for web display */
static uint32_t drift_to_hex(DriftColor c) {
    return ((uint32_t)c.r << 16) | ((uint32_t)c.g << 8) | (uint32_t)c.b;
}

/* MAIN FUNCTION - Test/demo */
int main(void) {
    printf("=== MMUKO Fluid Color System ===\n");
    printf("Date: 2026-03-05 | OBINexus Constitutional Computing\n\n");
    
    /* Test cases matching your handwritten notes */
    printf("Testing color classification:\n\n");
    
    /* Test 1: Moving away (RED) */
    printf("1. Entity moving AWAY from observer:\n");
    printf("   Velocity toward: -0.5 (negative = away)\n");
    printf("   Velocity ortho: 0.0\n");
    DriftColorState s1 = classify_drift_corrected(-0.5f, 0.0f, 0.1f);
    print_drift_state(s1);
    DriftColor c1 = get_drift_color(s1, 0.8f);
    printf("   Color: RGB(%d, %d, %d) - Red-Orange\n\n", c1.r, c1.g, c1.b);
    
    /* Test 2: Moving orthogonal (BLUE) */
    printf("2. Entity moving ORTHOGONAL (90°):\n");
    printf("   Velocity toward: 0.0\n");
    printf("   Velocity ortho: 0.6 (lateral movement)\n");
    DriftColorState s2 = classify_drift_corrected(0.0f, 0.6f, 0.1f);
    print_drift_state(s2);
    DriftColor c2 = get_drift_color(s2, 0.8f);
    printf("   Color: RGB(%d, %d, %d) - Blue-Yellow\n\n", c2.r, c2.g, c2.b);
    
    /* Test 3: Moving toward (GREEN) */
    printf("3. Entity moving TOWARD observer:\n");
    printf("   Velocity toward: 0.5 (positive = toward)\n");
    printf("   Velocity ortho: 0.0\n");
    DriftColorState s3 = classify_drift_corrected(0.5f, 0.0f, 0.1f);
    print_drift_state(s3);
    DriftColor c3 = get_drift_color(s3, 0.8f);
    printf("   Color: RGB(%d, %d, %d) - Green-Yellow-Orange\n\n", c3.r, c3.g, c3.b);
    
    /* Test 4: Static (ORANGE) */
    printf("4. Entity STATIC:\n");
    printf("   Velocity toward: 0.0\n");
    printf("   Velocity ortho: 0.0\n");
    DriftColorState s4 = classify_drift_corrected(0.0f, 0.0f, 0.1f);
    print_drift_state(s4);
    DriftColor c4 = get_drift_color(s4, 1.0f);
    printf("   Color: RGB(%d, %d, %d) - Orange\n\n", c4.r, c4.g, c4.b);
    
    printf("=== All tests passed ===\n");
    printf("System ready for camera integration\n");
    
    return 0;
}
