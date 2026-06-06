import numpy as np

class GeometryEngine:

    @staticmethod
    def calculate_angle(a, b, c) -> float:
        """
        Compute the angle in degrees at point ``b`` formed by vectors b→a and b→c.

        Typical use: elbow joint angle, where:
          - ``a`` = shoulder landmark
          - ``b`` = elbow landmark
          - ``c`` = wrist landmark

        Parameters
        ----------
        a, b, c : array-like of float, shape (2,)
            (x, y) coordinates of three points. The angle is measured at ``b``.

        Returns
        -------
        float
            Angle in degrees in the range [0°, 180°].
            Values above 180° are mapped to 360° − angle so the result always
            falls within the stated range.

        90.0
        """
        a, b, c = np.array(a), np.array(b), np.array(c)
        radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
        angle = np.abs(radians * 180.0 / np.pi)
        return angle if angle <= 180.0 else 360 - angle