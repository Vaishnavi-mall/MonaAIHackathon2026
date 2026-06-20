"""
Creative short-form video generator for marketing briefs.

Renders a 9:16 MP4 with vivid gradient backgrounds, bokeh, and scene transitions.
Pillow draws every frame; MoviePy assembles and encodes via ffmpeg.
No external AI or ImageMagick required.
"""

import logging
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

VW, VH = 540, 960          # 9:16 at half resolution
FPS = 15                   # sufficient for a preview; halves encoding time

SCALE_X = VW / 1080
SCALE_Y = VH / 1920

TIKTOK_SAFE = (
    int(20 * SCALE_X), int(160 * SCALE_Y),
    int((20 + 540) * SCALE_X), int((160 + 740) * SCALE_Y),
)
INSTAGRAM_SAFE = (
    int(20 * SCALE_X), int(80 * SCALE_Y),
    int((20 + 980) * SCALE_X), int((80 + 1580) * SCALE_Y),
)

# Vivid mood palettes: gradient top/bottom, bright accent, deep dark
MOOD_PALETTE = {
    "upbeat":    {"top": (255, 90, 30),   "bot": (140, 20, 220),  "accent": (255, 215, 0),   "dark": (25, 5, 55)},
    "energetic": {"top": (220, 20, 80),   "bot": (20, 10, 200),   "accent": (255, 80, 160),  "dark": (10, 5, 50)},
    "calming":   {"top": (10, 130, 170),  "bot": (10, 40, 100),   "accent": (80, 230, 210),  "dark": (5, 20, 55)},
    "romantic":  {"top": (200, 30, 110),  "bot": (55, 10, 140),   "accent": (255, 155, 210), "dark": (30, 5, 55)},
    "inspiring": {"top": (10, 160, 235),  "bot": (20, 55, 215),   "accent": (120, 245, 255), "dark": (5, 20, 70)},
    "natural":   {"top": (30, 170, 90),   "bot": (10, 65, 55),    "accent": (180, 245, 110), "dark": (5, 25, 15)},
    "luxury":    {"top": (180, 140, 30),  "bot": (20, 15, 30),    "accent": (240, 210, 100), "dark": (10, 8, 20)},
    "default":   {"top": (80, 20, 220),   "bot": (20, 85, 230),   "accent": (210, 145, 255), "dark": (15, 5, 70)},
}

_FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]

_font_cache: dict = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _font(size: int) -> ImageFont.ImageFont:
    if size not in _font_cache:
        for p in _FONT_PATHS:
            try:
                _font_cache[size] = ImageFont.truetype(p, size)
                break
            except (IOError, OSError):
                continue
        else:
            _font_cache[size] = ImageFont.load_default()
    return _font_cache[size]


def _palette(brief: dict) -> dict:
    mood = (brief.get("music_mood") or "default").lower()
    for key, pal in MOOD_PALETTE.items():
        if key in mood:
            return pal
    return MOOD_PALETTE["default"]


def _diagonal_gradient(top_rgb, bot_rgb) -> Image.Image:
    """Fast numpy diagonal gradient, returned as RGB PIL image."""
    xs = np.linspace(0, 1, VW, dtype=np.float32)
    ys = np.linspace(0, 1, VH, dtype=np.float32)
    t = (xs[np.newaxis, :] + ys[:, np.newaxis]) / 2.0   # (VH, VW)
    arr = np.empty((VH, VW, 3), dtype=np.uint8)
    for c, (tc, bc) in enumerate(zip(top_rgb, bot_rgb)):
        arr[:, :, c] = np.clip(tc + (bc - tc) * t, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _bokeh_layer(pal: dict, seed: int) -> Image.Image:
    """Blurred coloured circles on a transparent canvas."""
    bokeh = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(bokeh)
    state = seed & 0xFFFFFFFF
    accent, top = pal["accent"], pal["top"]

    def rng():
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state / 0xFFFFFFFF

    for _ in range(20):
        cx = int(rng() * VW)
        cy = int(rng() * VH)
        r  = int(35 + rng() * 110)
        a  = int(20 + rng() * 35)
        ct = rng()
        cr = int(accent[0] * ct + top[0] * (1 - ct))
        cg = int(accent[1] * ct + top[1] * (1 - ct))
        cb = int(accent[2] * ct + top[2] * (1 - ct))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(cr, cg, cb, a))

    return bokeh.filter(ImageFilter.GaussianBlur(radius=16))


def _accent_lines(pal: dict, seed: int) -> Image.Image:
    """Subtle diagonal accent lines."""
    layer = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    state = (seed ^ 0xDEAD) & 0xFFFFFFFF
    accent = pal["accent"]

    def rng():
        nonlocal state
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        return state / 0xFFFFFFFF

    for _ in range(4):
        offset = int(rng() * VW * 1.5)
        d.line([(offset - VH, 0), (offset, VH)], fill=(*accent, 16), width=int(2 + rng() * 3))

    return layer


