/* ==========================================================================
 * mmuko_cv.c — MMUKO Camera Vision Framework Implementation
 * OBINexus | Nnamdi M. Okpala
 * ==========================================================================
 *
 * Compile standalone:
 *   gcc -O2 -march=native -ffast-math -o mmuko_cv_test mmuko_cv.c -lm
 *
 * Compile to WASM:
 *   emcc -O3 -s WASM=1 -s EXPORTED_FUNCTIONS="['_mmuko_cv_init',
 *        '_mmuko_cv_begin_frame','_mmuko_cv_feed_landmark',
 *        '_mmuko_cv_end_frame','_mmuko_detect_slice']"
 *        -s EXPORTED_RUNTIME_METHODS="['ccall','cwrap']"
 *        mmuko_cv.c -o mmuko_cv.js
 * ========================================================================== */

#include "mmuko_cv.h"
#include <string.h>
#include <stdio.h>

/* --------------------------------------------------------------------------
 * LANDMARK RING TOPOLOGY
 * MediaPipe Hands landmark connectivity — which joints are anatomically
 * adjacent. This is the "ring" in Cubit Ring, made explicit as a graph.
 *
 * Index reference:
 *   0=WRIST  1=THUMB_CMC  2=THUMB_MCP  3=THUMB_IP  4=THUMB_TIP
 *   5=INDEX_MCP  6=INDEX_PIP  7=INDEX_DIP  8=INDEX_TIP
 *   9=MIDDLE_MCP 10=MID_PIP  11=MID_DIP  12=MID_TIP
 *  13=RING_MCP  14=RING_PIP  15=RING_DIP  16=RING_TIP
 *  17=PINKY_MCP 18=PINKY_PIP 19=PINKY_DIP 20=PINKY_TIP
 * -------------------------------------------------------------------------- */
static const int LM_RING[MP_HAND_LANDMARKS][4] = {
    /* 0  WRIST     */ { 1,  5,  9,  13 },
    /* 1  THUMB_CMC */ { 0,  2, -1,  -1 },
    /* 2  THUMB_MCP */ { 1,  3, -1,  -1 },
    /* 3  THUMB_IP  */ { 2,  4, -1,  -1 },
    /* 4  THUMB_TIP */ { 3, -1, -1,  -1 },
    /* 5  IDX_MCP   */ { 0,  6,  9,  -1 },
    /* 6  IDX_PIP   */ { 5,  7, -1,  -1 },
    /* 7  IDX_DIP   */ { 6,  8, -1,  -1 },
    /* 8  IDX_TIP   */ { 7, -1, -1,  -1 },
    /* 9  MID_MCP   */ { 0,  5, 10,  13 },
    /* 10 MID_PIP   */ { 9, 11, -1,  -1 },
    /* 11 MID_DIP   */ {10, 12, -1,  -1 },
    /* 12 MID_TIP   */ {11, -1, -1,  -1 },
    /* 13 RING_MCP  */ { 0,  9, 14,  17 },
    /* 14 RING_PIP  */ {13, 15, -1,  -1 },
    /* 15 RING_DIP  */ {14, 16, -1,  -1 },
    /* 16 RING_TIP  */ {15, -1, -1,  -1 },
    /* 17 PINK_MCP  */ { 0, 13, 18,  -1 },
    /* 18 PINK_PIP  */ {17, 19, -1,  -1 },
    /* 19 PINK_DIP  */ {18, 20, -1,  -1 },
    /* 20 PINK_TIP  */ {19, -1, -1,  -1 },
};

/* Predefined constraint pairs: (lm_a, lm_b, label, rest_dist)
 * These are the "entanglement" bindings — joint dependency pairs.        */
