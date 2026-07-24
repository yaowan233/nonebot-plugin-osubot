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
    var elapsed = scroll - this.time;
    var x = this.beatmap.calcX(this.position.x, scroll);
    var y = 0;
    var opacity = 1;
    var scale = 1;

    if (elapsed > 0)
    {
        // Match osu!taiko's hit feedback: snap the note to the judgement
        // point and launch it upwards while it fades out.
        x = 0;

        var progress = Math.min(1, elapsed / Taiko.HIT_ANIMATION_DURATION);
        opacity = 1 - progress;

        var scaleProgress = progress;
        var easedScale = 1 - Math.pow(1 - scaleProgress, 2);
        scale = 1 - 0.2 * easedScale;

        var easedRise = 1 - Math.pow(1 - progress, 2);
        y = -Taiko.HIT_TRAVEL_HEIGHT * easedRise;
    }

    ctx.save();
    ctx.globalAlpha *= opacity;
    ctx.translate(x, y);
    ctx.scale(scale, scale);
    var border = 3;
    ctx.beginPath();
    ctx.arc(0, 0, diam / 2 - border / 2, -Math.PI, Math.PI);
    ctx.fillStyle = Taiko.DEFAULT_COLORS[this.kai];
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = border;
    ctx.stroke();
    ctx.restore();
};
