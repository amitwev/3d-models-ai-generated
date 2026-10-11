#!/usr/bin/env python3
"""Generate the home-office MagSafe stand (STL): same 45 degree stand as the car
version, with a folded 3-in-1 MagSafe charger hidden inside.

The folded charger slides in from the top/back end of the sloped face and
stops against the bottom of its pocket. A continuous 0.6 mm skin covers the
magnetic puck, so from the front the face is plain plastic; the phone snaps
to it through the skin and charges. The USB-C port faces the opening, so the
cable leaves from the back and the charger is pulled out by its 5 mm lip.

Local frame (as in generate_holder.py): u runs up the face from the phone's
bottom edge, n points out of the face towards the phone, y runs across.

Usage:
    python3 phone-holder/generate_desk_stand.py

Requires: pip install manifold3d trimesh numpy matplotlib
"""

import math
from pathlib import Path

import manifold3d as m3d
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from generate_holder import cs, oriented, rect, to_trimesh, report

HERE = Path(__file__).resolve().parent
ANGLE = 45

# --- Folded charger (measured by the owner) ---------------------------------
CHG_ACROSS = 86.0      # along the cable edge, including the two rubber hinges
CHG_ALONG = 75.0       # cable edge to the opposite edge
CHG_T = 32.0           # total thickness including the puck
PUCK_D = 54.0
PUCK_H = 2.5           # puck above the charger's top square (re-measured: under 3 mm)
PLUG = (11.0, 6.0, 17.0)  # USB-C plug boot: width, thickness, length
PLUG_N = 4.5           # plug centre below the square's top face (estimate)

# --- Phone (iPhone 17 Air, no case) -----------------------------------------
PHONE_L, PHONE_W, PHONE_T = 156.0, 74.7, 7.0
CHG_FROM_BOTTOM = 41.0  # phone bottom edge to the charger's lower edge

# --- Stand ------------------------------------------------------------------
SKIN = 0.6             # plastic between puck and phone
CLEAR_T = 1.0          # thickness clearance (charger rests on the back wall)
CLEAR_W = 1.0          # width clearance
CLEAR_U = 0.5          # clearance at the bottom stop
LIP_OUT = 5.0          # charger sticks out of the opening by this much
WALL = 3.0             # side and back walls around the pocket
W = CHG_ACROSS + CLEAR_W + 2 * WALL   # 93
D = 169.0
CORNER_R = 4.0
BASE_T = 3.0
LEDGE_T = 4.0
SLOT_T = PHONE_T + 0.5
LIP_T, LIP_H, LIP_W = 3.0, 8.0, 14.0
P0 = (13.0, 10.0)      # phone's back-bottom corner (x, z)

U0 = CHG_FROM_BOTTOM - CLEAR_U              # pocket bottom stop
U_TOP = CHG_FROM_BOTTOM + CHG_ALONG - LIP_OUT  # end of the face / opening
N_PUCK = -SKIN                               # pocket ceiling over the puck
CHANNEL_H = 3.0        # puck channel height under the skin (owner: 3 mm, not ~5)
N_SQUARE = N_PUCK - CHANNEL_H               # ceiling over the square
N_BACK = N_PUCK - CHG_T - CLEAR_T            # pocket back wall
POCKET_W = CHG_ACROSS + CLEAR_W
CHANNEL_W = PUCK_D + 3.0  # 1.5 mm each side: 1 mm was too tight in the test print

TEST_L = 10.0          # pocket fit-test frame length


def frame():
    a = math.radians(ANGLE)
    c, s = math.cos(a), math.sin(a)
    p0 = np.array(P0)
    P = lambda u, n: p0 + u * np.array([c, s]) + n * np.array([-s, c])  # noqa: E731
    # Local (u, y, n) -> world (x, y, z).
    M = [[c, 0, -s, P0[0]], [0, 1, 0, 0], [s, 0, c, P0[1]]]
    return P, M


def local_box(M, u0, u1, y0, y1, n0, n1):
    return m3d.Manifold.cube([u1 - u0, y1 - y0, n1 - n0]).translate([u0, y0, n0]).transform(M)


def side_extrude(section, y0, y1):
    solid = m3d.Manifold.extrude(section.simplify(1e-3), y1 - y0)
    return solid.rotate([90, 0, 0]).translate([0, y1, 0])


def base_plate(t):
    return m3d.Manifold.extrude(
        m3d.CrossSection.square([D - 2 * CORNER_R, W - 2 * CORNER_R])
        .translate([CORNER_R, CORNER_R]).offset(CORNER_R, m3d.JoinType.Round, circular_segments=48), t)