typedef struct { int a; int b; float rest; const char *label; } cp_def_t;
static const cp_def_t CP_DEFS[] = {
    {  4,  8, 0.04f, "pinch"       },  /* thumb tip ↔ index tip         */
    {  4, 12, 0.06f, "thumb_mid"   },  /* thumb tip ↔ middle tip        */
    {  8, 12, 0.03f, "index_mid"   },  /* index tip ↔ middle tip        */
    {  0,  9, 0.20f, "wrist_palm"  },  /* wrist ↔ middle MCP (scale)   */
    {  5, 17, 0.25f, "knuckle_bar" },  /* index MCP ↔ pinky MCP        */
    {  8,  0, 0.50f, "index_reach" },  /* index tip ↔ wrist (extension) */
    { 12,  0, 0.55f, "mid_reach"   },
    {  4,  2, 0.05f, "thumb_curl"  },
    {  6,  5, 0.08f, "index_pip"   },  /* index PIP curl                */
    { 10,  9, 0.08f, "mid_pip"     },  /* middle PIP curl               */
};
#define CP_DEF_COUNT ((int)(sizeof(CP_DEFS)/sizeof(CP_DEFS[0])))

/* --------------------------------------------------------------------------
 * DRIFT THEOREM CLASSIFIER
 * Maps (v_toward, v_ortho) → DriftState
 * Threshold is tunable; default 0.015 normalised units/frame.
 * -------------------------------------------------------------------------- */
drift_state_t mmuko_classify_drift(float v_toward, float v_ortho,
                                    float threshold)
{
    float at = fabsf(v_toward);
    float ao = fabsf(v_ortho);

    if (at < threshold && ao < threshold) return DRIFT_ORANGE; /* static     */
    if (ao > at * 1.5f && ao > threshold) return DRIFT_BLUE;   /* orthogonal */
    if (v_toward >  threshold)            return DRIFT_GREEN;   /* approach   */
    if (v_toward < -threshold)            return DRIFT_RED;     /* recession  */
    return DRIFT_YELLOW;                                         /* transition */
}

/* --------------------------------------------------------------------------
 * COMPASS DIRECTION QUANTISER
 * Converts a velocity vector to one of 8 compass directions.
 * This implements the "directional bit topology" of the Cubit Ring.
 * -------------------------------------------------------------------------- */
compass_dir_t mmuko_quantise_direction(vec3f_t vel)
{
    float mag = sqrtf(vel.x*vel.x + vel.y*vel.y);
    if (mag < 1e-4f) return DIR_UNDEFINED;

    /* atan2 in degrees, 0° = East, CCW positive */
    float angle_deg = atan2f(vel.y, vel.x) * (180.0f / 3.14159265f);
    if (angle_deg < 0.0f) angle_deg += 360.0f;

    /* Quantise to 8 sectors of 45° each, offset by 22.5° for symmetric bins */
    int sector = (int)((angle_deg + 22.5f) / 45.0f) % 8;

    /* Map sectors to compass: E=0, NE=1, N=2, NW=3, W=4, SW=5, S=6, SE=7
     * MediaPipe y-axis is inverted (0=top), so North = negative y            */
    static const compass_dir_t sector_map[8] = {
        DIR_E, DIR_NE, DIR_N, DIR_NW, DIR_W, DIR_SW, DIR_S, DIR_SE
    };
    return sector_map[sector];
}

/* --------------------------------------------------------------------------
 * FEEDBACK ESTIMATOR — Nonlinear Resolution
 * W(t) = alpha * P(t) + (1 - alpha) * P(t-1)    (weighted spline)
 * Prediction:  P(t+1) = P(t) + (P(t) - P(t-1))  (linear extrapolation)
 * Both are computed over the ring history buffer.
 * -------------------------------------------------------------------------- */
void mmuko_estimator_push(feedback_estimator_t *est, vec3f_t pos)
{
    est->history[est->head] = pos;
    est->head = (est->head + 1) % MMUKO_HISTORY_FRAMES;
    if (est->count < MMUKO_HISTORY_FRAMES) est->count++;
}