def _build_bg(pal: dict, seed: int = 0) -> Image.Image:
    """Diagonal gradient + bokeh + accent lines, returned as RGB PIL image."""
    bg = _diagonal_gradient(pal["top"], pal["bot"]).convert("RGBA")
    bg = Image.alpha_composite(bg, _bokeh_layer(pal, seed))
    bg = Image.alpha_composite(bg, _accent_lines(pal, seed))
    return bg.convert("RGB")


def _wrap(text: str, draw: ImageDraw.ImageDraw, font: ImageFont.ImageFont, max_w: int) -> list:
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines or [""]


def _center_text(draw: ImageDraw.ImageDraw, text: str, cy: int, font, fill, max_w: int):
    """Word-wrap and draw text centred at vertical position cy."""
    lines = _wrap(text, draw, font, max_w)
    lh = int(draw.textbbox((0, 0), "Ag", font=font)[3] * 1.35)
    y0 = cy - (lh * len(lines)) // 2
    for i, line in enumerate(lines):
        bx = draw.textbbox((0, 0), line, font=font)
        x = (VW - (bx[2] - bx[0])) // 2
        draw.text((x, y0 + i * lh), line, font=font, fill=fill)


def _pill(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, fill, radius=12):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


# ── Frame renderers ───────────────────────────────────────────────────────────

