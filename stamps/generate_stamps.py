#!/usr/bin/env python3
"""Generate numbered clay stamps (STL) from stamps/catalog.json.

Each stamp is a solid block (rectangular, or round with "shape": "round")
with the text raised on its top face, mirrored, so that pressing it into clay
leaves a readable imprint. Optionally a motif (e.g. a sunflower) and a raised
border are added next to the text. The stamp ID (e.g. "001") is engraved, not
mirrored, on the front side wall so a printed stamp can always be matched
back to its catalog entry.

Usage:
    python3 stamps/generate_stamps.py            # build every stamp
    python3 stamps/generate_stamps.py 001 003    # build only these IDs

Requires: pip install fonttools shapely manifold3d trimesh numpy matplotlib
"""

import json
import sys
from pathlib import Path

import manifold3d as m3d
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely import affinity
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

HERE = Path(__file__).resolve().parent
CURVE_STEPS = 12  # line segments per curve segment


class _FlattenPen(BasePen):
    """Collects glyph contours as flattened point lists."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.contours = []
        self._cur = []

    def _moveTo(self, p):
        self._cur = [p]

    def _lineTo(self, p):
        self._cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self._cur[-1]
        for t in np.linspace(0, 1, CURVE_STEPS + 1)[1:]:
            mt = 1 - t
            self._cur.append(tuple(
                mt**3 * np.array(p0) + 3 * mt**2 * t * np.array(p1)
                + 3 * mt * t**2 * np.array(p2) + t**3 * np.array(p3)))

    def _qCurveToOne(self, p1, p2):
        p0 = self._cur[-1]
        for t in np.linspace(0, 1, CURVE_STEPS + 1)[1:]:
            mt = 1 - t
            self._cur.append(tuple(
                mt**2 * np.array(p0) + 2 * mt * t * np.array(p1) + t**2 * np.array(p2)))

    def _closePath(self):
        if len(self._cur) >= 3:
            self.contours.append(self._cur)
        self._cur = []

    _endPath = _closePath


def _nonzero_fill(contours):
    """Fill contours with the non-zero rule, as font rasterizers do.

    Variable/instanced fonts often have overlapping contours, so a plain
    even-odd fill would punch holes where strokes overlap.
    """
    cs = m3d.CrossSection([np.asarray(c, dtype=float) for c in contours],
                          m3d.FillRule.NonZero)
    # The resolved rings no longer overlap, so XOR rebuilds outers and holes.
    shape = None
    for ring in cs.to_polygons():
        poly = Polygon(ring).buffer(0)
        shape = poly if shape is None else shape.symmetric_difference(poly)
    return shape


def text_shape(text, font_path, rtl):
    """Return the text outline as a shapely geometry in font units."""
    font = TTFont(font_path)
    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"]
    # Hebrew letters need no shaping; RTL just means the visual order is reversed.
    visual = text[::-1] if rtl else text
    shapes, x = [], 0
    for ch in visual:
        name = cmap[ord(ch)]
        pen = _FlattenPen(glyph_set)
        glyph_set[name].draw(pen)
        if pen.contours:
            glyph = _nonzero_fill(pen.contours)
            shapes.append(affinity.translate(glyph, xoff=x))
        x += hmtx[name][0]
    return unary_union(shapes)


def fit_text(shape, max_w, max_h):
    """Scale shape (uniformly) to fit max_w x max_h and center it on the origin."""
    minx, miny, maxx, maxy = shape.bounds
    s = min(max_w / (maxx - minx), max_h / (maxy - miny))
    shape = affinity.scale(shape, s, s, origin=(0, 0))
    minx, miny, maxx, maxy = shape.bounds
    return affinity.translate(shape, -(minx + maxx) / 2, -(miny + maxy) / 2)


def fit_box(shape, cx, cy, max_w, max_h):
    """Like fit_text, but centered on (cx, cy)."""
    return affinity.translate(fit_text(shape, max_w, max_h), cx, cy)


def _almond(length, width, sharpness=0.8):
    """A pointed, petal/leaf shape from (0, 0) to (length, 0)."""
    t = np.linspace(0, 1, 25)
    half = width / 2 * np.sin(np.pi * t) ** sharpness
    outline = [(length * a, b) for a, b in zip(t, half)]
    outline += [(length * a, -b) for a, b in zip(t[::-1], half[::-1])]
    return Polygon(outline).buffer(0)


def sunflower_shape(r, petals=12, seed_d=0.7, seed_pitch=1.15, gap=0.6):
    """A sunflower of outer radius r (mm), centered on the origin.

    Pointed petals around a raised center disk, separated from it by a groove;
    the center has small dimples for the seeds.
    """
    center_r = 0.4 * r
    r_in = center_r + gap
    length = r - r_in
    # Petal width leaves a ~0.5 mm groove between neighbours at mid-length.
    width = 2 * np.pi * (r_in + length / 2) / petals - 0.5
    petal = affinity.translate(_almond(length, width), r_in)
    flower = unary_union([affinity.rotate(petal, 360 * i / petals, origin=(0, 0))
                          for i in range(petals)])
    center = Polygon([(center_r * np.cos(a), center_r * np.sin(a))
                      for a in np.linspace(0, 2 * np.pi, 72, endpoint=False)])
    seeds = []
    n = int(center_r // seed_pitch) + 1
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x = (i + 0.5 * (j % 2)) * seed_pitch
            y = j * seed_pitch * np.sqrt(3) / 2
            if np.hypot(x, y) + seed_d / 2 <= center_r - 0.4:
                seeds.append(Polygon([(x + seed_d / 2 * np.cos(a), y + seed_d / 2 * np.sin(a))
                                      for a in np.linspace(0, 2 * np.pi, 16, endpoint=False)]))
    return flower.union(center.difference(unary_union(seeds)))


def sunflower_stem_shape(r, stem_mm, stem_w=1.3, leaf_len=None, leaf_w=None):
    """A sunflower head of radius r centered on the origin, like the emoji:
    a stem hanging down stem_mm below the head with two leaves on it."""
    leaf_len = leaf_len or 0.95 * r
    leaf_w = leaf_w or 0.45 * r
    bottom = -r - stem_mm
    stem = Polygon([(-stem_w / 2, -r + 0.5), (stem_w / 2, -r + 0.5),
                    (stem_w / 2, bottom), (-stem_w / 2, bottom)])
    vein_w = 0.45
    leaves = []
    # One leaf per side, angled upwards, the left one a bit lower (as in 🌻).
    for side, frac in ((-1, 0.6), (1, 0.35)):
        leaf = _almond(leaf_len, leaf_w, sharpness=0.65)
        vein = Polygon([(0.15 * leaf_len, -vein_w / 2), (0.75 * leaf_len, -vein_w / 2),
                        (0.75 * leaf_len, vein_w / 2), (0.15 * leaf_len, vein_w / 2)])
        leaf = leaf.difference(vein)
        angle = 35 if side > 0 else 145
        leaf = affinity.rotate(leaf, angle, origin=(0, 0))
        leaves.append(affinity.translate(leaf, 0, -r - frac * stem_mm))
    return unary_union([sunflower_shape(r), stem] + leaves)


MOTIFS = {"sunflower": sunflower_shape, "sunflower_stem": sunflower_stem_shape}


def outline_shape(stamp, inset=0.0):
    """The stamp's footprint (rect or circle) shrunk by inset mm."""
    if stamp.get("shape", "rect") == "round":
        r = stamp["diameter_mm"] / 2 - inset
        return Polygon([(r * np.cos(a), r * np.sin(a))
                        for a in np.linspace(0, 2 * np.pi, 128, endpoint=False)])
    w, d = stamp["width_mm"] / 2 - inset, stamp["depth_mm"] / 2 - inset
    return Polygon([(-w, -d), (w, -d), (w, d), (-w, d)])