vec3f_t mmuko_estimator_smooth(feedback_estimator_t *est)
{
    if (est->count == 0) return (vec3f_t){0,0,0};
    if (est->count == 1) return est->history[(est->head - 1 + MMUKO_HISTORY_FRAMES) % MMUKO_HISTORY_FRAMES];

    /* Weighted exponential moving average over history window */
    int idx_cur  = (est->head - 1 + MMUKO_HISTORY_FRAMES) % MMUKO_HISTORY_FRAMES;
    int idx_prev = (est->head - 2 + MMUKO_HISTORY_FRAMES) % MMUKO_HISTORY_FRAMES;
    float a = est->alpha;

    vec3f_t cur  = est->history[idx_cur];
    vec3f_t prev = est->history[idx_prev];

    est->smoothed = (vec3f_t){
        a * cur.x + (1.0f - a) * prev.x,
        a * cur.y + (1.0f - a) * prev.y,
        a * cur.z + (1.0f - a) * prev.z
    };
    return est->smoothed;
}

vec3f_t mmuko_estimator_predict(feedback_estimator_t *est)
{
    if (est->count < 2) return est->smoothed;

    int idx_cur  = (est->head - 1 + MMUKO_HISTORY_FRAMES) % MMUKO_HISTORY_FRAMES;
    int idx_prev = (est->head - 2 + MMUKO_HISTORY_FRAMES) % MMUKO_HISTORY_FRAMES;

    vec3f_t cur  = est->history[idx_cur];
    vec3f_t prev = est->history[idx_prev];

    /* Linear extrapolation: P(t+1) = 2*P(t) - P(t-1) */
    est->predicted = (vec3f_t){
        2.0f * cur.x - prev.x,
        2.0f * cur.y - prev.y,
        2.0f * cur.z - prev.z
    };
    return est->predicted;
}

/* --------------------------------------------------------------------------
 * CONSTRAINT EVALUATION — Entanglement binding check
 * -------------------------------------------------------------------------- */
consensus_t mmuko_eval_constraint(constraint_pair_t *cp,
                                   landmark_node_t   *lm_a,
                                   landmark_node_t   *lm_b)
{
    vec3f_t delta = vec3f_sub(lm_a->pos, lm_b->pos);
    float dist    = vec3f_mag(delta);

    cp->extension = dist - cp->rest_distance;
    float ratio   = dist / (cp->rest_distance + 0.001f);

    if (ratio < 1.2f) {
        cp->consensus = CONSENSUS_YES;
    } else if (ratio < 2.0f) {
        cp->consensus = CONSENSUS_MAYBE;
    } else {
        cp->consensus = CONSENSUS_NO;
    }
    return cp->consensus;
}

/* --------------------------------------------------------------------------
 * INIT HAND CONSTRAINTS — populate constraint_pair array for a hand
 * -------------------------------------------------------------------------- */
void mmuko_init_hand_constraints(hand_state_t *hand)
{
    int n = (CP_DEF_COUNT < MMUKO_CONSTRAINT_PAIRS) ? CP_DEF_COUNT : MMUKO_CONSTRAINT_PAIRS;
    for (int i = 0; i < n; i++) {
        hand->constraints[i].lm_a          = CP_DEFS[i].a;
        hand->constraints[i].lm_b          = CP_DEFS[i].b;
        hand->constraints[i].rest_distance = CP_DEFS[i].rest;
        hand->constraints[i].stiffness     = 1.0f;
        hand->constraints[i].extension     = 0.0f;
        hand->constraints[i].consensus     = CONSENSUS_NO;
        strncpy(hand->constraints[i].label, CP_DEFS[i].label, 15);
    }
    hand->constraint_count = n;
}

/* --------------------------------------------------------------------------
 * BUILD STATE GRAPH — landmark nodes + ring topology + direction
 * Maps to: Cubit Ring state graph generation
 * -------------------------------------------------------------------------- */
void mmuko_build_state_graph(hand_state_t *hand)
{
    for (int i = 0; i < MP_HAND_LANDMARKS; i++) {
        landmark_node_t *n = &hand->landmarks[i];
        n->index = i;
        /* Copy ring adjacency */
        for (int j = 0; j < 4; j++) n->neighbours[j] = LM_RING[i][j];
        /* Quantise velocity to compass direction */
        if (n->active) {
            n->direction = mmuko_quantise_direction(n->vel);
            /* Compute angular velocity from neighbour */
            if (LM_RING[i][0] >= 0) {
                landmark_node_t *nb = &hand->landmarks[LM_RING[i][0]];
                vec3f_t rel = vec3f_sub(n->vel, nb->vel);
                n->spin_mrad = (uint16_t)(vec3f_mag(rel) * 1000.0f);
            }
        }
    }
}

