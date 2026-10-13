#!/usr/bin/env python3
"""Generate the BYD Seal U DM-i phone stand (STL) for the left wireless-charging bay.

The stand drops into the left charging bay of the centre console (inside the
small rubber tabs: 85 x 170 mm) and is held by the tabs alone - no adhesive,
no vent clip. The phone stands in portrait, bottom edge towards the gear
selector, leaning back at `angle` degrees from the bay floor, screen facing
the driver. A Lightning plug stands fixed in a pocket in the bottom ledge, tip
up along the phone axis, so the phone plugs itself in as it is lowered into
the stand (a dock); the cable is clamped in a groove and leaves through the
front of the stand.

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

# --- Phone (iPhone 14 Pro with case; the cradle also takes a Galaxy S24/S25) -
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
SUPPORT_L = GUIDE_L + 5  # back plate ends 5 mm past the side guides, so the
                         # stand stays under the vent frame
LEDGE_T = 4.0
SLOT_T = PHONE_T + 0.5  # gap between back plate and front lip
LIP_T = 4.5
LIP_H = 16.0           # lip height along the phone (holds the phone, whose
                       # centre of gravity sits past the short back plate)
LIP_W = 14.0           # lips only at the two corners, screen stays clear
RIB_T = 3.0
P0 = (35.0, 21.0)      # back-bottom corner of the phone (x, z): high enough
                       # that a 28 mm plug boot clears the bay floor at 45 deg

# --- Lightning dock (iPhone 14 Pro with case) -------------------------------
# The plug boot sits in a pocket in the ledge with its tip pointing up the
# phone axis. The phone leans on the back plate under its own weight, so the
# plug only has to sit at the port's distance from the case back; sideways
# the plug itself centres the phone (the guides leave +-1 mm). Lifting the
# phone off leaves the plug in place: the cable is snapped into a pinch below
# the pocket that keeps the boot from being pulled out.
DOCK_PORT_N = 5.5      # port centre above the case back: 3.9 (half of the
                       # 7.85 mm phone) + ~1.6 case back - measure your case
DOCK_BOOT = (8.0, 5.3, 12.0)   # plug boot width, thickness, rigid length
                               # (Apple cable; measure third-party ones)
DOCK_TIP_L = 6.7       # metal tip length
DOCK_RISE = 0.5        # boot top above the ledge: reaches into the case's
                       # port opening so the tip goes in deeper
DOCK_FIT = 0.15        # pocket clearance per side: snug push fit
DOCK_RELIEF_W = 4.6    # groove for the boot's strain relief
DOCK_RELIEF_L = 9.0
DOCK_CABLE_D = 3.0     # cable diameter at the pinch
DOCK_PINCH_L = 6.0
DOCK_WALL = 2.5
DOCK_BLOCK_W = 16.0    # dock block width across the stand
DOCK_DEPTH = DOCK_BOOT[2] - DOCK_RISE
DOCK_PINCH_C = -DOCK_DEPTH - DOCK_RELIEF_L   # pinch: c from here down by DOCK_PINCH_L
DOCK_L = DOCK_DEPTH + DOCK_RELIEF_L + DOCK_PINCH_L + DOCK_WALL
DOCK_TOP_N = DOCK_PORT_N + DOCK_BOOT[1] / 2 + DOCK_FIT + DOCK_WALL
DOCK_CASE_BOTTOM = 1.5  # typical case thickness under the phone (for the report)

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
    # The base starts at the front block: no tabs in front of it.
    solid = base_plate(BASE_T) ^ m3d.Manifold.cube([D, W, BASE_T + 2]).translate([x_front, 0, -1])
    for y0, y1, prof in zip(cuts, cuts[1:], profiles):
        solid += side_extrude(prof, y0, y1)

    solid += side_extrude(dock_block(P), W / 2 - DOCK_BLOCK_W / 2, W / 2 + DOCK_BLOCK_W / 2)
    return solid - dock_cuts().transform(dock_frame(angle))


def dock_block(P):
    """Side profile of the solid around the plug pocket, down to the floor."""
    front = P(-DOCK_L, DOCK_TOP_N)
    return m3d.CrossSection.hull_points([
        P(0, DOCK_TOP_N), front, (front[0], 0), (P(-LEDGE_T, -PLATE_T)[0], 0),
        P(-LEDGE_T, -PLATE_T), P(0, -PLATE_T)])


def dock_frame(angle):
    """3x4 matrix from dock coordinates (a across the stand, b out of the
    screen, c along the phone axis; origin at P(0, 0) on the centre line)."""
    a = math.radians(angle)
    u = [math.cos(a), 0, math.sin(a)]
    n = [-math.sin(a), 0, math.cos(a)]
    return np.array([[0, n[0], u[0], P0[0]],
                     [1, n[1], u[1], W / 2],
                     [0, n[2], u[2], P0[1]]])


def along_c(section, c0, c1):
    """Extrude an (a, b) section along c in dock coordinates."""
    return m3d.Manifold.extrude(section.simplify(1e-3), c1 - c0).translate([0, 0, c0])


def dock_cuts():
    """Pocket, strain-relief groove and cable pinch, in dock coordinates.

    The groove is open towards the screen side, so the cable is pressed in
    from the front; at the pinch it snaps past a throat into a bore slightly
    smaller than the cable, which holds it.
    """
    bw, bt, _ = DOCK_BOOT
    nc, f = DOCK_PORT_N, DOCK_FIT
    pocket = rect(-bw / 2 - f, bw / 2 + f, nc - bt / 2 - f, nc + bt / 2 + f)
    r = DOCK_RELIEF_W / 2
    groove = m3d.CrossSection.circle(r, 40).translate([0, nc]) + rect(-r, r, nc, nc + 60)
    rb, rt = (DOCK_CABLE_D - 0.2) / 2, (DOCK_CABLE_D - 0.6) / 2
    top = DOCK_TOP_N
    funnel = cs(oriented([(-rt, top - 1.6), (rt, top - 1.6), (rt + 2, top + 0.4), (-rt - 2, top + 0.4)]))
    pinch = m3d.CrossSection.circle(rb, 40).translate([0, nc]) + rect(-rt, rt, nc, nc + 60) + funnel
    c1, c2 = -DOCK_DEPTH, DOCK_PINCH_C
    c3 = c2 - DOCK_PINCH_L
    return (along_c(pocket, c1, 5) + along_c(groove, c2 - 0.01, c1 + 0.01)
            + along_c(pinch, c3, c2) + along_c(groove, c3 - 80, c3 + 0.01))


def check_dock(angle, stand):
    """Assert the phone clears the stand and the plug sits in its pocket.

    Checked: the boot fits the pocket and rests on its floor, the tip and the
    cable run free, the pinch grips the cable, the pocket walls are at least
    1.5 mm thick. Returns how far the tip sticks out above the ledge.
    """
    P = frame(angle)
    T = dock_frame(angle)
    phone = side_extrude(quad(P, 0.05, PHONE_L, 0.05, PHONE_T - 1),
                         W / 2 - PHONE_W / 2 - 1, W / 2 + PHONE_W / 2 - 1)
    assert (stand ^ phone).volume() < 0.01, f"{angle} deg: phone hits the stand"

    def part(a, b, c0, c1):
        sec = rect(-a / 2, a / 2, DOCK_PORT_N - b / 2, DOCK_PORT_N + b / 2)
        return along_c(sec, c0, c1).transform(T)

    def rod(d, c0, c1):
        sec = m3d.CrossSection.circle(d / 2, 40).translate([0, DOCK_PORT_N])
        return along_c(sec, c0, c1).transform(T)

    bw, bt, bl = DOCK_BOOT
    c_boot = DOCK_RISE - bl
    clear = {
        "plug boot": part(bw, bt, c_boot, DOCK_RISE),
        "plug tip": part(7.7, 1.5, DOCK_RISE, DOCK_RISE + DOCK_TIP_L),
        "strain relief": rod(DOCK_RELIEF_W - 0.4, DOCK_PINCH_C, c_boot),
        "cable": rod(DOCK_CABLE_D - 0.3, -100, c_boot),
    }
    for name, body in clear.items():
        assert (stand ^ body).volume() < 0.01, f"{angle} deg: {name} hits the stand"
    seat = part(bw, bt, c_boot - 0.5, c_boot)
    assert (stand ^ seat).volume() > 0.25 * seat.volume(), f"{angle} deg: boot has nothing to rest on"
    grip = rod(DOCK_CABLE_D, DOCK_PINCH_C - DOCK_PINCH_L, DOCK_PINCH_C)
    assert (stand ^ grip).volume() > 0.01, f"{angle} deg: pinch does not grip the cable"
    w = 1.5
    shell = (part(bw + 2 * (DOCK_FIT + w), bt + 2 * (DOCK_FIT + w), c_boot + 0.05, -0.01)
             - part(bw + 2 * DOCK_FIT, bt + 2 * DOCK_FIT, c_boot - 1, 1))
    assert (shell - stand).volume() < 0.01, f"{angle} deg: pocket wall thinner than {w} mm"
    return DOCK_RISE + DOCK_TIP_L


def build_dock_test():
    """The pocket, groove and pinch in a small upright block, to try the plug."""
    bt = DOCK_BOOT[1]
    b0 = DOCK_PORT_N - bt / 2 - DOCK_FIT - DOCK_WALL
    block = along_c(rect(-DOCK_BLOCK_W / 2, DOCK_BLOCK_W / 2, b0, DOCK_TOP_N), -DOCK_L, 0)
    return (block - dock_cuts()).translate([0, 0, DOCK_L])


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
    fig = plt.figure(figsize=(13, 5.8))

    # Side view: stand profile, phone, plug and the vent frame height.
    ax = fig.add_subplot(1, 2, 1)
    side = wedge(P) + quad(P, 0, GUIDE_L, -PLATE_T, GUIDE_H) + quad(
        P, -LEDGE_T, LIP_H, SLOT_T, SLOT_T + LIP_T) + rect(P(-LEDGE_T, SLOT_T + LIP_T)[0], D, 0, BASE_T)
    for ring in side.to_polygons():
        ax.fill(*np.vstack([ring, ring[:1]]).T, color="#4a6fa5")
    # The centre strip carries the dock block, cut by the pocket and cable groove.
    dock = dock_block(P) - quad(P, -DOCK_L - 40, -DOCK_DEPTH, DOCK_PORT_N - DOCK_RELIEF_W / 2, 60)
    for i, ring in enumerate(dock.to_polygons()):
        ax.fill(*np.vstack([ring, ring[:1]]).T, color="#2f4f7f",
                label=f"dock block ({DOCK_BLOCK_W:.0f} mm wide, centre)" if i == 0 else None)
    ph = phone_outline(P)
    ax.fill(ph[:, 0], ph[:, 1], color="#cccccc", alpha=0.7, label="phone with case")
    bw, bt, bl = DOCK_BOOT
    n_c = DOCK_PORT_N
    for (s0, s1, t), lab in [((DOCK_RISE - bl, DOCK_RISE, bt), "Lightning plug, fixed"),
                             ((DOCK_RISE, DOCK_RISE + DOCK_TIP_L, 1.5), None)]:
        ring = np.array([P(s0, n_c - t / 2), P(s1, n_c - t / 2), P(s1, n_c + t / 2), P(s0, n_c + t / 2)])
        ax.fill(ring[:, 0], ring[:, 1], color="#e07b39", label=lab)
    out = P(-DOCK_L - 4, n_c)
    cable = np.array([P(DOCK_RISE - bl, n_c), out, (out[0] - 8, 1.5), (-12, 1.5)])
    ax.plot(cable[:, 0], cable[:, 1], color="#e07b39", lw=3, alpha=0.6)
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

    fig.suptitle(f"BYD Seal U phone stand - {angle}° - {W:.1f} x {tm.extents[0]:.0f} mm footprint")
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

    for solid, name in [(build_test_plate(), "fit_test_plate"), (build_dock_test(), "dock_plug_fit_test")]:
        tm = to_trimesh(solid, name)
        path = out_dir / f"{name}.stl"
        tm.export(path)
        report(path, tm)

    for angle in VARIANTS:
        if wanted and angle not in wanted:
            continue
        stand = build_stand(angle)
        tip = check_dock(angle, stand)
        tm = to_trimesh(stand, f"stand {angle}")
        assert tm.bounds[1][2] < FRAME_CLEARANCE, f"{angle} deg: stand hits the vent frame"
        path = out_dir / f"seal_u_phone_stand_{angle}deg.stl"
        tm.export(path)
        render_preview(angle, tm, out_dir / f"seal_u_phone_stand_{angle}deg_preview.png")
        report(path, tm)
        print(f"   dock check OK: tip {tip:.1f} mm above the ledge, ~{tip - DOCK_CASE_BOTTOM:.1f} mm "
              f"into the phone with a {DOCK_CASE_BOTTOM} mm case bottom")


if __name__ == "__main__":
    main()