def face_shape(stamp):
    """Everything raised on the stamp face, as it should read in the imprint."""
    font_path = HERE / "fonts" / stamp["font"]
    text = text_shape(stamp["text"], font_path, stamp.get("rtl", True))
    layout = stamp.get("layout")
    if layout is None:
        w, d, margin = stamp["width_mm"], stamp["depth_mm"], stamp["margin_mm"]
        return fit_text(text, w - 2 * margin, d - 2 * margin)
    parts = [fit_box(text, *layout["text_box"])]
    motif = layout.get("motif")
    if motif:
        cx, cy, r = motif["center_r"]
        shape = MOTIFS[motif["type"]](r, **motif.get("options", {}))
        parts.append(affinity.translate(shape, cx, cy))
    border = stamp.get("border")
    if border:
        outer = outline_shape(stamp, border["inset_mm"])
        parts.append(outer.difference(outline_shape(stamp, border["inset_mm"] + border["width_mm"])))
    return unary_union(parts)


def to_cross_section(shape):
    polys = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
    rings = []
    for p in polys:
        rings.append(list(p.exterior.coords)[:-1])
        rings.extend(list(r.coords)[:-1] for r in p.interiors)
    return m3d.CrossSection(rings, m3d.FillRule.EvenOdd)


def build(stamp, out_dir):
    round_ = stamp.get("shape", "rect") == "round"
    if round_:
        w = d = stamp["diameter_mm"]
    else:
        w, d = stamp["width_mm"], stamp["depth_mm"]
    h = stamp["height_mm"]
    relief = stamp["relief_mm"]
    base_h = h - relief

    text = face_shape(stamp)
    # Mirror horizontally: viewed from above (looking at the stamp face) it reads
    # backwards; the imprint in clay reads correctly.
    text_mirrored = affinity.scale(text, -1, 1, origin=(0, 0))

    if round_:
        base = m3d.Manifold.cylinder(base_h, w / 2, w / 2, 128)
    else:
        base = m3d.Manifold.cube([w, d, base_h], center=False).translate([-w / 2, -d / 2, 0])
    relief_solid = m3d.Manifold.extrude(to_cross_section(text_mirrored), relief + 0.01)
    relief_solid = relief_solid.translate([0, 0, base_h - 0.01])
    solid = base + relief_solid

    # Engrave the stamp ID (readable, not mirrored) on the front wall (y = -d/2).
    id_cfg = stamp.get("id_label", {})
    id_h = id_cfg.get("height_mm", 5.0)
    id_depth = id_cfg.get("depth_mm", 0.6)
    id_font = HERE / "fonts" / id_cfg.get("font", "Rubik-Bold.ttf")
    label = fit_text(text_shape(stamp["id"], id_font, rtl=False), w - 4, id_h)
    wall_y = -d / 2
    if round_:
        # Curved wall: measure the depth from where the label's ends meet the wall.
        lw = label.bounds[2] - label.bounds[0]
        wall_y = -np.sqrt((w / 2) ** 2 - (lw / 2) ** 2)
    cut = m3d.Manifold.extrude(to_cross_section(label), id_depth + 0.5 + (wall_y + d / 2))
    # Extruded along +Z; rotate so it points into the wall (+Y), text upright.
    cut = cut.rotate([90, 0, 0]).translate([0, wall_y + id_depth, base_h / 2])
    solid = solid - cut

    mesh = solid.to_mesh()
    tm = trimesh.Trimesh(vertices=mesh.vert_properties[:, :3], faces=mesh.tri_verts)
    assert tm.is_watertight, f"stamp {stamp['id']} mesh is not watertight"

    stem = f"{stamp['id']}_{stamp['slug']}"
    stl_path = out_dir / f"{stem}.stl"
    tm.export(stl_path)
    label_on_wall = affinity.translate(label, 0, base_h / 2)
    render_preview(stamp, text_mirrored, text, label_on_wall, base_h,
                   out_dir / f"{stem}_preview.png")
    return stl_path, tm