/* --------------------------------------------------------------------------
 * SMOOTH LANDMARKS — Nonlinear Resolution (feedback estimator per joint)
 * -------------------------------------------------------------------------- */
void mmuko_smooth_landmarks(hand_state_t *hand, float dt)
{
    for (int i = 0; i < MP_HAND_LANDMARKS; i++) {
        landmark_node_t      *n   = &hand->landmarks[i];
        feedback_estimator_t *est = &hand->estimators[i];

        if (!n->active) continue;
        mmuko_estimator_push(est, n->pos);
        vec3f_t smoothed   = mmuko_estimator_smooth(est);
        vec3f_t predicted  = mmuko_estimator_predict(est);

        /* Update velocity from smoothed positions */
        if (est->count >= 2) {
            float inv_dt = (dt > 1e-6f) ? (1.0f / dt) : 0.0f;
            vec3f_t raw_pos = n->pos;
            n->vel = (vec3f_t){
                (smoothed.x - raw_pos.x) * inv_dt,
                (smoothed.y - raw_pos.y) * inv_dt,
                (smoothed.z - raw_pos.z) * inv_dt
            };
        }
        n->pos_predicted = predicted;
    }
}

/* --------------------------------------------------------------------------
 * RESOLVE CONSTRAINTS — evaluate all entanglement pairs
 * Maps to: Nonlinear constraint propagation (iterative convergence step)
 * -------------------------------------------------------------------------- */
void mmuko_resolve_constraints(hand_state_t *hand)
{
    for (int i = 0; i < hand->constraint_count; i++) {
        constraint_pair_t *cp = &hand->constraints[i];
        landmark_node_t   *la = &hand->landmarks[cp->lm_a];
        landmark_node_t   *lb = &hand->landmarks[cp->lm_b];

        if (!la->active || !lb->active) {
            cp->consensus = CONSENSUS_NO;
            continue;
        }
        /* Update stiffness from confidence product */
        cp->stiffness = la->confidence * lb->confidence;
        mmuko_eval_constraint(cp, la, lb);
    }
}

/* --------------------------------------------------------------------------
 * UPDATE COORDINATE FRAME — Frame of Reference alignment
 * Uses wrist (LM 0), index MCP (LM 5), and pinky MCP (LM 17) to define
 * a stable hand coordinate system. All gesture measurements are in this frame.
 * -------------------------------------------------------------------------- */
void mmuko_update_coord_frame(hand_state_t *hand)
{
    landmark_node_t *wrist  = &hand->landmarks[0];
    landmark_node_t *idx    = &hand->landmarks[5];
    landmark_node_t *pinky  = &hand->landmarks[17];

    if (!wrist->active || !idx->active || !pinky->active) return;

    hand->frame.origin = wrist->pos;

    /* X axis: wrist → index MCP */
    vec3f_t kx = vec3f_sub(idx->pos, wrist->pos);
    float   mk = vec3f_mag(kx);
    if (mk < 1e-5f) return;
    hand->frame.axis_x  = (vec3f_t){ kx.x/mk, kx.y/mk, kx.z/mk };
    hand->frame.scale   = mk;

    /* Crude Y from wrist → middle MCP (LM 9) */
    landmark_node_t *mid = &hand->landmarks[9];
    if (mid->active) {
        vec3f_t ky = vec3f_sub(mid->pos, wrist->pos);
        float   my = vec3f_mag(ky);
        if (my > 1e-5f)
            hand->frame.axis_y = (vec3f_t){ ky.x/my, ky.y/my, ky.z/my };
    }
    hand->frame.calibrated = true;

    /* Palm centroid = average of MCP joints (5,9,13,17) */
    vec3f_t c = {0,0,0};
    int knuckles[4] = {5, 9, 13, 17};
    int kn = 0;
    for (int i = 0; i < 4; i++) {
        landmark_node_t *k = &hand->landmarks[knuckles[i]];
        if (k->active) { c.x+=k->pos.x; c.y+=k->pos.y; c.z+=k->pos.z; kn++; }
    }
    if (kn > 0) {
        hand->palm_centroid = (vec3f_t){ c.x/kn, c.y/kn, c.z/kn };
    }
}

