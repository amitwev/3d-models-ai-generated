#!/usr/bin/env python3
"""Generate the BYD Seal U DM-i phone stand (STL) for the left wireless-charging bay.

The stand drops into the left charging bay of the centre console (inside the
small rubber tabs: 85 x 170 mm) and is held by the tabs alone - no adhesive,
no vent clip. The phone stands in portrait, bottom edge towards the gear
selector, leaning back at `angle` degrees from the bay floor, screen facing
the driver. A slot in the bottom ledge lets a straight USB-C plug pass down
into a tunnel that leads the cable out of the front of the stand.

Coordinates: x = depth into the bay (0 = front edge, towards the gear
selector), y = across the bay, z = up from the bay floor.

Usage:
    python3 phone-holder/generate_holder.py            # every variant
    python3 phone-holder/generate_holder.py 40         # only the 40 degree stand

Requires: pip install manifold3d trimesh numpy matplotlib
"""

import math
import sys
from pathlib import Path

import manifold3d as m3d
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = Path(__file__).resolve().parent

# --- Car (measured by the owner) --------------------------------------------
BAY_W = 85.0           # bay width between the rubber tabs
BAY_D = 170.0          # bay depth between the rubber tabs
FRAME_CLEARANCE = 70.0  # bay floor to the underside of the vent frame

# --- Phone (iPhone 14 Pro / Galaxy S24, S25 with case) ----------------------
PHONE_T = 12.0         # max thickness with case (owner measured 11)
PHONE_W = 76.0         # max width with case
PHONE_L = 152.0        # max length with case

# --- Stand ------------------------------------------------------------------
FIT = 0.25             # clearance per side against the rubber tabs
W = BAY_W - 2 * FIT    # 84.5
D = BAY_D - 1.0        # 169
CORNER_R = 4.0         # plan-view corner radius of the base
BASE_T = 3.0           # base plate thickness
PLATE_T = 4.0          # back plate under the phone
WALL_T = (W - 78.0) / 2  # side walls -> 78 mm between the phone guides
GUIDE_H = 4.0          # side guides above the back plate
GUIDE_L = 60.0         # guide length from the ledge (stays clear of buttons)
SUPPORT_L = 110.0      # back plate length along the phone
LEDGE_T = 4.0
SLOT_T = PHONE_T + 0.5  # gap between back plate and front lip
LIP_T = 3.0
LIP_H = 8.0            # lip height along the phone
LIP_W = 14.0           # lips only at the two corners, screen stays clear
RIB_T = 3.0
P0 = (35.0, 18.0)      # back-bottom corner of the phone (x, z)
# Cable path: slot through the ledge, then a tunnel out of the front.
CABLE_W = 15.0
CABLE_N = (1.5, 11.0)  # slot extent across the phone thickness
CABLE_LEN = 45.0       # along the phone axis, below the ledge
TUNNEL_H = 12.0

TEST_T = 2.0           # fit-test plate thickness
VARIANTS = [35, 40, 45]


def frame(angle):
    a = math.radians(angle)
    u = np.array([math.cos(a), math.sin(a)])    # along the phone, upwards
    n = np.array([-math.sin(a), math.cos(a)])   # out of the screen
    p0 = np.array(P0)
    return lambda s, t: p0 + s * u + t * n


def cs(points):
    return m3d.CrossSection([np.asarray(points, dtype=float)], m3d.FillRule.Positive)


def oriented(points):
    """Counter-clockwise ring so the Positive fill rule keeps it."""
    pts = np.asarray(points, dtype=float)
    x, y = pts[:, 0], pts[:, 1]
    area = np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) / 2
    return pts if area > 0 else pts[::-1]


def quad(P, s0, s1, t0, t1):
    return cs(oriented([P(s0, t0), P(s1, t0), P(s1, t1), P(s0, t1)]))


def rect(x0, x1, z0, z1):
    return cs(oriented([(x0, z0), (x1, z0), (x1, z1), (x0, z1)]))


