function EqualDistanceMultiCurve(curves, pixelLength)
{
    // https://github.com/itdelatrisu/opsu/blob/master/src/itdelatrisu/opsu/objects/curves/EqualDistanceMultiCurve.java
    var nCurve = pixelLength / Curve.PRECISION | 0;
    this.path = [];

    var distanceAt = 0,
        curveIndex = 0,
        curve = curves[curveIndex],
        pointIndex = 0,
        startPoint = curve.path[0],
        lastDistanceAt = 0;
    // for each distance, try to get in between the two points that are between it
    for (var i = 0; i <= nCurve; i++)
    {
        var prefDistance = i * pixelLength / nCurve | 0;
        while (distanceAt < prefDistance)
        {
            lastDistanceAt = distanceAt;
            startPoint = curve.path[pointIndex];

            if (++pointIndex >= curve.path.length)
            {
                if (curveIndex + 1 < curves.length)
                {
                    curve = curves[++curveIndex];
                    pointIndex = 0;
                }
                else
                {
                    pointIndex = curve.path.length - 1;
                    if (lastDistanceAt == distanceAt)
                    {
                        // out of points even though the preferred distance hasn't been reached
                        break;
                    }
                }
            }
            distanceAt += curve.distance[pointIndex];
        }
        var endPoint = curve.path[pointIndex];

        // interpolate the point between the two closest distances
        if (distanceAt - lastDistanceAt > 1)
        {
            this.path[i] = Math.lerp(startPoint, endPoint, (prefDistance - lastDistanceAt) / (distanceAt - lastDistanceAt));
        }
        else
        {
            this.path[i] = endPoint;
        }
    }

    Curve.call(this);
};
EqualDistanceMultiCurve.prototype = Object.create(Curve.prototype);
EqualDistanceMultiCurve.prototype.constructor = EqualDistanceMultiCurve;
EqualDistanceMultiCurve.prototype.pointAt = function(t)
{
    var indexF = this.path.length * t,
        index = indexF | 0;
    if (index + 1 < this.path.length)
    {
        return Math.lerp(this.path[index], this.path[index + 1], indexF - index);
    }
    else
    {
        return this.path[this.path.length - 1];
    }
};
