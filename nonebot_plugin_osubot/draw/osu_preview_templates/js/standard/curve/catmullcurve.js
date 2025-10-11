function CatmullCurve(points, pixelLength)
{
    // https://github.com/itdelatrisu/opsu/blob/master/src/itdelatrisu/opsu/objects/curves/CatmullCurve.java
    var catmulls = [],
        controls = [];
    if (!points[0].equalTo(points[1]))
    {
        controls.push(points[0]);
    }
    for (var i = 0; i < points.length; i++)
    {
        controls.push(points[i]);
        try
        {
            catmulls.push(new CentripetalCatmullRom(controls));
            controls.shift();
        }
        catch (e) {}
    }
    var point2 = points.slice(-2);
    if (!point2[1].equalTo(point2[0]))
    {
        controls.push(point2[1]);
    }
    try
    {
        catmulls.push(new CentripetalCatmullRom(controls));
    }
    catch (e) {}

    EqualDistanceMultiCurve.call(this, catmulls, pixelLength);
};
CatmullCurve.prototype = Object.create(EqualDistanceMultiCurve.prototype);
CatmullCurve.prototype.constructor = CatmullCurve;