def side_extrude(section, y0, y1):
    """Extrude an (x, z) profile across y0..y1."""
    solid = m3d.Manifold.extrude(section.simplify(1e-3), y1 - y0)
    # Profile Y -> world z, extrusion Z -> world -y.
    return solid.rotate([90, 0, 0]).translate([0, y1, 0])


def wedge(P):
    """Side profile of the solid under the phone, floor to back plate."""
    e = P(SUPPORT_L, 0)
    return cs(oriented([
        (P(-LEDGE_T, SLOT_T + LIP_T)[0], 0), (e[0], 0), e,
        P(0, 0), P(0, SLOT_T + LIP_T), P(-LEDGE_T, SLOT_T + LIP_T),
    ]))


def base_plate(t):
    return m3d.Manifold.extrude(
        m3d.CrossSection.square([D - 2 * CORNER_R, W - 2 * CORNER_R])
        .translate([CORNER_R, CORNER_R]).offset(CORNER_R, m3d.JoinType.Round, circular_segments=48), t)


def build_stand(angle):
    P = frame(angle)
    wedge_cs = wedge(P)
    x_front = P(-LEDGE_T, SLOT_T + LIP_T)[0]
    x_ledge_back = P(-LEDGE_T, -PLATE_T)[0]
    x_rear = P(SUPPORT_L, 0)[0]

    full = (quad(P, 0, SUPPORT_L, -PLATE_T, 0)                       # back plate
            + quad(P, -LEDGE_T, 0, -PLATE_T, SLOT_T + LIP_T)         # ledge
            + (wedge_cs ^ rect(x_front - 1, x_ledge_back, -1, 300))  # front block
            + (wedge_cs ^ rect(x_rear - 4, x_rear + 1, -1, 300)))    # rear wall
    side = wedge_cs + quad(P, 0, GUIDE_L, -PLATE_T, GUIDE_H)
    lip = quad(P, -LEDGE_T, LIP_H, SLOT_T, SLOT_T + LIP_T)

    # One profile per slab across the width, so no faces coincide in 3D.
    cuts = [0, WALL_T, WALL_T + LIP_W, W / 2 - RIB_T / 2, W / 2 + RIB_T / 2,
            W - WALL_T - LIP_W, W - WALL_T, W]
    profiles = [full + side + lip, full + lip, full, full + wedge_cs, full, full + lip, full + side + lip]
    solid = base_plate(BASE_T)
    for y0, y1, prof in zip(cuts, cuts[1:], profiles):
        solid += side_extrude(prof, y0, y1)

    # Cable path: plug slot along the phone axis + tunnel out of the front.
    y0, y1 = W / 2 - CABLE_W / 2, W / 2 + CABLE_W / 2
    plug = quad(P, -CABLE_LEN, 2, *CABLE_N)
    tunnel = rect(-1, P(-CABLE_LEN, CABLE_N[1])[0] + CABLE_W, -1, TUNNEL_H)
    solid -= side_extrude(plug + tunnel, y0, y1)
    return solid


def build_test_plate():
    return base_plate(TEST_T)


def to_trimesh(solid, name):
    mesh = solid.to_mesh()
    # process=False: merging vertices would collapse the zero-area slivers that
    # manifold3d leaves where slabs meet, and break an otherwise closed mesh.
    tm = trimesh.Trimesh(vertices=mesh.vert_properties[:, :3], faces=mesh.tri_verts,
                         process=False)
    assert solid.status() == m3d.Error.NoError and tm.is_volume, f"{name} mesh is not a closed volume"
    return tm


def phone_outline(P):
    return np.array([P(0, 0), P(PHONE_L, 0), P(PHONE_L, PHONE_T), P(0, PHONE_T), P(0, 0)])


