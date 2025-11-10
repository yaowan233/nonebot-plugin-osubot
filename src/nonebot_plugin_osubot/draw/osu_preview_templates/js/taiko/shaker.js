function Shaker(data, beatmap)
{
    Spinner.call(this, data, beatmap);

}
Shaker.prototype = Object.create(Spinner.prototype, {});
Shaker.prototype.constructor = Shaker;
Shaker.ID = 8;
Taiko.prototype.hitObjectTypes[Shaker.ID] = Shaker;
Shaker.prototype.draw = function(scroll, ctx)
{
    var ds = this.beatmap.calcX(this.position.x, scroll);
    if (ds > 0)
    {
        var diam = Taiko.DIAMETER * 1.5;
        var border = 3;
        ctx.beginPath();
        ctx.arc(this.beatmap.calcX(this.position.x, scroll), 0, diam / 2 - border / 2, -Math.PI, Math.PI);
        ctx.fillStyle = Taiko.DEFAULT_COLORS[2];
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = border;
        ctx.stroke();
    }
    else
    {
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.translate(Beatmap.WIDTH / 2, Beatmap.HEIGHT / 2);
        // Spinner
        ctx.beginPath();
        ctx.arc(0, 0,
            Spinner.RADIUS - Spinner.BORDER_WIDTH / 2, -Math.PI, Math.PI);
        ctx.globalCompositeOperation = 'destination-over';
        ctx.shadowBlur = 0;
        ctx.fillStyle = 'rgba(0,0,0,.4)';
        ctx.fill();
        // Border
        ctx.shadowBlur = Spinner.BORDER_WIDTH;
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = Spinner.BORDER_WIDTH;
        ctx.stroke();
        // Approach
        if (ds < 0 && scroll <= this.endPosition.x)
        {
            var scale = 1 + ds / this.beatmap.calcX(this.endPosition.x, this.position.x);
            ctx.beginPath();
            ctx.arc(0, 0,
                (Spinner.RADIUS - Spinner.BORDER_WIDTH / 2) * scale, -Math.PI, Math.PI);
            ctx.globalCompositeOperation = 'source-over';
            ctx.shadowBlur = 3;
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = (Spinner.BORDER_WIDTH / 2) * scale;
            ctx.stroke();
        }
        ctx.restore();
    }
};