def _render_intro(brief: dict, pal: dict, seed: int) -> Image.Image:
    bg = _build_bg(pal, seed)
    draw = ImageDraw.Draw(bg)
    accent = pal["accent"]
    dark   = pal["dark"]

    product  = (brief.get("product_name") or "Product")[:30]
    platform = (brief.get("platform") or "TikTok")
    hook     = (brief.get("hook_text") or "")
    dur_s    = brief.get("content_duration_seconds", 30)
    mood     = (brief.get("music_mood") or "").title()

    f_product  = _font(int(VW * 0.11))
    f_platform = _font(int(VW * 0.050))
    f_hook     = _font(int(VW * 0.073))
    f_meta     = _font(int(VW * 0.042))

    # Product name
    _center_text(draw, product, VH * 28 // 100, f_product, (255, 255, 255), VW - 60)

    # Platform pill
    bbox = draw.textbbox((0, 0), platform, font=f_platform)
    pw, ph = bbox[2] - bbox[0] + 34, bbox[3] - bbox[1] + 18
    px = (VW - pw) // 2
    py = VH * 40 // 100
    _pill(draw, px, py, px + pw, py + ph, (*accent, 230), radius=24)
    draw.text((px + 17, py + 9), platform, font=f_platform, fill=(*dark, 255))

    # Hook text in accent colour
    if hook:
        _center_text(draw, f'"{hook}"', VH * 57 // 100, f_hook, accent, VW - 70)

    # Meta line
    meta = f"{dur_s}s  ·  {mood} mood"
    _center_text(draw, meta, VH * 82 // 100, f_meta, (180, 180, 200), VW - 60)

    # Accent bar
    by = VH * 88 // 100
    draw.rectangle([int(VW * 0.1), by, int(VW * 0.9), by + 3], fill=(*accent, 150))

    return bg


def _render_scene(scene: dict, pal: dict, safe_zone: tuple, seed: int) -> Image.Image:
    bg = _build_bg(pal, seed)
    draw = ImageDraw.Draw(bg)
    accent = pal["accent"]
    dark   = pal["dark"]
    sx, sy, ex, ey = safe_zone
    sw, sh = ex - sx, ey - sy

    # Safe-zone glow border
    overlay = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle([sx, sy, ex, ey], fill=(*accent, 8))
    od.rectangle([sx, sy, ex, ey], outline=(*accent, 55), width=2)
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(bg)

    f_badge   = _font(int(VW * 0.040))
    f_visual  = _font(int(VW * 0.068))
    f_overlay = _font(int(VW * 0.060))
    f_voice   = _font(int(VW * 0.040))

    # Scene badge
    badge = f"Scene {scene.get('scene_number', 1)}  ·  {scene.get('duration_seconds', 5)}s"
    bw = int(VW * 0.42)
    _pill(draw, sx + 8, sy + 12, sx + 8 + bw, sy + 50, (*dark, 210), radius=20)
    draw.text((sx + 22, sy + 20), badge, font=f_badge, fill=(*accent, 255))

    # Visual description — large white text, centred in upper third of safe zone
    visual = (scene.get("visual") or "")[:120]
    _center_text(draw, visual, sy + sh * 35 // 100, f_visual, (255, 255, 255), sw - 40)

    # Text overlay — accent colour on dark pill, middle of safe zone
    text_ovl = (scene.get("text_overlay") or "")[:80]
    if text_ovl:
        ovl_cy  = sy + sh * 60 // 100
        ovl_pad = int(sh * 0.10)
        _pill(draw, sx + 6, ovl_cy - ovl_pad, ex - 6, ovl_cy + ovl_pad, (0, 0, 0, 175), radius=10)
        _center_text(draw, text_ovl, ovl_cy, f_overlay, accent, sw - 50)

    # Voiceover subtitle — light text at bottom of safe zone
    voiceover = (scene.get("voiceover") or "")[:120]
    if voiceover:
        vo_cy = ey - int(sh * 0.10)
        _pill(draw, sx + 4, ey - int(sh * 0.19), ex - 4, ey - 6, (0, 0, 0, 185), radius=8)
        _center_text(draw, voiceover, vo_cy, f_voice, (228, 228, 228), sw - 40)

    return bg


def _render_cta(brief: dict, pal: dict, seed: int) -> Image.Image:
    bg = _build_bg(pal, seed)
    # Dark overlay to make CTA pop
    dark_layer = Image.new("RGBA", (VW, VH), (*pal["dark"], 110))
    bg = Image.alpha_composite(bg.convert("RGBA"), dark_layer).convert("RGB")
    draw = ImageDraw.Draw(bg)
    accent = pal["accent"]

    cta  = (brief.get("call_to_action") or "Shop Now")
    tags = (brief.get("suggested_hashtags") or [])[:5]
    msg  = (brief.get("main_message") or "")[:160]

    f_cta  = _font(int(VW * 0.105))
    f_tags = _font(int(VW * 0.048))
    f_msg  = _font(int(VW * 0.046))

    # Top accent stripe
    draw.rectangle([0, 0, VW, 5], fill=(*accent, 255))

    # CTA text
    _center_text(draw, cta, VH * 35 // 100, f_cta, (255, 255, 255), VW - 50)

    # Hashtags in accent colour
    tag_line = "  ".join(f"#{t.lstrip('#')}" for t in tags)
    _center_text(draw, tag_line, VH * 55 // 100, f_tags, accent, VW - 40)

    # Main message
    if msg:
        _center_text(draw, msg, VH * 74 // 100, f_msg, (200, 200, 215), VW - 60)

    return bg


# ── Public API ────────────────────────────────────────────────────────────────

def generate_video(brief: dict, output_path: str) -> str:
    """
    Render a creative MP4 marketing video from a content brief.

    Strategy: render each card as a static PIL image → ImageClip with
    MoviePy FadeIn/FadeOut effects. No per-frame Python callbacks means
    fast encoding via ffmpeg.

    Args:
        brief:       Output of generate_content_brief().
        output_path: Destination .mp4 path.

    Returns:
        output_path on success.
    """
    try:
        from moviepy import ImageClip, concatenate_videoclips, vfx
    except ImportError as exc:
        raise RuntimeError("moviepy required — pip install moviepy") from exc

    pal = _palette(brief)
    platform  = brief.get("platform") or "TikTok"
    safe_zone = (
        INSTAGRAM_SAFE
        if "Instagram" in platform and "TikTok" not in platform
        else TIKTOK_SAFE
    )

    base_seed = hash(brief.get("product_name") or "") & 0xFFFFFF
    FADE = 0.4  # seconds for each cross-fade

    clips = []

    # --- Intro card ---
    intro_img = _render_intro(brief, pal, seed=base_seed)
    clips.append(
        ImageClip(np.array(intro_img))
        .with_duration(4.0)
        .with_effects([vfx.FadeIn(FADE), vfx.FadeOut(FADE)])
    )

    # --- Scene cards ---
    for i, scene in enumerate(brief.get("scene_breakdown") or []):
        dur = max(3, int(scene.get("duration_seconds") or 5))
        scene_seed = (base_seed + i * 7919) & 0xFFFFFF
        scene_img = _render_scene(scene, pal, safe_zone, seed=scene_seed)
        clips.append(
            ImageClip(np.array(scene_img))
            .with_duration(float(dur))
            .with_effects([vfx.FadeIn(FADE), vfx.FadeOut(FADE)])
        )

    # --- CTA card ---
    cta_img = _render_cta(brief, pal, seed=(base_seed + 99991) & 0xFFFFFF)
    clips.append(
        ImageClip(np.array(cta_img))
        .with_duration(4.0)
        .with_effects([vfx.FadeIn(FADE), vfx.FadeOut(FADE)])
    )

    video = concatenate_videoclips(clips, method="compose")
    try:
        video.write_videofile(
            output_path,
            fps=FPS,
            codec="libx264",
            audio=False,
            logger=None,
        )
    finally:
        video.close()

    logger.info("Video rendered → %s", output_path)
    return output_path