/* --------------------------------------------------------------------------
 * UPDATE HYPOTHESES — Superposition set maintenance
 * For each candidate gesture, update confidence based on current constraints.
 * -------------------------------------------------------------------------- */
void mmuko_update_hypotheses(hand_state_t *hand, float dt)
{
    hypothesis_set_t *hs = &hand->hypotheses;

    /* Query constraint states */
    consensus_t pinch    = CONSENSUS_NO;
    consensus_t curl_idx = CONSENSUS_NO;

    for (int i = 0; i < hand->constraint_count; i++) {
        if (strcmp(hand->constraints[i].label, "pinch")      == 0) pinch    = hand->constraints[i].consensus;
        if (strcmp(hand->constraints[i].label, "index_pip")  == 0) curl_idx = hand->constraints[i].consensus;
    }

    /* Palm velocity from centroid */
    float palm_speed = vec3f_mag(hand->palm_velocity);
    vec3f_t palm_vel  = hand->palm_velocity;

    /* ---- HYPOTHESIS: PINCH ---- */
    {
        gesture_hypothesis_t *h = &hs->items[GESTURE_PINCH];
        h->id = GESTURE_PINCH;
        h->confidence = (pinch == CONSENSUS_YES)   ? 0.9f :
                        (pinch == CONSENSUS_MAYBE)  ? 0.5f : 0.05f;
    }

    /* ---- HYPOTHESIS: OPEN PALM ---- */
    {
        gesture_hypothesis_t *h = &hs->items[GESTURE_OPEN_PALM];
        h->id = GESTURE_OPEN_PALM;
        /* Open when pinch is NO and curl is NO and no constraints firing */
        int no_constraints = 1;
        for (int i = 0; i < hand->constraint_count; i++) {
            if (hand->constraints[i].consensus == CONSENSUS_YES) { no_constraints = 0; break; }
        }
        h->confidence = (pinch == CONSENSUS_NO && no_constraints) ? 0.85f : 0.1f;
    }

    /* ---- HYPOTHESIS: SWIPE (fruit slice) ---- */
    {
        gesture_hypothesis_t *h_h = &hs->items[GESTURE_SWIPE_H];
        gesture_hypothesis_t *h_v = &hs->items[GESTURE_SWIPE_V];
        gesture_hypothesis_t *h_d = &hs->items[GESTURE_SWIPE_DIAG];

        h_h->id = GESTURE_SWIPE_H;
        h_v->id = GESTURE_SWIPE_V;
        h_d->id = GESTURE_SWIPE_DIAG;

        if (palm_speed > MMUKO_SLICE_VELOCITY && pinch == CONSENSUS_NO) {
            float vx_abs = fabsf(palm_vel.x);
            float vy_abs = fabsf(palm_vel.y);
            float ratio  = (vy_abs > 1e-4f) ? (vx_abs / vy_abs) : 10.0f;

            h_h->confidence = (ratio > 2.0f) ? palm_speed : 0.1f;
            h_v->confidence = (ratio < 0.5f) ? palm_speed : 0.1f;
            h_d->confidence = (ratio >= 0.5f && ratio <= 2.0f) ? palm_speed : 0.1f;

            h_h->velocity = palm_speed; h_h->trajectory = palm_vel;
            h_v->velocity = palm_speed; h_v->trajectory = palm_vel;
            h_d->velocity = palm_speed; h_d->trajectory = palm_vel;
        } else {
            h_h->confidence = 0.0f;
            h_v->confidence = 0.0f;
            h_d->confidence = 0.0f;
        }
    }

    hs->count = GESTURE_COUNT;
}

