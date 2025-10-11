function Point()
{
    if (arguments.length >= 2)
    {
        this.x = +arguments[0];
        this.y = +arguments[1];
    }
    else if (arguments.length == 1)
    {
        this.x = +arguments[0][0];
        this.y = +arguments[0][1];
    }
    else
    {
        this.x = 0;
        this.y = 0;
    }
}
Point.prototype.distanceTo = function(point)
{
    return Math.hypot(point.x - this.x, point.y - this.y);
};
Point.prototype.equalTo = function(point)
{
    return point instanceof Point &&
        this.x == point.x && this.y == point.y;
};
Point.prototype.angleTo = function(point)
{
    return Math.atan2(point.y - this.y, point.x - this.x);
};
Point.prototype.clone = function()
{
    return new Point(this.x, this.y);
};
Point.prototype.translate = function(n)
{
    if (n instanceof Point)
    {
        this.x += n.x;
        this.y += n.y;
    }
    else
    {
        this.x += n;
        this.y += n;
    }
    return this;
};
Point.prototype.scale = function(n)
{
    this.x *= n;
    this.y *= n;
    return this;
};