def render_preview(angle, tm, path):
    P = frame(angle)
    fig = plt.figure(figsize=(13, 5.2))

    # Side view: stand profile, phone, plug and the vent frame height.
    ax = fig.add_subplot(1, 2, 1)
    side = wedge(P) + quad(P, 0, GUIDE_L, -PLATE_T, GUIDE_H) + quad(
        P, -LEDGE_T, LIP_H, SLOT_T, SLOT_T + LIP_T) + rect(0, D, 0, BASE_T)
    for ring in side.to_polygons():
        ax.fill(*np.vstack([ring, ring[:1]]).T, color="#4a6fa5")
    ph = phone_outline(P)
    ax.fill(ph[:, 0], ph[:, 1], color="#cccccc", alpha=0.7, label="phone with case")
    plug = np.array([P(0, 6), P(-30, 6)])
    ax.plot(plug[:, 0], plug[:, 1], color="#e07b39", lw=4, label="USB-C plug")
    ax.axhline(FRAME_CLEARANCE, color="#999999", ls="--", lw=1)
    ax.text(2, FRAME_CLEARANCE + 2, f"vent frame underside ({FRAME_CLEARANCE:.0f} mm)", color="#666666")
    ax.axvline(BAY_D, color="#999999", ls=":", lw=1)
    ax.text(BAY_D - 2, 10, "bay back", ha="right", color="#666666", rotation=90)
    top = P(PHONE_L, PHONE_T)
    ax.set_xlim(-15, BAY_D + 10)
    ax.set_ylim(-5, max(140, top[1] + 10))
    ax.set_aspect("equal")
    ax.set_xlabel("depth into bay (mm)  <- gear selector")
    ax.set_ylabel("height above bay floor (mm)")
    ax.set_title(f"Side view, {angle}° - phone top ≈ {P(PHONE_L, 0)[1]:.0f} mm high")
    ax.legend(loc="upper left", bbox_to_anchor=(0, 0.92))

    # 3D view of the printed part.
    ax3 = fig.add_subplot(1, 2, 2, projection="3d")
    # Small triangles so matplotlib's per-face depth sort looks right.
    verts, faces = trimesh.remesh.subdivide_to_size(tm.vertices, tm.faces, max_edge=3.0)
    view = trimesh.Trimesh(verts, faces, process=False)
    tris = view.vertices[view.faces]
    light = np.array([0.4, -0.6, 0.7]) / np.linalg.norm([0.4, -0.6, 0.7])
    shade = 0.35 + 0.65 * np.clip(view.face_normals @ light, 0, 1)
    colors = np.outer(shade, [0.35, 0.5, 0.75])
    ax3.add_collection3d(Poly3DCollection(tris, facecolors=colors, edgecolor="none"))
    ax3.set_xlim(0, D)
    ax3.set_ylim(W / 2 - D / 2, W / 2 + D / 2)
    ax3.set_zlim(0, D)
    ax3.view_init(elev=30, azim=-140)
    ax3.set_box_aspect((1, 1, 1))
    ax3.set_title("Printed part (flat base on the bed)")
    ax3.set_axis_off()

    fig.suptitle(f"BYD Seal U phone stand - {angle}° - {W:.1f} x {D:.0f} mm footprint")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def report(path, tm):
    ext = tm.extents
    print(f"{path.relative_to(HERE)}: {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm, "
          f"{tm.volume / 1000:.0f} cm3, {len(tm.faces)} faces")


def main():
    wanted = {int(a) for a in sys.argv[1:]}
    out_dir = HERE / "stl"
    out_dir.mkdir(exist_ok=True)

    tm = to_trimesh(build_test_plate(), "fit test")
    path = out_dir / "fit_test_plate.stl"
    tm.export(path)
    report(path, tm)

    for angle in VARIANTS:
        if wanted and angle not in wanted:
            continue
        tm = to_trimesh(build_stand(angle), f"stand {angle}")
        path = out_dir / f"seal_u_phone_stand_{angle}deg.stl"
        tm.export(path)
        render_preview(angle, tm, out_dir / f"seal_u_phone_stand_{angle}deg_preview.png")
        report(path, tm)


if __name__ == "__main__":
    main()
