/* ==========================================================================
 * mmuko_cv.h — MMUKO Camera Vision Framework
 * OBINexus | Nnamdi M. Okpala
 *
 * Translates MMUKO state topology into a real-time cybernetic vision system.
 *
 * CONCEPT MAPPING (MMUKO → Engineering):
 *   Cubit Ring      → landmark_state_node_t  (state graph node, O(1) ring lookup)
 *   Superposition   → hypothesis_set_t       (N competing gesture interpretations)
 *   Entanglement    → constraint_pair_t      (joint dependency / spring binding)
 *   Frame of Ref.   → coord_frame_t          (global sensor alignment model)
 *   Nonlinear Res.  → feedback_estimator_t   (iterative spline + Kalman smoother)
 *
 * Pipeline:
 *   Camera → Landmark Extraction → State Graph → Constraint Resolution
 *          → Motion Classification → Feedback Output
 *
 * Target: 30 fps @ 640x480, full pipeline < 16 ms (one frame budget)
 * ========================================================================== */

#ifndef MMUKO_CV_H
#define MMUKO_CV_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <math.h>

/* --------------------------------------------------------------------------
 * CONSTANTS
 * -------------------------------------------------------------------------- */
#define MMUKO_CV_VERSION        0x0100u   /* 1.0 */
#define MP_HAND_LANDMARKS       21        /* MediaPipe Hands landmark count */
#define MMUKO_COMPASS_DIRS      8         /* N NE E SE S SW W NW */
#define MMUKO_MAX_HANDS         2
#define MMUKO_MAX_HYPOTHESES    8         /* max concurrent gesture hypotheses */
#define MMUKO_CONSTRAINT_PAIRS  10        /* max joint constraint pairs */
#define MMUKO_HISTORY_FRAMES    8         /* temporal smoothing window */
#define MMUKO_SLICE_VELOCITY    0.35f     /* min normalised velocity for a slice */
#define MMUKO_PINCH_THRESHOLD   0.05f     /* normalised distance for pinch detect */

/* --------------------------------------------------------------------------
 * DRIFT STATES — 4-colour motion classifier
 * Maps directly to Drift Theorem: V(t) = P(t) - C(t)
 * -------------------------------------------------------------------------- */
typedef enum {
    DRIFT_RED    = 0,  /* radial recession  — Dr > 0  — moving away           */
    DRIFT_BLUE   = 1,  /* orthogonal drift  — ω high  — lateral / 90°         */
    DRIFT_GREEN  = 2,  /* radial approach   — Dr < 0  — closing in             */
    DRIFT_ORANGE = 3,  /* static / idle     — |V| < ε — below motion threshold */
    DRIFT_YELLOW = 4,  /* transition        — ambiguous inter-state            */
    DRIFT_STATE_COUNT
} drift_state_t;

/* --------------------------------------------------------------------------
 * COMPASS DIRECTION — 8-directional topology
 * Translates cubit ring directional bit encoding into engineering integers.
 * Bit positions: [N=0, NE=1, E=2, SE=3, S=4, SW=5, W=6, NW=7]
 * -------------------------------------------------------------------------- */
typedef enum {
    DIR_N  = 0, DIR_NE = 1, DIR_E  = 2, DIR_SE = 3,
    DIR_S  = 4, DIR_SW = 5, DIR_W  = 6, DIR_NW = 7,
    DIR_UNDEFINED = 8
} compass_dir_t;

/* --------------------------------------------------------------------------
 * 3D VECTOR — shared by position, velocity, acceleration
 * -------------------------------------------------------------------------- */
typedef struct { float x, y, z; } vec3f_t;

static inline vec3f_t vec3f_sub(vec3f_t a, vec3f_t b) {
    return (vec3f_t){ a.x-b.x, a.y-b.y, a.z-b.z };
}
static inline float vec3f_mag(vec3f_t v) {
    return sqrtf(v.x*v.x + v.y*v.y + v.z*v.z);
}
static inline vec3f_t vec3f_lerp(vec3f_t a, vec3f_t b, float t) {
    return (vec3f_t){ a.x+(b.x-a.x)*t, a.y+(b.y-a.y)*t, a.z+(b.z-a.z)*t };
}

/* --------------------------------------------------------------------------
 * LANDMARK STATE NODE — maps to MMUKO Cubit Ring
 *
 * Engineering role:  state graph node for one hand joint
 * Data:              current position, velocity, drift state, compass direction
 * Ring semantics:    index is position in 21-node landmark ring
 *                    neighbours[] gives O(1) access to anatomically adjacent joints
 * -------------------------------------------------------------------------- */