def profile(P):
    """Side profile: ledge, sloped face, open end, back drop to the base."""
    b = P(U_TOP, N_BACK - WALL)
    return cs(oriented([
        (P(-LEDGE_T, SLOT_T + LIP_T)[0], 0), (b[0], 0), b, P(U_TOP, 0),
        P(0, 0), P(0, SLOT_T + LIP_T), P(-LEDGE_T, SLOT_T + LIP_T),
    ]))


def pocket(M):
    """Charger pocket + puck channel, open through the top end of the face."""
    yc = W / 2
    body = local_box(M, U0, U_TOP + 5, yc - POCKET_W / 2, yc + POCKET_W / 2, N_BACK, N_SQUARE)
    u_puck_low = CHG_FROM_BOTTOM + CHG_ALONG / 2 - PUCK_D / 2 - 1
    channel = local_box(M, u_puck_low, U_TOP + 5, yc - CHANNEL_W / 2, yc + CHANNEL_W / 2,
                        N_SQUARE - 0.1, N_PUCK)
    return body + channel


def build_stand():
    P, M = frame()
    prof = profile(P)
    lip = cs(oriented([P(-LEDGE_T, SLOT_T), P(LIP_H, SLOT_T), P(LIP_H, SLOT_T + LIP_T),
                       P(-LEDGE_T, SLOT_T + LIP_T)]))
    lip_y = W / 2 - PHONE_W / 2 + LIP_W
    solid = base_plate(BASE_T) + side_extrude(prof, 0, W)
    solid += side_extrude(lip, 0, lip_y) + side_extrude(lip, W - lip_y, W)
    return solid - pocket(M)


def charger(M, shift=0.0):
    """Folded charger resting on the back wall, slid `shift` mm out along u."""
    yc = W / 2
    u0 = CHG_FROM_BOTTOM + shift
    n_bot = N_BACK
    n_sq = n_bot + CHG_T - PUCK_H
    body = local_box(M, u0, u0 + CHG_ALONG, yc - CHG_ACROSS / 2, yc + CHG_ACROSS / 2, n_bot, n_sq)
    puck = (m3d.Manifold.cylinder(PUCK_H, PUCK_D / 2, PUCK_D / 2, 96)
            .translate([u0 + CHG_ALONG / 2, yc, n_sq]).transform(M))
    pw, pt, pl = PLUG
    plug = local_box(M, u0 + CHG_ALONG, u0 + CHG_ALONG + pl, yc - pw / 2, yc + pw / 2,
                     n_sq - PLUG_N - pt / 2, n_sq - PLUG_N + pt / 2)
    return body + puck + plug


def check_fit(stand):
    """Charger, plug and phone clear the stand; the charger slides out freely."""
    P, M = frame()
    hit = (stand ^ charger(M)).volume()
    assert hit < 0.01, f"charger hits the stand ({hit:.2f} mm3)"
    for shift in np.arange(0, CHG_ALONG + 1, 2.5):
        hit = (stand ^ charger(M, shift)).volume()
        assert hit < 0.01, f"charger jams {shift:.1f} mm out of the pocket"
    phone = local_box(M, 0.05, PHONE_L, W / 2 - PHONE_W / 2, W / 2 + PHONE_W / 2, 0.05, PHONE_T)
    assert (stand ^ phone).volume() < 0.01, "phone hits the stand"
    # Gravity rests the charger on the back wall: puck top to phone back.
    gap = -(N_BACK + CHG_T)
    puck_u = CHG_FROM_BOTTOM + CHG_ALONG / 2
    return gap, puck_u


def build_test_frame():
    """Short slice of the pocket cross-section, printed flat, to test-slide the charger."""
    outer_n = -N_BACK + WALL
    yc = W / 2
    shape = m3d.CrossSection.square([W, outer_n])
    body = m3d.CrossSection.square([POCKET_W, N_SQUARE - N_BACK]).translate([yc - POCKET_W / 2, WALL])
    channel = m3d.CrossSection.square([CHANNEL_W, N_PUCK - N_SQUARE + 0.1]).translate(
        [yc - CHANNEL_W / 2, WALL + N_SQUARE - N_BACK - 0.1])
    return m3d.Manifold.extrude(shape - body - channel, TEST_L)


