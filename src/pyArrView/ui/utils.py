import numpy as np

def martin_phase(N=64):
    # phase colormap as found in a tool from Martin Uecker (muecker@gwdg.de)

    phase = np.linspace(0, 2 * np.pi, N)

    c = np.zeros((N, 3))
    c[:, 0] = np.sin(phase)
    c[:, 1] = np.sin(phase + 120 * np.pi / 180)
    c[:, 2] = np.sin(phase + 240 * np.pi / 180)

    c = (c + 1) / 2

    return c

def complex2rgb(img, N=256, clim=None, incolormap=None):
    """
    Calculates the cdata from img and the colormap

    Parameters:
        img:            the image as 2D complex data
        N:              the number of colormap tones as scalar
        clim:           the magnitude color limits as 2 element vector
        incolormap:     the colormap as n-by-3 matrix

    Returns:
        rgb:            the rgb cdata m-by-n-by-3 matrix
        clim:           the colorlimits as 2 element vector
    """

    if incolormap is None:
        cmap = martin_phase(N)
    else:
        cmap = incolormap

    m = np.abs(img)   # magnitude
    p = np.angle(img) # phase

    # get minimum and maximum magnitude value
    mi = np.min(m)
    ma = np.max(m)

    # set the colorlimits
    if clim is None:
        clim = [mi, ma]

    if round(mi * 1e12) == round(ma * 1e12) and ma != 0:
        # set magnitude value to 1 to show a pure phase map
        m = np.ones_like(m)
    else:
        # scale magnitude image to 0..1
        m[m < clim[0]] = clim[0]
        m = (m - clim[0]) / clim[1]
        m[m > 1] = 1

        # compensate for rounding errors which sometimes lead to negative values
        m[m < 0] = 0

    # Create the RGB image
    rgb = np.zeros((*img.shape, 3))
    rgb[..., 0] = np.interp(p, np.linspace(-np.pi, np.pi, N), cmap[:, 0])
    rgb[..., 1] = np.interp(p, np.linspace(-np.pi, np.pi, N), cmap[:, 1])
    rgb[..., 2] = np.interp(p, np.linspace(-np.pi, np.pi, N), cmap[:, 2])

    return rgb, clim