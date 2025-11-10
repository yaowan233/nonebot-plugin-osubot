function Curve()
{
    this.startAngle = this.path[0].angleTo(this.path[1]);
    var path2 = this.path.slice(-2);
    this.endAngle = path2[1].angleTo(path2[0]);
}
Curve.prototype.path = undefined;
Curve.prototype.pointAt = undefined;
Curve.PRECISION = 5;
Curve.parse = function(sliderType, points, pixelLength)
{
    try
    {
        if (sliderType == 'P')
        {
            return new CircumscribedCircle(points, pixelLength);
        }
        if (sliderType == 'C')
        {
            return new CatmullCurve(points, pixelLength);
        }
    }
    catch(e) {}
    try
    {
        return new LinearBezier(points, pixelLength, sliderType == 'L');
    }
    catch(e)
    {
        return new SingleNoteCurve(points[0]);
    }
}



function SingleNoteCurve(point)
{
    this.path = [point];
};
SingleNoteCurve.prototype = Object.create(Curve.prototype);
SingleNoteCurve.prototype.constructor = SingleNoteCurve;
SingleNoteCurve.prototype.pointAt = function(t)
{
    return this.path[0];
};
