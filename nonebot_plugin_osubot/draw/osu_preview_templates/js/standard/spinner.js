function Spinner(data, beatmap)
{
    HitCircle.call(this, data, beatmap);

    this.endTime = data[5] | 0;
    this.duration = this.endTime - this.time;
}
Spinner.prototype = Object.create(HitCircle.prototype);
Spinner.prototype.constructor = Spinner;
Spinner.ID = 8;
Standard.prototype.hitObjectTypes[Spinner.ID] = Spinner;
Spinner.FADE_IN_TIME = 500;
Spinner.FADE_OUT_TIME = 200;
Spinner.RADIUS = Beatmap.MAX_Y / 2;
Spinner.BORDER_WIDTH = Spinner.RADIUS / 20;
Spinner.prototype.draw = function(time, ctx)
{
    var dt = this.time - time,
        opacity = 1;
    if (dt >= 0)
    {
        opacity = (this.beatmap.approachTime - dt) / Spinner.FADE_IN_TIME;
    }
    else if (time > this.endTime)
    {
        opacity = 1 - (time - this.endTime) / Spinner.FADE_OUT_TIME;
    }
    ctx.globalAlpha = Math.max(0, Math.min(opacity, 1));
    ctx.save();
    // Spinner
    ctx.beginPath();
    ctx.arc(this.position.x, this.position.y,
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
    ctx.restore();
    // Approach
    if (dt < 0 && time <= this.endTime)
    {
        var scale = 1 + dt / this.duration;
        ctx.beginPath();
        ctx.arc(this.position.x, this.position.y,
            (Spinner.RADIUS - Spinner.BORDER_WIDTH / 2) * scale, -Math.PI, Math.PI);
        ctx.shadowBlur = 3;
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = (Spinner.BORDER_WIDTH / 2) * scale;
        ctx.stroke();
    }
};
