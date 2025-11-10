Math.hypot = Math.hypot || function()
{
    var power = 0;
    for (var i = 0; i < arguments.length; i++)
    {
        power += arguments[i] * arguments[i];
    }
    return Math.sqrt(power);
};
Math.lerp = Math.lerp || function(a, b, t)
{
    if (a instanceof Point)
    {
        return new Point(Math.lerp(a.x, b.x, t), Math.lerp(a.y, b.y, t));
    }
    return a + (b - a) * t;
};
/** Calculate point C's direction by line AB
 * @return {Number}
 * 1    C is counter-clockwise to AB
 * 0    C is parallel to AB
 * -1   C is clockwise to AB
 */
Math.ccw = function(a, b, c)
{
    var ret = (b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y);
    if (ret > 0)
    {
        return 1;
    }
    if (ret < 0)
    {
        return -1;
    }
    return 0;
};
Math.clamp = function(num, min, max) {
    if (num < min) return min;
    if (num > max) return max;
    return num;
}
// https://developer.mozilla.org/en-US/docs/Web/API/HTMLCanvasElement/toBlob#Polyfill
if (!HTMLCanvasElement.prototype.toBlob)
{
    Object.defineProperty(HTMLCanvasElement.prototype, 'toBlob', {
        value: function (callback, type, quality)
        {

            var binStr = atob(this.toDataURL(type, quality).split(',')[1]),
                len = binStr.length,
                arr = new Uint8Array(len);

            for (var i = 0; i < len; i++)
            {
                arr[i] = binStr.charCodeAt(i);
            }

            callback(new Blob([ arr ], { type: type || 'image/png' }));
        }
    });
}
