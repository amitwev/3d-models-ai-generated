#!/usr/bin/env python3
"""Generate numbered clay stamps (STL) from stamps/catalog.json.

Each stamp is a solid block with the text raised on its top face, mirrored,
so that pressing it into clay leaves a readable imprint. The stamp ID
(e.g. "001") is engraved, not mirrored, on one long side wall so a printed
stamp can always be matched back to its catalog entry.

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


def to_cross_section(shape):
    polys = list(shape.geoms) if isinstance(shape, MultiPolygon) else [shape]
    rings = []
    for p in polys:
        rings.append(list(p.exterior.coords)[:-1])
        rings.extend(list(r.coords)[:-1] for r in p.interiors)
    return m3d.CrossSection(rings, m3d.FillRule.EvenOdd)


def build(stamp, out_dir):
    w, d, h = stamp["width_mm"], stamp["depth_mm"], stamp["height_mm"]
    relief = stamp["relief_mm"]
    margin = stamp["margin_mm"]
    base_h = h - relief

    font_path = HERE / "fonts" / stamp["font"]
    text = fit_text(text_shape(stamp["text"], font_path, stamp.get("rtl", True)),
                    w - 2 * margin, d - 2 * margin)
    # Mirror horizontally: viewed from above (looking at the stamp face) it reads
    # backwards; the imprint in clay reads correctly.
    text_mirrored = affinity.scale(text, -1, 1, origin=(0, 0))

    base = m3d.Manifold.cube([w, d, base_h], center=False).translate([-w / 2, -d / 2, 0])
    relief_solid = m3d.Manifold.extrude(to_cross_section(text_mirrored), relief + 0.01)
    relief_solid = relief_solid.translate([0, 0, base_h - 0.01])
    solid = base + relief_solid

    # Engrave the stamp ID (readable, not mirrored) on the front long wall (y = -d/2).
    id_cfg = stamp.get("id_label", {})
    id_h = id_cfg.get("height_mm", 5.0)
    id_depth = id_cfg.get("depth_mm", 0.6)
    id_font = HERE / "fonts" / id_cfg.get("font", "Rubik-Bold.ttf")
    label = fit_text(text_shape(stamp["id"], id_font, rtl=False), w - 4, id_h)
    cut = m3d.Manifold.extrude(to_cross_section(label), id_depth + 0.5)
    # Extruded along +Z; rotate so it points into the wall (+Y), text upright.
    cut = cut.rotate([90, 0, 0]).translate([0, -d / 2 + id_depth, base_h / 2])
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
    w, d = stamp["width_mm"], stamp["depth_mm"]
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    h = stamp["height_mm"]
    panels = [
        (axes[0], face, "Stamp face (mirrored, top view)", (-d / 2, d), "#d9d9d9", "#333333"),
        (axes[1], imprint, "Imprint in clay", (-d / 2, d), "#c98b5e", "#7a4a2a"),
        (axes[2], label, "Front side wall (ID engraving)", (0, base_h), "#8fb3d9", "#3d5f85"),
    ]
    for ax, shape, title, (y0, height), bg, fg in panels:
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
