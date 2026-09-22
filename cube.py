#!/usr/bin/env python3
"""
Python port of the classic "spinning ASCII cube" C program.

Three cubes (edge widths 20, 10 and 5) tumble in front of the camera.
Every face is drawn with its own character:

        @   $   ~   #   ;   +

A z-buffer makes sure that nearer surfaces hide the ones behind them.

Press Ctrl+C to stop.
"""

import math
import sys
import time

# ----------------------------------------------------------------------
# Scene constants -- identical to the C original
# ----------------------------------------------------------------------
WIDTH = 160
HEIGHT = 44
DISTANCE_FROM_CAM = 100.0
K1 = 40.0
INCREMENT_SPEED = 0.6
BACKGROUND = ord('.')

FRAME_DELAY = 0.016            # usleep(8000 * 2)  ->  16 ms

A_STEP, B_STEP, C_STEP = 0.05, 0.05, 0.01   # rotation speed per frame

# ----------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------
# Each of the six cube faces is described by three vectors (i, j, k).
# A point on the surface is
#       P = i*cubeX + j*cubeY + k*cubeWidth
# where every vector is (coef of cubeX, coef of cubeY, coef of cubeWidth).
SURFACES = (
    ((1, 0, 0), (0, 1, 0), (0, 0, -1), ord('@')),
    ((0, 0, 1), (0, 1, 0), (1, 0, 0), ord('$')),
    ((0, 0, -1), (0, 1, 0), (-1, 0, 0), ord('~')),
    ((-1, 0, 0), (0, 1, 0), (0, 0, 1), ord('#')),
    ((1, 0, 0), (0, 0, -1), (0, -1, 0), ord(';')),
    ((1, 0, 0), (0, 0, 1), (0, 1, 0), ord('+')),
)

# (cubeWidth, horizontalOffset) -- the three cubes of the C program
CUBES = (
    (20.0, -2.0 * 20.0),
    (10.0,  1.0 * 10.0),
    (5.0,   8.0 * 5.0),
)


def make_coords(cube_width):
    """Reproduce the C loop:  for (v = -w; v < w; v += 0.6)."""
    values = []
    v = -cube_width
    while v < cube_width:
        values.append(v)
        v += INCREMENT_SPEED
    return values


# The sample points of every cube never change -> pre-compute them once.
CUBE_DATA = [(w, off, make_coords(w)) for w, off in CUBES]


# ----------------------------------------------------------------------
# Render one frame
# ----------------------------------------------------------------------
def render(A, B, C):
    """Return the complete frame as a string (including the leading '\\n')."""
    sA, cA = math.sin(A), math.cos(A)
    sB, cB = math.sin(B), math.cos(B)
    sC, cC = math.sin(C), math.cos(C)

    # ------------------------------------------------------------------
    # Rotation coefficients:
    #     x = i*xi + j*xj + k*xk        (same idea for y and z)
    # ------------------------------------------------------------------
    xi = cB * cC
    xj = sA * sB * cC + cA * sC
    xk = sA * sC - cA * sB * cC

    yi = -cB * sC
    yj = cA * cC - sA * sB * sC
    yk = sA * cC + cA * sB * sC

    zi = sB
    zj = -sA * cB
    zk = cA * cB

    # ------------------------------------------------------------------
    # Collapse every face into
    #     x = px*cubeX + qx*cubeY + rx*cubeWidth
    # (and the same for y and z).  These 9 numbers per face are all we
    # need inside the hot loop.
    # ------------------------------------------------------------------
    face_data = []
    for I, J, K, ch in SURFACES:
        face_data.append((
            I[0] * xi + J[0] * xj + K[0] * xk,   # px
            I[1] * xi + J[1] * xj + K[1] * xk,   # qx
            I[2] * xi + J[2] * xj + K[2] * xk,   # rx
            I[0] * yi + J[0] * yj + K[0] * yk,   # py
            I[1] * yi + J[1] * yj + K[1] * yk,   # qy
            I[2] * yi + J[2] * yj + K[2] * yk,   # ry
            I[0] * zi + J[0] * zj + K[0] * zk,   # pz
            I[1] * zi + J[1] * zj + K[1] * zk,   # qz
            I[2] * zi + J[2] * zj + K[2] * zk,   # rz
            ch,
        ))

    size = WIDTH * HEIGHT
    z_buffer = [0.0] * size
    buffer = bytearray(b'.' * size)

    half_w = WIDTH * 0.5
    half_h = HEIGHT * 0.5
    k1_2 = K1 * 2.0

    # ------------------------------------------------------------------
    # Rasterise every cube
    # ------------------------------------------------------------------
    for cube_width, h_offset, coords in CUBE_DATA:
        for px, qx, rx0, py, qy, ry0, pz, qz, rz0, ch in face_data:
            # width-dependent parts (constant for this cube + face)
            rx = rx0 * cube_width
            ry = ry0 * cube_width
            rz = rz0 * cube_width + DISTANCE_FROM_CAM

            for cube_x in coords:
                # parts that only depend on cubeX
                bx = px * cube_x + rx
                by = py * cube_x + ry
                bz = pz * cube_x + rz

                for cube_y in coords:
                    x = bx + qx * cube_y
                    y = by + qy * cube_y
                    z = bz + qz * cube_y

                    ooz = 1.0 / z

                    xp = int(half_w + h_offset + k1_2 * ooz * x)
                    yp = int(half_h + K1 * ooz * y)

                    idx = xp + yp * WIDTH
                    if 0 <= idx < size and ooz > z_buffer[idx]:
                        z_buffer[idx] = ooz
                        buffer[idx] = ch

    # ------------------------------------------------------------------
    # Turn the pixel buffer into text.
    # NOTE: the C program prints '\n' instead of the very first character
    # of every row, so each output row is WIDTH-1 characters wide.
    # That quirk is reproduced here on purpose.
    # ------------------------------------------------------------------
    rows = []
    for y in range(HEIGHT):
        start = y * WIDTH
        rows.append(buffer[start + 1:start + WIDTH].decode())
    return '\n' + '\n'.join(rows)


# ----------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------
def main():
    out = sys.stdout
    out.write('\x1b[2J\x1b[?25l')      # clear screen + hide cursor
    out.flush()

    A = B = C = 0.0
    try:
        while True:
            out.write('\x1b[H')        # cursor home
            out.write(render(A, B, C))
            out.flush()

            A += A_STEP
            B += B_STEP
            C += C_STEP
            time.sleep(FRAME_DELAY)
    except KeyboardInterrupt:
        pass
    finally:
        out.write('\x1b[?25h\n')       # show cursor again
        out.flush()


if __name__ == '__main__':
    main()