typedef struct {
    int          index;            /* MediaPipe landmark index [0..20]          */
    vec3f_t      pos;              /* normalised position [0,1]^3               */
    vec3f_t      vel;              /* frame-delta velocity                      */
    vec3f_t      pos_predicted;    /* spline-predicted next position            */
    float        confidence;       /* detection confidence [0,1]                */
    drift_state_t drift;           /* 4-state motion classifier output          */
    compass_dir_t direction;       /* quantised 8-compass movement direction    */
    uint16_t     spin_mrad;        /* angular velocity in milliradians          */
    bool         active;           /* landmark visible / tracked this frame     */
    int          neighbours[4];    /* adjacent landmark indices (ring topology) */
} landmark_node_t;

/* --------------------------------------------------------------------------
 * COORDINATE FRAME — maps to MMUKO Frame of Reference
 *
 * Engineering role:  global sensor alignment model
 * Sets the reference coordinate system so all landmark positions are
 * expressed in a stable world-frame regardless of camera orientation.
 * -------------------------------------------------------------------------- */
typedef struct {
    vec3f_t      origin;           /* wrist position as coordinate origin       */
    vec3f_t      axis_x;           /* palm-right unit vector                    */
    vec3f_t      axis_y;           /* palm-up unit vector                       */
    vec3f_t      axis_z;           /* palm-forward unit vector (depth)          */
    float        scale;            /* wrist-to-middle-mcp distance (px normalised) */
    bool         calibrated;       /* true once first stable frame seen         */
} coord_frame_t;

/* --------------------------------------------------------------------------
 * CONSTRAINT PAIR — maps to MMUKO Entanglement
 *
 * Engineering role:  joint dependency binding
 * Two landmarks are "entangled" when their relative state determines a
 * semantic gesture component (e.g. thumb-tip + index-tip → pinch).
 *
 * Spring model:  extension = |pos_a - pos_b|,  force = k * extension
 * Consensus:     YES (extension < threshold), MAYBE, NO
 * -------------------------------------------------------------------------- */
typedef enum {
    CONSENSUS_NO    = 0,
    CONSENSUS_MAYBE = 1,
    CONSENSUS_YES   = 2
} consensus_t;

typedef struct {
    int          lm_a;             /* landmark index A                          */
    int          lm_b;             /* landmark index B                          */
    float        rest_distance;    /* rest length of the spring (normalised)    */
    float        stiffness;        /* k value, driven by tracking confidence    */
    float        extension;        /* current |pos_a - pos_b| - rest_distance   */
    consensus_t  consensus;        /* resolved state of this constraint         */
    char         label[16];        /* e.g. "pinch", "curl", "spread"           */
} constraint_pair_t;

/* --------------------------------------------------------------------------
 * GESTURE HYPOTHESIS — one entry in the superposition set
 *
 * Engineering role:  single candidate gesture interpretation
 * The "superposition" of the Cubit Ring is exactly this: N hypotheses
 * co-exist until constraint resolution collapses them to one winner.
 * -------------------------------------------------------------------------- */
typedef enum {
    GESTURE_NONE       = 0,
    GESTURE_OPEN_PALM  = 1,
    GESTURE_FIST       = 2,
    GESTURE_POINT      = 3,
    GESTURE_PINCH      = 4,
    GESTURE_SWIPE_H    = 5,   /* horizontal swipe (fruit slice) */
    GESTURE_SWIPE_V    = 6,   /* vertical swipe                  */
    GESTURE_SWIPE_DIAG = 7,   /* diagonal swipe (fruit slice)    */
    GESTURE_COUNT
} gesture_id_t;

typedef struct {
    gesture_id_t id;
    float        confidence;       /* posterior probability [0,1]               */
    vec3f_t      trajectory;       /* dominant motion vector this frame         */
    float        velocity;         /* scalar speed (normalised)                 */
    uint64_t     first_seen_us;    /* microsecond timestamp of onset            */
    uint64_t     last_seen_us;     /* most recent matching frame                */
} gesture_hypothesis_t;

/* --------------------------------------------------------------------------
 * HYPOTHESIS SET — maps to MMUKO Superposition
 *
 * Engineering role:  multiple competing state interpretations
 * Resolution:        constraint_resolve() collapses to winner by max confidence
 * -------------------------------------------------------------------------- */
typedef struct {
    gesture_hypothesis_t items[MMUKO_MAX_HYPOTHESES];
    int                  count;
    int                  winner_idx;  /* index of highest-confidence item, or -1 */
} hypothesis_set_t;

/* --------------------------------------------------------------------------
 * FEEDBACK ESTIMATOR — maps to MMUKO Nonlinear Resolution
 *
 * Engineering role:  iterative convergence, frame-to-frame state propagation
 * Implements:        weighted spline W(t) = (2/3)P(t) + (1/3)P(t-Δt)
 *                    optional Kalman filter extension (see R1 roadmap)
 * -------------------------------------------------------------------------- */