/* --------------------------------------------------------------------------
 * COLLAPSE HYPOTHESES — Superposition → single winner
 * Maps to: constraint_resolve() collapsing the hypothesis set
 * -------------------------------------------------------------------------- */
void mmuko_collapse_hypotheses(hand_state_t *hand)
{
    hypothesis_set_t *hs = &hand->hypotheses;
    float best = -1.0f;
    hs->winner_idx = -1;

    for (int i = 0; i < hs->count; i++) {
        if (hs->items[i].confidence > best) {
            best = hs->items[i].confidence;
            hs->winner_idx = i;
        }
    }
}

/* --------------------------------------------------------------------------
 * SLICE DETECTION — Fruit Ninja integration output
 * A slice fires when ANY hand shows SWIPE_H, SWIPE_V, or SWIPE_DIAG
 * with velocity > MMUKO_SLICE_VELOCITY and pinch constraint = NO.
 * -------------------------------------------------------------------------- */
bool mmuko_detect_slice(mmuko_cv_ctx_t *ctx)
{
    ctx->slice_detected = false;

    for (int h = 0; h < ctx->hand_count; h++) {
        hand_state_t     *hand = &ctx->hands[h];
        hypothesis_set_t *hs   = &hand->hypotheses;

        if (!hand->present) continue;

        /* Check winning gesture */
        int wi = hs->winner_idx;
        if (wi < 0) continue;
        gesture_hypothesis_t *winner = &hs->items[wi];

        bool is_swipe = (winner->id == GESTURE_SWIPE_H  ||
                         winner->id == GESTURE_SWIPE_V  ||
                         winner->id == GESTURE_SWIPE_DIAG);

        if (is_swipe && winner->velocity > MMUKO_SLICE_VELOCITY) {
            ctx->slice_detected  = true;
            ctx->slice_velocity  = winner->velocity;
            ctx->slice_hand      = h;

            /* Index fingertip (LM 8) provides slice geometry */
            landmark_node_t *tip = &hand->landmarks[8];
            if (tip->active) {
                ctx->slice_start = tip->pos;
                ctx->slice_end   = tip->pos_predicted;
            }
            break;  /* first slicing hand wins */
        }
    }
    return ctx->slice_detected;
}

/* --------------------------------------------------------------------------
 * CONTEXT LIFECYCLE
 * -------------------------------------------------------------------------- */
void mmuko_cv_init(mmuko_cv_ctx_t *ctx)
{
    memset(ctx, 0, sizeof(*ctx));
    for (int h = 0; h < MMUKO_MAX_HANDS; h++) {
        hand_state_t *hand = &ctx->hands[h];
        hand->hand_id = h;
        mmuko_init_hand_constraints(hand);
        /* Initialise estimator alpha = 2/3 (MMUKO spline weight) */
        for (int i = 0; i < MP_HAND_LANDMARKS; i++) {
            hand->estimators[i].alpha = 0.667f;
        }
    }
}

void mmuko_cv_reset(mmuko_cv_ctx_t *ctx)
{
    uint32_t fn = ctx->frame_number;
    mmuko_cv_init(ctx);
    ctx->frame_number = fn;
}

/* --------------------------------------------------------------------------
 * FRAME PROCESSING API
 * -------------------------------------------------------------------------- */
void mmuko_cv_begin_frame(mmuko_cv_ctx_t *ctx, uint64_t timestamp_us)
{
    ctx->dt_us      = (ctx->frame_us > 0) ? (timestamp_us - ctx->frame_us) : 33333;
    ctx->frame_us   = timestamp_us;
    ctx->frame_number++;

    /* Reset hand presence */
    for (int h = 0; h < MMUKO_MAX_HANDS; h++) {
        ctx->hands[h].present = false;
    }
    ctx->hand_count = 0;

    /* Rolling FPS estimate */
    float dt_s = (float)ctx->dt_us * 1e-6f;
    ctx->fps = (dt_s > 1e-6f) ? (0.9f * ctx->fps + 0.1f * (1.0f / dt_s)) : ctx->fps;
}

