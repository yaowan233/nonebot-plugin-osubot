function CircumscribedCircle(points, pixelLength)
{
    var a = points[0].x - points[1].x, b = points[0].y - points[1].y,
        c = points[1].x - points[2].x, d = points[1].y - points[2].y,
        q = (a * d - b * c) * 2,
        l0 = points[0].x * points[0].x + points[0].y * points[0].y,
        l1 = points[1].x * points[1].x + points[1].y * points[1].y,
        l2 = points[2].x * points[2].x + points[2].y * points[2].y,
        x = ((l0 - l1) * d + (l1 - l2) * -b) / q,
        y = ((l0 - l1) * -c + (l1 - l2) * a) / q,
        dx = points[0].x - x,
        dy = points[0].y - y,
        r = Math.hypot(dx, dy),
        base = Math.atan2(dy, dx),
        t = pixelLength / r * Math.ccw(points[0], points[1], points[2]);
    if (!t)
    {
        // when points[2] is missing or vectors are parallel
        throw 'invalid data';
    }
    this.circle = {
        x: x,
        y: y,
        radius: r
    };
    this.angle = {
        base: base,
        delta: t
    };

    var nCurve = pixelLength / Curve.PRECISION | 0;
    this.path = [];
    for (var i = 0; i <= nCurve; i++)
    {
        this.path[i] = this.pointAt(i / nCurve);
    }

    Curve.call(this);
};
CircumscribedCircle.prototype = Object.create(Curve.prototype);
CircumscribedCircle.prototype.constructor = CircumscribedCircle;
CircumscribedCircle.prototype.pointAt = function(t)
{
    var angle = this.angle.base + this.angle.delta * t;
    return new Point(this.circle.x + Math.cos(angle) * this.circle.radius,
        this.circle.y + Math.sin(angle) * this.circle.radius);
};