def render_preview(tm, gap, puck_u, path):
    P, M = frame()
    fig = plt.figure(figsize=(13, 5.8))
    ax = fig.add_subplot(1, 2, 1)
    prof = profile(P)
    for ring in prof.to_polygons():
        ax.fill(*np.vstack([ring, ring[:1]]).T, color="#4a6fa5")
    ax.fill(*np.array([(0, 0), (D, 0), (D, BASE_T), (0, BASE_T)]).T, color="#4a6fa5")
    pk = cs(oriented([P(U0, N_BACK), P(U_TOP + 5, N_BACK), P(U_TOP + 5, N_PUCK), P(U0, N_PUCK)])) ^ prof
    for i, ring in enumerate(pk.to_polygons()):
        ax.fill(*np.vstack([ring, ring[:1]]).T, color="#ffffff", label="charger pocket" if i == 0 else None)
    u0, n_sq = CHG_FROM_BOTTOM, N_BACK + CHG_T - PUCK_H
    box = np.array([P(u0, N_BACK), P(u0 + CHG_ALONG, N_BACK), P(u0 + CHG_ALONG, n_sq), P(u0, n_sq)])
    ax.fill(*box.T, color="#bbbbbb", label="folded charger")
    puck = np.array([P(puck_u - PUCK_D / 2, n_sq), P(puck_u + PUCK_D / 2, n_sq),
                     P(puck_u + PUCK_D / 2, n_sq + PUCK_H), P(puck_u - PUCK_D / 2, n_sq + PUCK_H)])
    ax.fill(*puck.T, color="#9aa7b5", label=f"puck (hidden, {gap:.1f} mm below the face)")
    pw, pt, pl = PLUG
    plug = np.array([P(u0 + CHG_ALONG, n_sq - PLUG_N - pt / 2), P(u0 + CHG_ALONG + pl, n_sq - PLUG_N - pt / 2),
                     P(u0 + CHG_ALONG + pl, n_sq - PLUG_N + pt / 2), P(u0 + CHG_ALONG, n_sq - PLUG_N + pt / 2)])
    ax.fill(*plug.T, color="#e07b39", label="USB-C plug")
    ph = np.array([P(0, 0), P(PHONE_L, 0), P(PHONE_L, PHONE_T), P(0, PHONE_T)])
    ax.fill(*ph.T, color="#cccccc", alpha=0.7, label="iPhone 17 Air")
    ax.set_xlim(-5, D + 5)
    ax.set_ylim(-5, P(PHONE_L, PHONE_T)[1] + 10)
    ax.set_aspect("equal")
    ax.set_xlabel("depth (mm)")
    ax.set_ylabel("height (mm)")
    ax.set_title(f"Side section through the centre, {ANGLE}°")
    ax.legend(loc="upper left", fontsize=8)

    ax3 = fig.add_subplot(1, 2, 2, projection="3d")
    import trimesh
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    verts, faces = trimesh.remesh.subdivide_to_size(tm.vertices, tm.faces, max_edge=3.0)
    view = trimesh.Trimesh(verts, faces, process=False)
    light = np.array([0.4, -0.6, 0.7]) / np.linalg.norm([0.4, -0.6, 0.7])
    shade = 0.35 + 0.65 * np.clip(view.face_normals @ light, 0, 1)
    ax3.add_collection3d(Poly3DCollection(view.vertices[view.faces], facecolors=np.outer(shade, [0.35, 0.5, 0.75]),
                                          edgecolor="none"))
    ax3.set_xlim(0, D)
    ax3.set_ylim(W / 2 - D / 2, W / 2 + D / 2)
    ax3.set_zlim(0, D)
    ax3.view_init(elev=25, azim=40)
    ax3.set_box_aspect((1, 1, 1))
    ax3.set_title("From the back: charger opening")
    ax3.set_axis_off()
    fig.suptitle(f"Desk MagSafe stand - {ANGLE}° - {W:.0f} x {D:.0f} mm footprint")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    out_dir = HERE / "stl"
    out_dir.mkdir(exist_ok=True)

    tm = to_trimesh(build_test_frame(), "pocket test frame")
    path = out_dir / "desk_pocket_fit_test.stl"
    tm.export(path)
    report(path, tm)

    stand = build_stand()
    gap, puck_u = check_fit(stand)
    tm = to_trimesh(stand, "desk stand")
    path = out_dir / f"desk_magsafe_stand_{ANGLE}deg.stl"
    tm.export(path)
    render_preview(tm, gap, puck_u, out_dir / f"desk_magsafe_stand_{ANGLE}deg_preview.png")
    report(path, tm)
    print(f"   fit check OK: charger slides out freely; puck {gap:.1f} mm below the face, "
          f"centred {puck_u:.1f} mm above the phone's bottom edge")


if __name__ == "__main__":
    main()
