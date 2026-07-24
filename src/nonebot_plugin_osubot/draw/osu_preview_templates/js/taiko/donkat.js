function DonKat(data, beatmap)
{
    HitCircle.call(this, data, beatmap);

}
DonKat.prototype = Object.create(HitCircle.prototype, {
    don: {
        get: function()
        {
            return !this.kai | 0;
        }
    },
    kai: {
        get: function()
        {
            return ((this.hitSound & 10) != 0) | 0;
        }
    },
    dai: {
        get: function()
        {
            return this.hitSound & 4;
        }
    }
});
DonKat.prototype.constructor = DonKat;
DonKat.ID = 1;
Taiko.prototype.hitObjectTypes[DonKat.ID] = DonKat;
DonKat.prototype.draw = function(scroll, ctx)
{
    var diam = Taiko.DIAMETER * (this.dai ? 1.5 : 1);
    var x = this.beatmap.calcX(this.position.x, scroll);
    var border = 3;
    ctx.beginPath();
    ctx.arc(x, 0, diam / 2 - border / 2, -Math.PI, Math.PI);
    ctx.fillStyle = Taiko.DEFAULT_COLORS[this.kai];
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = border;
    ctx.stroke();
};
