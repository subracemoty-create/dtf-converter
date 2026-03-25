from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageFilter
import numpy as np
from scipy import ndimage
import os
import uuid

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def generate_halftone_alpha(brightness_map, bg_threshold, dot_size=6, angle=45):
    """
    Generate halftone dot pattern alpha channel.
    The output is BINARY alpha (0 or 255) but the DOT PATTERN creates
    the illusion of gradients - exactly what DTF printers need.
    """
    h, w = brightness_map.shape

    # --- GLOW SPREAD ---
    # Large blur to spread glow far from bright areas
    # Radius = 8% of image diagonal for natural light falloff
    glow_radius = max(int(np.sqrt(h**2 + w**2) * 0.08), 20)
    bright_img = Image.fromarray(brightness_map.astype(np.uint8), mode='L')
    glow_spread = bright_img.filter(ImageFilter.GaussianBlur(radius=glow_radius))
    glow_map = np.array(glow_spread, dtype=np.float64)

    # Combine: original for sharp rays + strong glow for soft ambient light
    combined = np.maximum(brightness_map, glow_map * 1.2)

    # Low threshold
    low_threshold = max(bg_threshold * 0.15, 2)

    # Gamma curve for natural falloff
    normalized = np.clip((combined - low_threshold) / (255 - low_threshold), 0, 1)
    smooth_alpha = (normalized ** 0.5) * 255

    # Kill truly black (original brightness near zero AND no glow reached)
    smooth_alpha[(brightness_map < 1) & (glow_map < 3)] = 0

    # Create rotated grid
    angle_rad = np.radians(angle)
    cos_a = np.cos(angle_rad)
    sin_a = np.sin(angle_rad)

    yy, xx = np.mgrid[0:h, 0:w]
    rx = xx * cos_a + yy * sin_a
    ry = -xx * sin_a + yy * cos_a

    cell_x = rx / dot_size
    cell_y = ry / dot_size

    dist_x = np.abs(cell_x - np.round(cell_x))
    dist_y = np.abs(cell_y - np.round(cell_y))
    dist = np.sqrt(dist_x ** 2 + dist_y ** 2)

    max_radius = 0.707
    normalized_alpha = smooth_alpha / 255.0
    dot_radius = normalized_alpha * max_radius

    halftone_mask = dist < dot_radius

    # Areas with alpha > 220 stay solid (bright core)
    solid_mask = smooth_alpha > 220
    final_alpha = np.where(solid_mask, 255.0, np.where(halftone_mask, 255.0, 0.0))

    return final_alpha


def detect_gradients(brightness):
    """Detect if image has significant gradients that need halftone."""
    grad_y = np.abs(np.diff(brightness, axis=0))
    grad_x = np.abs(np.diff(brightness, axis=1))
    h, w = brightness.shape
    gentle_grad_y = np.sum((grad_y > 1) & (grad_y < 15))
    gentle_grad_x = np.sum((grad_x > 1) & (grad_x < 15))
    total_pixels = h * w
    gradient_ratio = (gentle_grad_y + gentle_grad_x) / (2 * total_pixels)
    return gradient_ratio