void mmuko_cv_feed_landmark(mmuko_cv_ctx_t *ctx, int hand_idx, int lm_idx,
                             float x, float y, float z, float conf)
{
    if (hand_idx < 0 || hand_idx >= MMUKO_MAX_HANDS) return;
    if (lm_idx  < 0 || lm_idx  >= MP_HAND_LANDMARKS) return;

    hand_state_t    *hand = &ctx->hands[hand_idx];
    landmark_node_t *lm   = &hand->landmarks[lm_idx];

    /* Compute frame-delta velocity before overwriting position */
    if (lm->active) {
        float inv_dt = (ctx->dt_us > 0) ? (1e6f / (float)ctx->dt_us) : 0.0f;
        lm->vel = (vec3f_t){
            (x - lm->pos.x) * inv_dt,
            (y - lm->pos.y) * inv_dt,
            (z - lm->pos.z) * inv_dt
        };
    } else {
        lm->vel = (vec3f_t){0,0,0};
    }

    lm->pos        = (vec3f_t){x, y, z};
    lm->confidence = conf;
    lm->active     = (conf > 0.5f);

    /* Drift classification for this landmark */
    if (lm->active) {
        lm->drift = mmuko_classify_drift(lm->vel.z, lm->vel.x, 0.015f);
    }

    /* Mark hand as present */
    if (!hand->present) {
        hand->present = true;
        if (hand_idx >= ctx->hand_count) ctx->hand_count = hand_idx + 1;
    }
    hand->last_seen_us = ctx->frame_us;
}

void mmuko_cv_end_frame(mmuko_cv_ctx_t *ctx)
{
    float dt_s = (float)ctx->dt_us * 1e-6f;

    for (int h = 0; h < ctx->hand_count; h++) {
        hand_state_t *hand = &ctx->hands[h];
        if (!hand->present) continue;

        /* Stage 1: update coordinate frame (Frame of Reference) */
        mmuko_update_coord_frame(hand);

        /* Stage 2: build state graph with compass directions (Cubit Ring) */
        mmuko_build_state_graph(hand);

        /* Stage 3: smooth landmarks (Nonlinear Resolution) */
        mmuko_smooth_landmarks(hand, dt_s);

        /* Stage 4: evaluate all constraint pairs (Entanglement) */
        mmuko_resolve_constraints(hand);

        /* Stage 5: update hypothesis set (Superposition) */
        mmuko_update_hypotheses(hand, dt_s);

        /* Stage 6: collapse hypotheses to single winner */
        mmuko_collapse_hypotheses(hand);

        /* Palm velocity: centroid delta */
        static vec3f_t prev_centroid[MMUKO_MAX_HANDS] = {{0,0,0},{0,0,0}};
        float inv_dt = (dt_s > 1e-6f) ? (1.0f / dt_s) : 0.0f;
        hand->palm_velocity = (vec3f_t){
            (hand->palm_centroid.x - prev_centroid[h].x) * inv_dt,
            (hand->palm_centroid.y - prev_centroid[h].y) * inv_dt,
            (hand->palm_centroid.z - prev_centroid[h].z) * inv_dt
        };
        prev_centroid[h] = hand->palm_centroid;

        /* Hand-level drift from palm velocity */
        hand->hand_drift = mmuko_classify_drift(
            hand->palm_velocity.z, hand->palm_velocity.x, 0.015f);
    }

    /* Slice detection for game integration */
    mmuko_detect_slice(ctx);
}

/* --------------------------------------------------------------------------
 * DIAGNOSTIC PRINT (debug builds)
 * -------------------------------------------------------------------------- */
#ifdef MMUKO_CV_DEBUG
static const char *drift_names[] = {"RED","BLUE","GREEN","ORANGE","YELLOW"};
static const char *gesture_names[] = {
    "NONE","OPEN_PALM","FIST","POINT","PINCH","SWIPE_H","SWIPE_V","SWIPE_DIAG"
};
static const char *consensus_names[] = {"NO","MAYBE","YES"};