typedef struct {
    vec3f_t      history[MMUKO_HISTORY_FRAMES];  /* ring buffer of past positions */
    int          head;             /* current write position in ring buffer     */
    int          count;            /* number of valid history entries           */
    vec3f_t      smoothed;         /* current smoothed position output          */
    vec3f_t      predicted;        /* next-frame prediction                     */
    float        alpha;            /* smoothing factor (default 0.667 = 2/3)    */
} feedback_estimator_t;

/* --------------------------------------------------------------------------
 * HAND STATE — complete per-hand state container
 * One of these exists for each tracked hand (max MMUKO_MAX_HANDS).
 * -------------------------------------------------------------------------- */
typedef struct {
    /* Landmark ring — 21 nodes, ring-connected by neighbours[] */
    landmark_node_t      landmarks[MP_HAND_LANDMARKS];
    /* Per-landmark smoothers */
    feedback_estimator_t estimators[MP_HAND_LANDMARKS];
    /* Joint constraint pairs (entanglement bindings) */
    constraint_pair_t    constraints[MMUKO_CONSTRAINT_PAIRS];
    int                  constraint_count;
    /* Competing gesture hypotheses (superposition) */
    hypothesis_set_t     hypotheses;
    /* Coordinate frame (global reference alignment) */
    coord_frame_t        frame;
    /* Metadata */
    bool                 present;          /* hand detected this frame           */
    int                  hand_id;          /* 0 = right / left index             */
    uint64_t             last_seen_us;
    /* Aggregate drift state for the whole hand (palm centroid) */
    drift_state_t        hand_drift;
    vec3f_t              palm_centroid;
    vec3f_t              palm_velocity;
} hand_state_t;

/* --------------------------------------------------------------------------
 * MMUKO CV CONTEXT — top-level runtime state
 * -------------------------------------------------------------------------- */
typedef struct {
    hand_state_t    hands[MMUKO_MAX_HANDS];
    int             hand_count;
    uint32_t        frame_number;
    uint64_t        frame_us;          /* timestamp of current frame            */
    uint64_t        dt_us;             /* delta from previous frame             */
    float           fps;               /* rolling average FPS                   */
    /* Slice detection output (for Fruit Ninja integration) */
    bool            slice_detected;
    vec3f_t         slice_start;
    vec3f_t         slice_end;
    float           slice_velocity;
    int             slice_hand;        /* which hand triggered the slice        */
} mmuko_cv_ctx_t;

/* --------------------------------------------------------------------------
 * API DECLARATIONS
 * -------------------------------------------------------------------------- */

/* Context lifecycle */
void mmuko_cv_init(mmuko_cv_ctx_t *ctx);
void mmuko_cv_reset(mmuko_cv_ctx_t *ctx);

/* Frame processing — call once per camera frame */
void mmuko_cv_begin_frame(mmuko_cv_ctx_t *ctx, uint64_t timestamp_us);
void mmuko_cv_feed_landmark(mmuko_cv_ctx_t *ctx, int hand, int lm_idx,
                             float x, float y, float z, float conf);
void mmuko_cv_end_frame(mmuko_cv_ctx_t *ctx);

/* Internal pipeline stages (exposed for testing / WebAssembly export) */
void      mmuko_build_state_graph(hand_state_t *hand);
void      mmuko_resolve_constraints(hand_state_t *hand);
void      mmuko_update_hypotheses(hand_state_t *hand, float dt);
void      mmuko_collapse_hypotheses(hand_state_t *hand);
void      mmuko_update_coord_frame(hand_state_t *hand);
void      mmuko_smooth_landmarks(hand_state_t *hand, float dt);

/* Drift Theorem classifier */
drift_state_t mmuko_classify_drift(float v_toward, float v_ortho,
                                    float threshold);
compass_dir_t mmuko_quantise_direction(vec3f_t vel);

/* Constraint helpers */
void      mmuko_init_hand_constraints(hand_state_t *hand);
consensus_t mmuko_eval_constraint(constraint_pair_t *cp,
                                   landmark_node_t *lm_a,
                                   landmark_node_t *lm_b);

/* Feedback estimator */
void      mmuko_estimator_push(feedback_estimator_t *est, vec3f_t pos);
vec3f_t   mmuko_estimator_smooth(feedback_estimator_t *est);
vec3f_t   mmuko_estimator_predict(feedback_estimator_t *est);

/* Slice detection (Fruit Ninja integration point) */
bool      mmuko_detect_slice(mmuko_cv_ctx_t *ctx);

#endif /* MMUKO_CV_H */
