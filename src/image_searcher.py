"""
Searches for car bounding boxes in an entire image
"""
import cv2
import numpy as np
import matplotlib.image as mpimg

from src import classifier
from src.classifier import single_img_features


class SearchWindowTier(object):
    def __init__(self, min_y, max_y, size, overlap):
        self.min_y = min_y
        self.max_y = max_y
        self.size = size
        self.overlap = overlap
        pass


search_window_tiers = [
    # SearchWindowTier(350, 550, 85, 0.60),
    SearchWindowTier(350, 550, 130, 0.82),
    SearchWindowTier(350, 720, 170, 0.75)
]

# KEYS into paramter dictionaries
WINDOW_DIM = 'WINDOW_DIM'
WINDOW_OVERLAP = 'WINDOW_OVERLAP'
ACTIVE_TIER = 'ACTIVE_TIER'


# Definition of a pipeline parameter
class ParamDef(object):
    def __init__(self, min_value, max_value, step, description):
        self.min_value = min_value
        self.max_value = max_value
        self.step = step
        self.description = description
        pass


# Definition of all parameters in our pipeline
param_defs = {
                 WINDOW_DIM: ParamDef(50, 200, 5, "window size"),
                 WINDOW_OVERLAP: ParamDef(0, 1, 0.01, "window overlap"),
                 ACTIVE_TIER: ParamDef(0, len(search_window_tiers), 1, "current tier"),
}

# Parameters to use for various steps of the pipeline
params = {
    WINDOW_DIM: 150,
    WINDOW_OVERLAP: 0.75,
    ACTIVE_TIER: len(search_window_tiers),
}

# y_start_stop = [350, 720]  # Min and max in y to search in slide_window()


# Define a function you will pass an image
# and the list of windows to be searched (output of slide_windows())
def search_windows(img, windows):
    # 1) Create an empty list to receive positive detection windows
    on_windows = []
    # 2) Iterate over all windows in the list
    for window in windows:
        # 3) Extract the test window from original image
        test_img = cv2.resize(img[window[0][1]:window[1][1], window[0][0]:window[1][0]], (64, 64))
        prediction = classifier.is_car(test_img)
        # 7) If positive (prediction == 1) then save the window
        if prediction == 1:
            on_windows.append(window)
    # 8) Return windows for positive detections
    return on_windows


# Define a function that takes an image,
# start and stop positions in both x and y,
# window size (x and y dimensions),
# and overlap fraction (for both x and y)
def slide_window(img, x_start_stop=(None, None), y_start_stop=(None, None),
                 xy_window=(64, 64), xy_overlap=(0.5, 0.5)):
    # If x and/or y start/stop positions not defined, set to image size
    if x_start_stop[0] is None:
        x_start_stop[0] = 0
    if x_start_stop[1] is None:
        x_start_stop[1] = img.shape[1]
    if y_start_stop[0] is None:
        y_start_stop[0] = 0
    if y_start_stop[1] is None:
        y_start_stop[1] = img.shape[0]
    # Compute the span of the region to be searched
    xspan = x_start_stop[1] - x_start_stop[0]
    yspan = y_start_stop[1] - y_start_stop[0]
    # Compute the number of pixels per step in x/y
    nx_pix_per_step = np.int(xy_window[0] * (1 - xy_overlap[0]))
    ny_pix_per_step = np.int(xy_window[1] * (1 - xy_overlap[1]))
    # Compute the number of windows in x/y
    nx_windows = np.int(xspan / nx_pix_per_step) - 1
    ny_windows = np.int(yspan / ny_pix_per_step) - 1
    # Initialize a list to append window positions to
    window_list = []
    # Loop through finding x and y window positions
    # Note: you could vectorize this step, but in practice
    # you'll be considering windows one by one with your
    # classifier, so looping makes sense
    for ys in range(ny_windows):
        for xs in range(nx_windows):
            # Calculate window position
            startx = xs * nx_pix_per_step + x_start_stop[0]
            endx = startx + xy_window[0]
            starty = ys * ny_pix_per_step + y_start_stop[0]
            endy = starty + xy_window[1]

            # Append window position to list
            window_list.append(((startx, starty), (endx, endy)))
    # Return the list of windows
    return window_list


def get_hot_windows(image):
    active_tier = params[ACTIVE_TIER]
    # If a single tier is selected in the interactive UI, only search that one
    # and use the tuning values
    if active_tier != len(search_window_tiers):
        tier = search_window_tiers[active_tier]
        windows = slide_window(
            image,
            x_start_stop=[None, None],
            y_start_stop=(tier.min_y, tier.max_y),
            xy_window=(params[WINDOW_DIM], params[WINDOW_DIM]),
            xy_overlap=(params[WINDOW_OVERLAP], tier.overlap))
    # Otherwise search all tiers
    else:
        windows = []
        for tier in search_window_tiers:
            tier_windows = slide_window(
                image,
                x_start_stop=[None, None],
                y_start_stop=(tier.min_y, tier.max_y),
                xy_window=(tier.size, tier.size),
                xy_overlap=(tier.overlap, tier.overlap))
            windows.extend(tier_windows)

    return windows, search_windows(image, windows)


# Define a function to draw bounding boxes
def draw_boxes(img, bboxes, color=(0, 0, 255), thick=6):
    # Make a copy of the image
    imcopy = np.copy(img)
    # Iterate through the bounding boxes
    for bbox in bboxes:
        # Draw a rectangle given bbox coordinates
        cv2.rectangle(imcopy, bbox[0], bbox[1], color, thick)
    # Return the image copy with boxes drawn
    return imcopy

def make_heatmap_like(img):
    return np.zeros_like(img[:, :, 0]).astype(np.float)

def add_heat(heatmap, bbox_list):
    # Iterate through list of bboxes
    for box in bbox_list:
        # Add += 1 for all pixels inside each bbox
        heatmap[box[0][1]:box[1][1], box[0][0]:box[1][0]] += 1

    # Return updated heatmap
    return heatmap

def normalize_heatmap(heatmap):
    heatmap /= np.max(np.abs(heatmap))

def set_active_tier(tier_num):
    prev_tier_num = params[ACTIVE_TIER]
    if prev_tier_num == tier_num:
        return

    params[ACTIVE_TIER] = tier_num
    # Persist tunable params for previously active tier
    if prev_tier_num != len(search_window_tiers):
        prev_tier = search_window_tiers[prev_tier_num]
        prev_tier.overlap = params[WINDOW_OVERLAP]
        prev_tier.size = params[WINDOW_DIM]
    # Load tunable params for next tier
    if tier_num != len(search_window_tiers):
        tier = search_window_tiers[tier_num]
        params[WINDOW_OVERLAP] = tier.overlap
        params[WINDOW_DIM] = tier.size