void mmuko_cv_debug_print(const mmuko_cv_ctx_t *ctx) {
    printf("Frame %u | FPS %.1f | Hands %d | Slice %s\n",
        ctx->frame_number, ctx->fps, ctx->hand_count,
        ctx->slice_detected ? "YES" : "no");
    for (int h = 0; h < ctx->hand_count; h++) {
        const hand_state_t *hand = &ctx->hands[h];
        if (!hand->present) continue;
        int wi = hand->hypotheses.winner_idx;
        printf("  Hand %d | drift=%s | gesture=%s (conf=%.2f) | speed=%.3f\n",
            h,
            drift_names[hand->hand_drift],
            wi >= 0 ? gesture_names[hand->hypotheses.items[wi].id] : "NONE",
            wi >= 0 ? hand->hypotheses.items[wi].confidence : 0.0f,
            vec3f_mag(hand->palm_velocity));
        /* Print active constraints */
        for (int i = 0; i < hand->constraint_count; i++) {
            const constraint_pair_t *cp = &hand->constraints[i];
            if (cp->consensus != CONSENSUS_NO)
                printf("    [%s] ext=%.3f %s\n",
                    cp->label, cp->extension, consensus_names[cp->consensus]);
        }
    }
    if (ctx->slice_detected)
        printf("  *** SLICE v=%.2f hand=%d ***\n",
            ctx->slice_velocity, ctx->slice_hand);
}
#endif /* MMUKO_CV_DEBUG */

/* --------------------------------------------------------------------------
 * MINIMAL TEST HARNESS
 * -------------------------------------------------------------------------- */
#ifdef MMUKO_CV_STANDALONE
int main(void) {
    mmuko_cv_ctx_t ctx;
    mmuko_cv_init(&ctx);

    /* Simulate 5 frames of a horizontal swipe on hand 0 */
    float positions[5][3] = {
        {0.5f, 0.5f, 0.0f},
        {0.6f, 0.5f, 0.0f},
        {0.7f, 0.5f, 0.0f},
        {0.8f, 0.5f, 0.0f},
        {0.9f, 0.5f, 0.0f},
    };

    for (int f = 0; f < 5; f++) {
        mmuko_cv_begin_frame(&ctx, (uint64_t)(f * 33333));
        /* Feed a simplified hand: just wrist + fingertips for demo */
        float x = positions[f][0], y = positions[f][1], z = positions[f][2];
        /* Wrist */
        mmuko_cv_feed_landmark(&ctx, 0,  0, x-0.1f, y,       z, 0.95f);
        /* Thumb tip */
        mmuko_cv_feed_landmark(&ctx, 0,  4, x+0.05f, y-0.1f, z, 0.92f);
        /* Index tip */
        mmuko_cv_feed_landmark(&ctx, 0,  8, x+0.1f, y-0.15f, z, 0.94f);
        /* Middle tip */
        mmuko_cv_feed_landmark(&ctx, 0, 12, x+0.05f, y-0.18f, z, 0.93f);
        /* MCP joints */
        mmuko_cv_feed_landmark(&ctx, 0,  5, x+0.02f, y-0.05f, z, 0.96f);
        mmuko_cv_feed_landmark(&ctx, 0,  9, x,       y-0.05f, z, 0.96f);
        mmuko_cv_feed_landmark(&ctx, 0, 13, x-0.02f, y-0.05f, z, 0.95f);
        mmuko_cv_feed_landmark(&ctx, 0, 17, x-0.05f, y-0.03f, z, 0.94f);

        mmuko_cv_end_frame(&ctx);

#ifdef MMUKO_CV_DEBUG
        mmuko_cv_debug_print(&ctx);
#endif
        printf("Frame %d: slice=%s drift=%d\n", f,
            ctx.slice_detected ? "YES" : "no",
            ctx.hands[0].hand_drift);
    }

    printf("\nTest complete. MMUKO CV framework operational.\n");
    return 0;
}
#endif /* MMUKO_CV_STANDALONE */
