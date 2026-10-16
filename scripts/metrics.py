"""Numerical operations; no Illustrator private-format parsing."""
import math

PT_PER_MM = 72 / 25.4


def effective_ppi(pixels, transform):
    """Matrix maps unit image square to page points. Includes rotation/shear.

    Axis PPI plus worst principal direction PPI (singular value) are returned.
    """
    w, h = pixels
    a, b, c, d = transform[:4]
    if min(w, h) <= 0:
        raise ValueError("Invalid pixel dimensions")
    x, y = math.hypot(a, b), math.hypot(c, d)
    if min(x, y) <= 0 or abs(a*d-b*c) < 1e-12:
        raise ValueError("Degenerate image transform")
    u, v, z = (a*a+b*b)/w**2, (c*c+d*d)/h**2, (a*c+b*d)/(w*h)
    largest = (u+v+math.sqrt((u-v)**2+4*z*z))/2
    return {"x": 72*w/x, "y": 72*h/y, "minimum": 72/math.sqrt(largest)}


def tac(cmyk):
    if len(cmyk) != 4 or any(not 0 <= x <= 100 for x in cmyk):
        raise ValueError("CMYK channels must be 0..100")
    return sum(cmyk)


def raster_tac(image, limit):
    """Decoded, non-inverted CMYK samples only; not rendered separations."""
    import numpy as np
    if image.mode != "CMYK":
        raise ValueError("Native CMYK required; RGB conversion is not TAC evidence")
    values = np.asarray(image, dtype=np.float64).sum(axis=2)*100/255
    return {"maximum": float(values.max()), "average": float(values.mean()),
            "over_limit_percent": float((values > limit).mean()*100),
            "basis": "decoded original CMYK samples, includes cropped/masked pixels"}


def linear_channel(v):
    return v/12.92 if v <= 0.04045 else ((v+0.055)/1.055)**2.4


def contrast(fg, bg):
    def lum(rgb):
        return sum(linear_channel(v)*k for v, k in zip(rgb, [0.2126, 0.7152, 0.0722]))
    a, b = sorted([lum(fg), lum(bg)])
    return (b+0.05)/(a+0.05)


def simulate(rgb, kind, severity=100):
    import numpy as np
    from colorspacious.cvd import machado_et_al_2009_matrix
    x = np.asarray(rgb, dtype=float)
    lin = np.where(x <= .04045, x/12.92, ((x+.055)/1.055)**2.4)
    out = lin @ machado_et_al_2009_matrix(kind, severity).T
    # Clamp before fractional exponent to avoid invalid-value warnings.
    out = np.clip(out, 0, 1)
    return np.where(out <= .0031308, 12.92*out, 1.055*out**(1/2.4)-.055)


def delta_e76(a, b):
    import numpy as np
    from colorspacious import cspace_convert
    return float(np.linalg.norm(cspace_convert(a, "sRGB1", "CIELab") -
                                cspace_convert(b, "sRGB1", "CIELab")))