def process_dtf(img, shirt_color='black', threshold=25, feather=3, min_cluster=500,
                halftone_mode='auto', dot_size=6, halftone_angle=45):
    """Process image for DTF printing - universal algorithm with halftone support"""
    img = img.convert("RGBA")
    pixels = np.array(img, dtype=np.float64)

    r, g, b = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
    brightness = 0.299 * r + 0.587 * g + 0.114 * b

    max_rgb = np.maximum(np.maximum(r, g), b)
    min_rgb = np.minimum(np.minimum(r, g), b)
    saturation = max_rgb - min_rgb

    # Auto-detect background
    h, w = brightness.shape
    corners = [
        brightness[:h // 10, :w // 10],
        brightness[:h // 10, -w // 10:],
        brightness[-h // 10:, :w // 10],
        brightness[-h // 10:, -w // 10:],
    ]
    bg_brightness = np.median(np.concatenate([c.flatten() for c in corners]))
    bg_threshold = bg_brightness + threshold

    # Determine halftone usage
    use_halftone = False
    if halftone_mode == 'on':
        use_halftone = True
    elif halftone_mode == 'auto':
        gradient_ratio = detect_gradients(brightness)
        use_halftone = gradient_ratio > 0.35

    # Clean edges - skip in halftone mode (rays/glow can reach edges)
    if not use_halftone:
        MIN_CONSECUTIVE = 10
        row_has_content = np.array([
            np.sum((brightness[row, :] > bg_threshold + 10) | (saturation[row, :] > 50)) > w * 0.05
            for row in range(h)
        ])

        top_start = 0
        for row in range(h - MIN_CONSECUTIVE):
            if all(row_has_content[row:row + MIN_CONSECUTIVE]):
                top_start = row
                break

        bot_end = h
        for row in range(h - 1, MIN_CONSECUTIVE, -1):
            if all(row_has_content[row - MIN_CONSECUTIVE:row]):
                bot_end = row
                break

        if top_start > 0:
            pixels[:top_start, :, :] = 0
            brightness[:top_start, :] = 0
            saturation[:top_start, :] = 0

        if bot_end < h:
            pixels[bot_end:, :, :] = 0
            brightness[bot_end:, :] = 0
            saturation[bot_end:, :] = 0

    r, g, b = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]

    # Detect content
    if shirt_color == 'black':
        is_bright = brightness > max(bg_threshold, 40)
        is_colorful = saturation > 50
        keep_mask = is_bright | is_colorful
    else:
        is_dark = brightness < (255 - bg_threshold)
        is_colorful = saturation > 50
        keep_mask = is_dark | is_colorful

    # Remove small isolated artifacts (skip in halftone - thin rays are valid)
    if not use_halftone:
        labeled, num_features = ndimage.label(keep_mask)
        if num_features > 0:
            component_sizes = ndimage.sum(keep_mask, labeled, range(1, num_features + 1))
            for i, size in enumerate(component_sizes):
                if size < min_cluster:
                    keep_mask[labeled == (i + 1)] = False

    # Generate alpha channel
    if use_halftone:
        brightness_clean = 0.299 * pixels[:, :, 0] + 0.587 * pixels[:, :, 1] + 0.114 * pixels[:, :, 2]
        alpha = generate_halftone_alpha(brightness_clean, bg_threshold, dot_size, halftone_angle)
        # Also include colorful pixels as solid
        color_mask = saturation > 50
        alpha = np.where(color_mask & (alpha == 0), 255.0, alpha)
    else:
        alpha_binary = np.where(keep_mask, 255.0, 0.0)
        alpha_img = Image.fromarray(alpha_binary.astype(np.uint8), mode='L')
        alpha_feathered = alpha_img.filter(ImageFilter.GaussianBlur(radius=feather))
        alpha = np.array(alpha_feathered, dtype=np.float64)
        alpha[alpha < 15] = 0

    # Preserve colors with depth
    content_mask = alpha > 0
    kept_brightness = brightness[content_mask]
    if len(kept_brightness) > 0:
        p5 = np.percentile(kept_brightness, 5)
        p95 = np.percentile(kept_brightness, 95)
        if p95 - p5 > 10:
            for ch in [0, 1, 2]:
                channel = pixels[:, :, ch]
                stretched = np.clip((channel - p5 * 0.8) * (240.0 / (p95 - p5 * 0.8)), 0, 255)
                normalized = stretched / 255.0
                s_curved = normalized ** 0.9 * 255.0
                pixels[:, :, ch] = np.where(content_mask, s_curved, channel)

    pixels[:, :, 3] = alpha
    return Image.fromarray(pixels.astype(np.uint8)), use_halftone


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/dtf')
def dtf():
    return render_template('index.html')


@app.route('/bgremover')
def bgremover():
    return render_template('bgremover.html')


@app.route('/convert', methods=['POST'])
def convert():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    shirt_color = request.form.get('shirt_color', 'black')
    threshold = int(request.form.get('threshold', 25))
    feather = int(request.form.get('feather', 3))
    min_cluster = int(request.form.get('min_cluster', 500))
    halftone_mode = request.form.get('halftone', 'auto')
    dot_size = int(request.form.get('dot_size', 6))
    halftone_angle = int(request.form.get('halftone_angle', 45))

    try:
        img = Image.open(file.stream)
        result, used_halftone = process_dtf(
            img, shirt_color, threshold, feather, min_cluster,
            halftone_mode, dot_size, halftone_angle
        )

        # Save result
        file_id = str(uuid.uuid4())[:8]
        orig_name = os.path.splitext(file.filename)[0]
        output_name = f"{orig_name}_dtf.png"
        output_path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
        result.save(output_path, "PNG")

        # Create preview (smaller)
        preview = result.copy()
        preview.thumbnail((600, 600))
        pw, ph = preview.size

        # Checker preview
        checker = Image.new('RGBA', (pw, ph), (200, 200, 200, 255))
        xs = np.arange(pw)
        ys = np.arange(ph)
        grid = (xs[None, :] // 12 + ys[:, None] // 12) % 2
        checker_arr = np.array(checker)
        checker_arr[grid == 1] = [255, 255, 255, 255]
        checker = Image.fromarray(checker_arr)
        checker.paste(preview, (0, 0), preview)
        preview_path = os.path.join(UPLOAD_DIR, f"{file_id}_preview.png")
        checker.save(preview_path, "PNG")

        # Black preview
        black_bg = Image.new('RGBA', (pw, ph), (0, 0, 0, 255))
        black_bg.paste(preview, (0, 0), preview)
        black_preview_path = os.path.join(UPLOAD_DIR, f"{file_id}_black.png")
        black_bg.save(black_preview_path, "PNG")

        return jsonify({
            'success': True,
            'file_id': file_id,
            'filename': output_name,
            'size': f"{result.size[0]}x{result.size[1]}",
            'halftone': bool(used_halftone)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/download/<file_id>')
def download(file_id):
    path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=f"dtf_{file_id}.png")
    return "File not found", 404


@app.route('/preview/<file_id>/<mode>')
def preview(file_id, mode):
    if mode == 'checker':
        path = os.path.join(UPLOAD_DIR, f"{file_id}_preview.png")
    elif mode == 'black':
        path = os.path.join(UPLOAD_DIR, f"{file_id}_black.png")
    else:
        path = os.path.join(UPLOAD_DIR, f"{file_id}.png")
    if os.path.exists(path):
        return send_file(path, mimetype='image/png')
    return "File not found", 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=True)
