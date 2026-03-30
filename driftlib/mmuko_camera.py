"""
MMUKO Fluid Camera System
Python + OpenCV + C DLL with zoom support
Date: 2026-03-05 | OBINexus Constitutional Computing
"""

import cv2
import numpy as np
import ctypes
import math
from ctypes import cdll, c_float, c_uint8, c_char_p, POINTER

# Load C library
try:
    drift_lib = cdll.LoadLibrary('./drift_lib.dll')
except OSError:
    print("ERROR: drift_lib.dll not found. Run compile_dll.bat first.")
    exit(1)

# Setup C function signatures
drift_lib.classify_drift.argtypes = [c_float, c_float, c_float]
drift_lib.classify_drift.restype = ctypes.c_int

drift_lib.get_color.argtypes = [ctypes.c_int, c_float, POINTER(c_uint8), POINTER(c_uint8), POINTER(c_uint8)]
drift_lib.get_color.restype = None

drift_lib.get_state_name.argtypes = [ctypes.c_int]
drift_lib.get_state_name.restype = c_char_p

# State mapping
STATE_NAMES = {
    0: "RED (AWAY)",
    1: "BLUE (ORTHOGONAL)",
    2: "GREEN (APPROACH)",
    3: "ORANGE (STATIC)",
    4: "YELLOW (TRANSITION)"
}

STATE_COLORS_BGR = {
    0: (0, 55, 255),      # Red-Orange in BGR
    1: (255, 102, 0),     # Blue-Yellow in BGR
    2: (40, 255, 80),     # Green-Yellow-Orange in BGR
    3: (0, 165, 255),     # Orange in BGR
    4: (0, 255, 255),     # Yellow in BGR
}