def _fill(ax, shape, **kw):
    polys = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
    for p in polys:
        verts = list(p.exterior.coords)
        codes = [1] + [2] * (len(verts) - 1)
        for r in p.interiors:
            rv = list(r.coords)
            verts += rv
            codes += [1] + [2] * (len(rv) - 1)
        ax.add_patch(matplotlib.patches.PathPatch(matplotlib.path.Path(verts, codes), **kw))


def render_preview(stamp, face, imprint, label, base_h, path):
    round_ = stamp.get("shape", "rect") == "round"
    if round_:
        w = d = stamp["diameter_mm"]
    else:
        w, d = stamp["width_mm"], stamp["depth_mm"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6 if w > 1.4 * d else 5))
    h = stamp["height_mm"]
    panels = [
        (axes[0], face, "Stamp face (mirrored, top view)", (-d / 2, d), "#d9d9d9", "#333333"),
        (axes[1], imprint, "Imprint in clay", (-d / 2, d), "#c98b5e", "#7a4a2a"),
        (axes[2], label, "Front side wall (ID engraving)", (0, base_h), "#8fb3d9", "#3d5f85"),
    ]
    for ax, shape, title, (y0, height), bg, fg in panels:
        if round_ and ax is not axes[2]:
            ax.add_patch(matplotlib.patches.Circle((0, 0), w / 2, color=bg))
        else:
            ax.add_patch(matplotlib.patches.Rectangle((-w / 2, y0), w, height, color=bg))
        _fill(ax, shape, color=fg, lw=0)
        ax.set_xlim(-w / 2 - 1, w / 2 + 1)
        ax.set_ylim(y0 - 1, y0 + height + 1)
        ax.set_aspect("equal")
        ax.set_title(title)
        ax.set_xlabel("mm")
    # Relief on top of the side wall, for scale.
    axes[2].add_patch(matplotlib.patches.Rectangle((-w / 2, base_h), w, h - base_h, color="#333333"))
    axes[2].set_ylim(-1, h + 1)
    fig.suptitle(f"Stamp {stamp['id']} - {stamp['text']} ({stamp['font']})")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main():
    catalog = json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))
    wanted = set(sys.argv[1:])
    out_dir = HERE / "stl"
    out_dir.mkdir(exist_ok=True)
    for stamp in catalog["stamps"]:
        if wanted and stamp["id"] not in wanted:
            continue
        stl_path, tm = build(stamp, out_dir)
        ext = tm.extents
        print(f"{stamp['id']}: {stl_path.relative_to(HERE)}  "
              f"{ext[0]:.2f} x {ext[1]:.2f} x {ext[2]:.2f} mm, {len(tm.faces)} faces")


if __name__ == "__main__":
    main()