class MMUKOCamera:
    def __init__(self, camera_id=0):
        self.cap = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)  # DirectShow for Windows
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {camera_id}")
        
        # Set resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        # Zoom properties (if camera supports it)
        self.zoom_level = 1.0
        self.max_zoom = 5.0  # Digital zoom max
        
        # Optical flow setup
        self.prev_gray = None
        self.feature_params = dict(
            maxCorners=100,
            qualityLevel=0.3,
            minDistance=7,
            blockSize=7
        )
        self.lk_params = dict(
            winSize=(15, 15),
            maxLevel=2,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03)
        )
        
        # Observer position (center of frame)
        self.observer_x = 640
        self.observer_y = 360
        
        print("MMUKO Camera initialized")
        print("Controls: [Q]uit | [+/-] Zoom | [R]eset zoom | [S]ave frame")
        
    def set_optical_zoom(self, zoom_value):
        """Set optical zoom if camera supports CAP_PROP_ZOOM"""
        # Try optical zoom first
        if self.cap.set(cv2.CAP_PROP_ZOOM, zoom_value):
            return True
        return False
    
    def apply_digital_zoom(self, frame, zoom):
        """Apply digital zoom by cropping and resizing"""
        if zoom <= 1.0:
            return frame
            
        h, w = frame.shape[:2]
        
        # Calculate crop region
        new_w = int(w / zoom)
        new_h = int(h / zoom)
        
        x1 = (w - new_w) // 2
        y1 = (h - new_h) // 2
        x2 = x1 + new_w
        y2 = y1 + new_h
        
        # Crop and resize back
        cropped = frame[y1:y2, x1:x2]
        zoomed = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        
        return zoomed
    
    def compute_motion_vectors(self, frame):
        """Compute optical flow and return dominant motion vector"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.prev_gray is None:
            self.prev_gray = gray
            return 0.0, 0.0, 0.0
        
        # Detect features
        p0 = cv2.goodFeaturesToTrack(self.prev_gray, mask=None, **self.feature_params)
        
        if p0 is None:
            self.prev_gray = gray
            return 0.0, 0.0, 0.0
        
        # Calculate optical flow
        p1, st, err = cv2.calcOpticalFlowPyrLK(self.prev_gray, gray, p0, None, **self.lk_params)
        
        if p1 is None or st is None:
            self.prev_gray = gray
            return 0.0, 0.0, 0.0
        
        # Select good points
        good_new = p1[st == 1]
        good_old = p0[st == 1]
        
        # Compute average motion vector
        motions = good_new - good_old
        if len(motions) == 0:
            self.prev_gray = gray
            return 0.0, 0.0, 0.0
        
        avg_motion = np.mean(motions, axis=0)
        dx, dy = avg_motion[0], avg_motion[1]
        
        # Convert to toward/away/orthogonal
        # Observer is at center, so vector from entity to observer
        entity_x = np.mean(good_new[:, 0])
        entity_y = np.mean(good_new[:, 1])
        
        to_observer_x = self.observer_x - entity_x
        to_observer_y = self.observer_y - entity_y
        
        # Normalize
        dist = math.sqrt(to_observer_x**2 + to_observer_y**2)
        if dist > 0:
            to_observer_x /= dist
            to_observer_y /= dist
        
        # Project motion onto toward/away axis
        velocity_toward = -(dx * to_observer_x + dy * to_observer_y)  # Negative because moving toward observer
        velocity_ortho = abs(dx * (-to_observer_y) + dy * to_observer_x)  # Perpendicular component
        
        # Scale by zoom level (higher zoom = more sensitive)
        velocity_toward *= self.zoom_level
        velocity_ortho *= self.zoom_level
        
        self.prev_gray = gray
        
        return velocity_toward, velocity_ortho, len(good_new)
    
    def classify_and_color(self, v_toward, v_ortho, threshold=0.5):
        """Call C library to classify motion"""
        state = drift_lib.classify_drift(c_float(v_toward), c_float(v_ortho), c_float(threshold))
        
        r, g, b = c_uint8(), c_uint8(), c_uint8()
        intensity = min(1.0, abs(v_toward) + abs(v_ortho))
        drift_lib.get_color(state, c_float(intensity), ctypes.byref(r), ctypes.byref(g), ctypes.byref(b))
        
        return state, (r.value, g.value, b.value)
    
    def draw_hud(self, frame, state, color_rgb, v_toward, v_ortho, feature_count):
        """Draw heads-up display with color state"""
        h, w = frame.shape[:2]
        
        # Get BGR color for OpenCV
        color_bgr = STATE_COLORS_BGR.get(state, (128, 128, 128))
        
        # Fill border with state color
        border_thickness = 20
        cv2.rectangle(frame, (0, 0), (w, h), color_bgr, border_thickness)
        
        # State text
        state_name = STATE_NAMES.get(state, "UNKNOWN")
        cv2.putText(frame, f"STATE: {state_name}", (30, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, color_bgr, 3)
        
        # Motion vectors
        cv2.putText(frame, f"Toward: {v_toward:+.2f}", (30, 100),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Ortho:  {v_ortho:+.2f}", (30, 140),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Features: {feature_count}", (30, 180),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, f"Zoom: {self.zoom_level:.1f}x", (30, 220),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Draw observer crosshair
        cx, cy = w // 2, h // 2
        cv2.drawMarker(frame, (cx, cy), (0, 255, 0), cv2.MARKER_CROSS, 40, 2)
        
        # Color swatch
        cv2.rectangle(frame, (w-150, 30), (w-30, 90), color_bgr, -1)
        cv2.rectangle(frame, (w-150, 30), (w-30, 90), (255, 255, 255), 2)
        
        return frame
    
    def run(self):
        """Main loop"""
        print("\nStarting MMUKO Fluid Camera...")
        print("Waiting for motion...")
        
        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("Camera error")
                break
            
            # Apply digital zoom
            display_frame = self.apply_digital_zoom(frame, self.zoom_level)
            
            # Compute motion
            v_toward, v_ortho, feature_count = self.compute_motion_vectors(display_frame)
            
            # Classify
            state, color_rgb = self.classify_and_color(v_toward, v_ortho)
            
            # Draw HUD
            display_frame = self.draw_hud(display_frame, state, color_rgb, 
                                         v_toward, v_ortho, feature_count)
            
            # Show
            cv2.imshow('MMUKO Fluid - OBINexus', display_frame)
            
            # Key handling
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q') or key == 27:  # Q or ESC
                break
            elif key == ord('+') or key == ord('='):
                self.zoom_level = min(self.max_zoom, self.zoom_level + 0.5)
                print(f"Zoom: {self.zoom_level:.1f}x")
            elif key == ord('-'):
                self.zoom_level = max(1.0, self.zoom_level - 0.5)
                print(f"Zoom: {self.zoom_level:.1f}x")
            elif key == ord('r'):
                self.zoom_level = 1.0
                print("Zoom reset")
            elif key == ord('s'):
                filename = f"mmuko_capture_{cv2.getTickCount()}.png"
                cv2.imwrite(filename, display_frame)
                print(f"Saved: {filename}")
        
        self.shutdown()
    
    def shutdown(self):
        self.cap.release()
        cv2.destroyAllWindows()
        print("MMUKO Camera shutdown")

if __name__ == "__main__":
    try:
        cam = MMUKOCamera(0)  # Use default camera
        cam.run()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()